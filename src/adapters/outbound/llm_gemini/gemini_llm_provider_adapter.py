import collections.abc
import typing

import google.auth.exceptions as google_auth_exceptions
import google.genai.errors as genai_errors
import google.genai.types as genai_types
import httpx
from google import genai

import src.infra.langsmith_tracer as langsmith_tracer
import src.ports.llm_provider_port as llm_provider_port
import src.services.dto.llm_dto as llm_dto
import src.services.exceptions as service_exceptions


class GeminiLlmProviderAdapter(llm_provider_port.LlmProviderPort):
    def __init__(
        self,
        project_id: str,
        location: str,
        model: str,
        max_output_tokens: int,
        tracer: langsmith_tracer.LangsmithTracer | None = None,
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._client: genai.Client | None = None
        if tracer is None:
            self._tracer = langsmith_tracer.LangsmithTracer()
        else:
            self._tracer = tracer

    def generate_reply(self, prompt_input: llm_dto.GenerateReplyInputDTO) -> llm_dto.AgentReplyDTO:
        trace_inputs: dict[str, object] = {
            "messages_count": len(prompt_input.messages),
            "tools_count": len(prompt_input.tools),
            "function_call_results_count": len(prompt_input.function_call_results),
            "system_prompt_chars": len(prompt_input.system_prompt),
        }
        trace_metadata: dict[str, object] = {
            "llm_provider": "gemini",
            "model": self._model,
            "location": self._location,
        }
        with self._tracer.trace(
            name="gemini.generate_reply",
            run_type="llm",
            inputs=trace_inputs,
            metadata=trace_metadata,
            tags=["llm", "gemini"],
        ) as trace_run:
            if not self._project_id:
                trace_run.set_error("GEMINI_PROJECT_ID is required")
                raise service_exceptions.ExternalProviderError("GEMINI_PROJECT_ID is required")

            if not self._location:
                trace_run.set_error("GEMINI_LOCATION is required")
                raise service_exceptions.ExternalProviderError("GEMINI_LOCATION is required")

            request_contents = self._build_request_contents(prompt_input)
            request_config: genai_types.GenerateContentConfigDict = {
                "system_instruction": prompt_input.system_prompt,
                "max_output_tokens": self._max_output_tokens,
            }
            tools = self._build_tools(prompt_input)
            if tools:
                function_calling_config: genai_types.FunctionCallingConfigDict = {
                    "mode": genai_types.FunctionCallingConfigMode.AUTO,
                }
                tool_config: genai_types.ToolConfigDict = {
                    "function_calling_config": function_calling_config,
                }
                request_config["tools"] = tools
                request_config["tool_config"] = tool_config
            client = self._get_client()

            try:
                response = client.models.generate_content(
                    model=self._model,
                    contents=request_contents,
                    config=request_config,
                )
            except google_auth_exceptions.DefaultCredentialsError as error:
                trace_run.set_error("google application default credentials are required")
                raise service_exceptions.ExternalProviderError(
                    "google application default credentials are required"
                ) from error
            except httpx.TimeoutException as error:
                trace_run.set_error("timeout calling gemini")
                raise service_exceptions.ExternalProviderError("timeout calling gemini") from error
            except httpx.RequestError as error:
                trace_run.set_error("network error calling gemini")
                raise service_exceptions.ExternalProviderError(
                    "network error calling gemini"
                ) from error
            except genai_errors.ClientError as error:
                detail = self._extract_api_error_detail(error)
                trace_run.set_error(
                    f"gemini rejected the request (status={error.code}, detail={detail})"
                )
                raise service_exceptions.ExternalProviderError(
                    f"gemini rejected the request (status={error.code}, detail={detail})"
                ) from error
            except genai_errors.ServerError as error:
                detail = self._extract_api_error_detail(error)
                trace_run.set_error(f"gemini server error (status={error.code}, detail={detail})")
                raise service_exceptions.ExternalProviderError(
                    f"gemini server error (status={error.code}, detail={detail})"
                ) from error
            except genai_errors.APIError as error:
                detail = self._extract_api_error_detail(error)
                trace_run.set_error(f"gemini api error (status={error.code}, detail={detail})")
                raise service_exceptions.ExternalProviderError(
                    f"gemini api error (status={error.code}, detail={detail})"
                ) from error

            function_calls = self._extract_function_calls(response)
            reply_text = self._extract_reply_text(response)
            if reply_text is None and not function_calls:
                trace_run.set_error("gemini returned empty content")
                raise service_exceptions.ExternalProviderError("gemini returned empty content")

            trace_run.set_outputs(
                {
                    "has_text_reply": reply_text is not None and reply_text != "",
                    "function_calls_count": len(function_calls),
                }
            )
            return llm_dto.AgentReplyDTO(
                content=reply_text if reply_text is not None else "",
                function_calls=function_calls,
            )

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(
                vertexai=True,
                project=self._project_id,
                location=self._location,
            )
        return self._client

    def _build_request_contents(
        self, prompt_input: llm_dto.GenerateReplyInputDTO
    ) -> list[dict[str, typing.Any]]:
        request_contents: list[dict[str, typing.Any]] = []
        for message in prompt_input.messages:
            role = "user"
            if message.role == "assistant":
                role = "model"
            request_contents.append(
                {
                    "role": role,
                    "parts": [{"text": message.content}],
                }
            )

        if prompt_input.function_call_results:
            model_function_call_parts: list[dict[str, typing.Any]] = []
            for function_result in prompt_input.function_call_results:
                function_call_payload: dict[str, typing.Any] = {
                    "name": function_result.function_call.name,
                    "args": function_result.function_call.args,
                }
                if function_result.function_call.call_id is not None:
                    function_call_payload["id"] = function_result.function_call.call_id
                thought_signature = self._resolve_function_call_thought_signature(
                    function_result.function_call
                )
                part_payload: dict[str, typing.Any] = {"functionCall": function_call_payload}
                if thought_signature is not None:
                    part_payload["thoughtSignature"] = thought_signature
                model_function_call_parts.append(part_payload)
            request_contents.append(
                {
                    "role": "model",
                    "parts": model_function_call_parts,
                }
            )
            for function_result in prompt_input.function_call_results:
                function_response_payload: dict[str, typing.Any] = {
                    "name": function_result.function_response.name,
                    "response": function_result.function_response.response,
                }
                if function_result.function_response.call_id is not None:
                    function_response_payload["id"] = function_result.function_response.call_id
                request_contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": function_response_payload,
                            }
                        ],
                    }
                )
        return request_contents

    def _build_tools(
        self, prompt_input: llm_dto.GenerateReplyInputDTO
    ) -> genai_types.ToolListUnionDict:
        if not prompt_input.tools:
            return []
        function_declarations: list[genai_types.FunctionDeclarationDict] = []
        for tool in prompt_input.tools:
            function_declarations.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters_json_schema": tool.parameters_json_schema,
                }
            )
        tool_entry: genai_types.ToolDict = {"function_declarations": function_declarations}
        return [tool_entry]

    def _extract_reply_text(self, response: typing.Any) -> str | None:
        candidate_parts = self._extract_first_candidate_parts(response)
        for part in candidate_parts:
            part_text = part.text
            if not isinstance(part_text, str):
                continue
            normalized_part_text = part_text.strip()
            if normalized_part_text:
                return normalized_part_text
        return None

    def _extract_function_calls(self, response: typing.Any) -> list[llm_dto.FunctionCallDTO]:
        candidate_parts = self._extract_first_candidate_parts(response)
        part_function_calls = self._extract_function_calls_from_candidate_parts(candidate_parts)
        if part_function_calls:
            return part_function_calls

        response_function_calls = response.function_calls
        if response_function_calls is not None:
            parsed_function_calls = self._normalize_function_calls(response_function_calls)
            if parsed_function_calls:
                return parsed_function_calls

        return []

    def _extract_function_calls_from_candidate_parts(
        self, candidate_parts: list[typing.Any]
    ) -> list[llm_dto.FunctionCallDTO]:
        function_calls: list[llm_dto.FunctionCallDTO] = []
        for part in candidate_parts:
            raw_function_call = part.function_call
            if raw_function_call is None:
                continue
            thought_signature = self._normalize_thought_signature(part.thought_signature)
            function_call = self._normalize_single_function_call(
                raw_function_call,
                thought_signature=thought_signature,
            )
            if function_call is not None:
                function_calls.append(function_call)
        return function_calls

    def _extract_first_candidate_parts(self, response: typing.Any) -> list[typing.Any]:
        candidates = response.candidates
        if candidates is None:
            return []
        if not candidates:
            return []

        first_candidate = candidates[0]
        if first_candidate is None or first_candidate.content is None:
            return []
        if first_candidate.content.parts is None:
            return []
        return list(first_candidate.content.parts)

    def _normalize_function_calls(
        self, raw_function_calls: list[typing.Any]
    ) -> list[llm_dto.FunctionCallDTO]:
        normalized_function_calls: list[llm_dto.FunctionCallDTO] = []
        for raw_function_call in raw_function_calls:
            normalized_call = self._normalize_single_function_call(
                raw_function_call,
                thought_signature=None,
            )
            if normalized_call is not None:
                normalized_function_calls.append(normalized_call)
        return normalized_function_calls

    def _normalize_single_function_call(
        self,
        raw_function_call: typing.Any,
        thought_signature: bytes | None,
    ) -> llm_dto.FunctionCallDTO | None:
        if raw_function_call is None:
            return None

        name: str | None = None
        raw_args: object = {}
        call_id: str | None = None
        raw_thought_signature: object = thought_signature

        if isinstance(raw_function_call, dict):
            raw_name = raw_function_call.get("name")
            if isinstance(raw_name, str) and raw_name:
                name = raw_name
            raw_args = raw_function_call.get("args", {})
            raw_call_id = raw_function_call.get("id")
            if isinstance(raw_call_id, str) and raw_call_id:
                call_id = raw_call_id
            if raw_thought_signature is None:
                raw_thought_signature = raw_function_call.get("thought_signature")
        else:
            try:
                raw_name = raw_function_call.name
                if isinstance(raw_name, str) and raw_name:
                    name = raw_name
                raw_args = raw_function_call.args
                raw_call_id = raw_function_call.id
                if isinstance(raw_call_id, str) and raw_call_id:
                    call_id = raw_call_id
            except AttributeError:
                return None

        if name is None:
            return None

        args: dict[str, object] = {}
        if isinstance(raw_args, collections.abc.Mapping):
            for key, value in raw_args.items():
                if isinstance(key, str):
                    args[key] = typing.cast(object, value)

        return llm_dto.FunctionCallDTO(
            name=name,
            args=args,
            call_id=call_id,
            thought_signature=self._normalize_thought_signature(raw_thought_signature),
        )

    def _normalize_thought_signature(self, raw_value: object) -> bytes | None:
        if isinstance(raw_value, bytes) and raw_value:
            return raw_value
        return None

    def _resolve_function_call_thought_signature(
        self,
        function_call: llm_dto.FunctionCallDTO,
    ) -> bytes | None:
        if function_call.thought_signature is not None:
            return function_call.thought_signature
        return None

    def _extract_api_error_detail(self, error: genai_errors.APIError) -> str:
        message = error.message
        if isinstance(message, str):
            normalized_message = message.strip()
            if normalized_message:
                return normalized_message

        status = error.status
        if isinstance(status, str):
            normalized_status = status.strip()
            if normalized_status:
                return normalized_status
        return "unknown error"

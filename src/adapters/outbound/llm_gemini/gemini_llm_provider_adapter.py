import typing

import google.auth.exceptions as google_auth_exceptions
import google.genai.errors as genai_errors
import httpx
from google import genai

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
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._client: genai.Client | None = None

    def generate_reply(self, prompt_input: llm_dto.GenerateReplyInputDTO) -> llm_dto.AgentReplyDTO:
        if not self._project_id:
            raise service_exceptions.ExternalProviderError("GEMINI_PROJECT_ID is required")

        if not self._location:
            raise service_exceptions.ExternalProviderError("GEMINI_LOCATION is required")

        request_contents = self._build_request_contents(prompt_input)
        request_config = {
            "system_instruction": prompt_input.system_prompt,
            "max_output_tokens": self._max_output_tokens,
        }
        client = self._get_client()

        try:
            response = client.models.generate_content(
                model=self._model,
                contents=request_contents,
                config=request_config,
            )
        except google_auth_exceptions.DefaultCredentialsError as error:
            raise service_exceptions.ExternalProviderError(
                "google application default credentials are required"
            ) from error
        except httpx.TimeoutException as error:
            raise service_exceptions.ExternalProviderError("timeout calling gemini") from error
        except httpx.RequestError as error:
            raise service_exceptions.ExternalProviderError(
                "network error calling gemini"
            ) from error
        except genai_errors.ClientError as error:
            detail = self._extract_api_error_detail(error)
            raise service_exceptions.ExternalProviderError(
                f"gemini rejected the request (status={error.code}, detail={detail})"
            ) from error
        except genai_errors.ServerError as error:
            detail = self._extract_api_error_detail(error)
            raise service_exceptions.ExternalProviderError(
                f"gemini server error (status={error.code}, detail={detail})"
            ) from error
        except genai_errors.APIError as error:
            detail = self._extract_api_error_detail(error)
            raise service_exceptions.ExternalProviderError(
                f"gemini api error (status={error.code}, detail={detail})"
            ) from error

        reply_text = self._extract_reply_text(response)
        if reply_text is None:
            raise service_exceptions.ExternalProviderError("gemini returned empty content")
        return llm_dto.AgentReplyDTO(content=reply_text)

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
        return request_contents

    def _extract_reply_text(self, response: typing.Any) -> str | None:
        response_text = response.text
        if isinstance(response_text, str):
            normalized_text = response_text.strip()
            if normalized_text:
                return normalized_text

        if response.candidates is None:
            return None

        for candidate in response.candidates:
            if candidate is None or candidate.content is None:
                continue
            if candidate.content.parts is None:
                continue
            for part in candidate.content.parts:
                part_text = part.text
                if not isinstance(part_text, str):
                    continue
                normalized_part_text = part_text.strip()
                if normalized_part_text:
                    return normalized_part_text
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

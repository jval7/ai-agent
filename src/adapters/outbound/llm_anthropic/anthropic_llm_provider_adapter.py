import json
import typing

import httpx

import src.ports.llm_provider_port as llm_provider_port
import src.services.dto.llm_dto as llm_dto
import src.services.exceptions as service_exceptions


class AnthropicLlmProviderAdapter(llm_provider_port.LlmProviderPort):
    def __init__(
        self,
        api_key: str,
        model: str,
        api_version: str,
        max_tokens: int,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._api_version = api_version
        self._max_tokens = max_tokens
        self._client = httpx.Client(timeout=timeout_seconds)

    def generate_reply(self, prompt_input: llm_dto.GenerateReplyInputDTO) -> llm_dto.AgentReplyDTO:
        if not self._api_key:
            raise service_exceptions.ExternalProviderError("ANTHROPIC_API_KEY is required")

        request_url = "https://api.anthropic.com/v1/messages"
        request_headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._api_version,
            "content-type": "application/json",
        }

        request_messages: list[dict[str, typing.Any]] = []
        for message in prompt_input.messages:
            role = "user"
            if message.role == "assistant":
                role = "assistant"
            request_messages.append(
                {
                    "role": role,
                    "content": [{"type": "text", "text": message.content}],
                }
            )

        request_payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": prompt_input.system_prompt,
            "messages": request_messages,
        }

        try:
            response = self._client.post(
                request_url,
                headers=request_headers,
                json=request_payload,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as error:
            raise service_exceptions.ExternalProviderError("timeout calling anthropic") from error
        except httpx.RequestError as error:
            raise service_exceptions.ExternalProviderError(
                "network error calling anthropic"
            ) from error
        except httpx.HTTPStatusError as error:
            raise service_exceptions.ExternalProviderError(
                "anthropic rejected the request"
            ) from error
        except json.JSONDecodeError as error:
            raise service_exceptions.ExternalProviderError(
                "invalid response from anthropic"
            ) from error

        if not isinstance(payload, dict):
            raise service_exceptions.ExternalProviderError("anthropic payload is invalid")

        content_items = payload.get("content")
        if not isinstance(content_items, list) or not content_items:
            raise service_exceptions.ExternalProviderError("anthropic returned empty content")

        for content_item in content_items:
            if not isinstance(content_item, dict):
                continue
            content_type = content_item.get("type")
            if content_type != "text":
                continue
            text_content = content_item.get("text")
            if isinstance(text_content, str) and text_content.strip():
                return llm_dto.AgentReplyDTO(content=text_content.strip())

        raise service_exceptions.ExternalProviderError("anthropic returned no text blocks")

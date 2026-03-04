import base64
import binascii
import json
import typing
import urllib.parse

import google.auth as google_auth
import google.auth.credentials as google_auth_credentials
import google.auth.exceptions as google_auth_exceptions
import google.auth.transport.requests as google_auth_requests
import httpx
import pydantic

_SECRET_MANAGER_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_SECRET_MANAGER_ACCESS_ENDPOINT_TEMPLATE = (
    "https://secretmanager.googleapis.com/v1/projects/{project_id}/"
    "secrets/{secret_id}/versions/{secret_version}:access"
)
_DEFAULT_APP_CONFIG_SECRET_ID = "AI_AGENT_APP_CONFIG_JSON"
_DEFAULT_APP_CONFIG_SECRET_VERSION = "latest"


class SecretManagerPayloadModel(pydantic.BaseModel):
    data: str


class SecretManagerAccessVersionResponseModel(pydantic.BaseModel):
    payload: SecretManagerPayloadModel


class LoadedAppConfigSecretModel(pydantic.BaseModel):
    project_id: str
    secret_json: str


class SecretManagerAppConfigLoaderAdapter:
    def __init__(
        self,
        secret_id: str | None = None,
        secret_version: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.secret_id = secret_id or _DEFAULT_APP_CONFIG_SECRET_ID
        self.secret_version = secret_version or _DEFAULT_APP_CONFIG_SECRET_VERSION
        self.timeout_seconds = timeout_seconds

    def load(self) -> LoadedAppConfigSecretModel:
        credentials, project_id = self._load_default_credentials()
        normalized_project_id = self._normalize_project_id(project_id)
        access_token = self._refresh_access_token(credentials)
        endpoint = self._build_secret_access_endpoint(normalized_project_id)
        response_text = self._access_secret(endpoint=endpoint, access_token=access_token)
        parsed_response = self._parse_access_response(response_text)
        secret_json = self._decode_secret_payload(parsed_response.payload.data)
        return LoadedAppConfigSecretModel(
            project_id=normalized_project_id,
            secret_json=secret_json,
        )

    def _load_default_credentials(
        self,
    ) -> tuple[google_auth_credentials.Credentials, str | None]:
        try:
            credentials_with_project_id: tuple[google_auth_credentials.Credentials, str | None]
            credentials_with_project_id = google_auth.default(scopes=[_SECRET_MANAGER_SCOPE])
            return credentials_with_project_id
        except google_auth_exceptions.DefaultCredentialsError as error:
            raise ValueError(
                "ADC credentials are required to load application config from Secret Manager"
            ) from error

    @staticmethod
    def _normalize_project_id(project_id: str | None) -> str:
        if project_id is None:
            raise ValueError(
                "No GCP project found in ADC. Configure one with: gcloud config set project <PROJECT_ID>"
            )

        normalized_project_id = project_id.strip()
        if normalized_project_id == "":
            raise ValueError(
                "No GCP project found in ADC. Configure one with: gcloud config set project <PROJECT_ID>"
            )
        return normalized_project_id

    @staticmethod
    def _refresh_access_token(credentials: google_auth_credentials.Credentials) -> str:
        request = google_auth_requests.Request()
        try:
            refresh_credentials = typing.cast(
                typing.Callable[[google_auth_requests.Request], None],
                credentials.refresh,
            )
            refresh_credentials(request)
        except google_auth_exceptions.RefreshError as error:
            raise ValueError("Could not refresh ADC access token for Secret Manager") from error

        access_token = credentials.token
        if not isinstance(access_token, str):
            raise ValueError("ADC returned an empty access token")

        normalized_access_token = access_token.strip()
        if normalized_access_token == "":
            raise ValueError("ADC returned an empty access token")

        return normalized_access_token

    def _build_secret_access_endpoint(self, project_id: str) -> str:
        encoded_secret_id = urllib.parse.quote(self.secret_id, safe="")
        encoded_secret_version = urllib.parse.quote(self.secret_version, safe="")
        return _SECRET_MANAGER_ACCESS_ENDPOINT_TEMPLATE.format(
            project_id=project_id,
            secret_id=encoded_secret_id,
            secret_version=encoded_secret_version,
        )

    def _access_secret(self, endpoint: str, access_token: str) -> str:
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        try:
            response = httpx.get(
                endpoint,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise ValueError("Timed out while reading app config secret") from error
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            raise ValueError(
                f"Secret Manager access failed with status code {status_code}"
            ) from error
        except httpx.RequestError as error:
            raise ValueError("Failed to reach Secret Manager API") from error

        return response.text

    @staticmethod
    def _parse_access_response(response_text: str) -> SecretManagerAccessVersionResponseModel:
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError as error:
            raise ValueError("Secret Manager response is not valid JSON") from error

        try:
            return SecretManagerAccessVersionResponseModel.model_validate(response_data)
        except pydantic.ValidationError as error:
            raise ValueError("Secret Manager response is missing payload.data") from error

    @staticmethod
    def _decode_secret_payload(encoded_payload: str) -> str:
        try:
            decoded_payload = base64.b64decode(encoded_payload, validate=True)
        except binascii.Error as error:
            raise ValueError("Secret payload is not valid base64") from error

        try:
            return decoded_payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Secret payload is not valid UTF-8") from error

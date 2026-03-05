import datetime
import json
import urllib.parse

import httpx

import src.infra.settings as app_settings
import src.ports.google_calendar_provider_port as google_calendar_provider_port
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.exceptions as service_exceptions


class GoogleCalendarProviderAdapter(google_calendar_provider_port.GoogleCalendarProviderPort):
    def __init__(self, settings: app_settings.Settings, timeout_seconds: float = 15.0) -> None:
        self._settings = settings
        self._client = httpx.Client(timeout=timeout_seconds)

    def build_oauth_connect_url(self, state: str, scopes: list[str]) -> str:
        if not self._settings.google_oauth_client_id:
            raise service_exceptions.ExternalProviderError("GOOGLE_OAUTH_CLIENT_ID is required")
        if not self._settings.google_oauth_redirect_uri:
            raise service_exceptions.ExternalProviderError("GOOGLE_OAUTH_REDIRECT_URI is required")

        query_params = {
            "client_id": self._settings.google_oauth_client_id,
            "redirect_uri": self._settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        encoded_query = urllib.parse.urlencode(query_params)
        return f"https://accounts.google.com/o/oauth2/v2/auth?{encoded_query}"

    def exchange_code_for_tokens(self, code: str) -> google_calendar_dto.GoogleOauthTokensDTO:
        if code.startswith("mock::"):
            segments = code.split("::")
            if len(segments) != 4:
                raise service_exceptions.ExternalProviderError(
                    "mock code must be mock::access_token::refresh_token::expires_in_seconds"
                )
            try:
                expires_in_seconds = int(segments[3])
            except ValueError as error:
                raise service_exceptions.ExternalProviderError(
                    "mock code expires_in_seconds is invalid"
                ) from error
            return google_calendar_dto.GoogleOauthTokensDTO(
                access_token=segments[1],
                refresh_token=segments[2],
                expires_in_seconds=expires_in_seconds,
                scope=None,
                token_type="Bearer",
            )

        self._validate_oauth_settings()
        payload = self._post_form(
            url="https://oauth2.googleapis.com/token",
            operation_label="exchanging google oauth code",
            form_data={
                "code": code,
                "client_id": self._settings.google_oauth_client_id,
                "client_secret": self._settings.google_oauth_client_secret,
                "redirect_uri": self._settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        return self._map_token_payload(payload)

    def refresh_access_token(self, refresh_token: str) -> google_calendar_dto.GoogleOauthTokensDTO:
        self._validate_oauth_settings()
        payload = self._post_form(
            url="https://oauth2.googleapis.com/token",
            operation_label="refreshing google access token",
            form_data={
                "refresh_token": refresh_token,
                "client_id": self._settings.google_oauth_client_id,
                "client_secret": self._settings.google_oauth_client_secret,
                "grant_type": "refresh_token",
            },
        )
        return self._map_token_payload(payload)

    def get_primary_calendar_metadata(
        self, access_token: str
    ) -> google_calendar_dto.GoogleCalendarMetadataDTO:
        payload = self._get_json(
            url="https://www.googleapis.com/calendar/v3/users/me/calendarList/primary",
            operation_label="loading primary calendar metadata",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        calendar_id = payload.get("id")
        if not isinstance(calendar_id, str) or not calendar_id:
            raise service_exceptions.ExternalProviderError("google calendar metadata is missing id")

        timezone = payload.get("timeZone")
        if not isinstance(timezone, str) or not timezone:
            timezone = "UTC"

        return google_calendar_dto.GoogleCalendarMetadataDTO(
            calendar_id=calendar_id,
            timezone=timezone,
        )

    def list_busy_intervals(
        self,
        access_token: str,
        calendar_id: str,
        time_min: datetime.datetime,
        time_max: datetime.datetime,
        timezone: str,
    ) -> list[google_calendar_dto.GoogleCalendarBusyIntervalDTO]:
        payload = self._post_json(
            url="https://www.googleapis.com/calendar/v3/freeBusy",
            operation_label="loading calendar busy intervals",
            headers={"Authorization": f"Bearer {access_token}"},
            body={
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "timeZone": timezone,
                "items": [{"id": calendar_id}],
            },
        )

        calendars = payload.get("calendars")
        if not isinstance(calendars, dict):
            return []
        primary_calendar = calendars.get(calendar_id)
        if not isinstance(primary_calendar, dict):
            return []
        busy = primary_calendar.get("busy")
        if not isinstance(busy, list):
            return []

        intervals: list[google_calendar_dto.GoogleCalendarBusyIntervalDTO] = []
        for item in busy:
            if not isinstance(item, dict):
                continue
            start_value = item.get("start")
            end_value = item.get("end")
            if not isinstance(start_value, str) or not isinstance(end_value, str):
                continue
            try:
                start_at = datetime.datetime.fromisoformat(start_value.replace("Z", "+00:00"))
                end_at = datetime.datetime.fromisoformat(end_value.replace("Z", "+00:00"))
            except ValueError:
                continue
            intervals.append(
                google_calendar_dto.GoogleCalendarBusyIntervalDTO(
                    start_at=start_at,
                    end_at=end_at,
                )
            )
        return intervals

    def create_event(
        self,
        access_token: str,
        calendar_id: str,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        timezone: str,
        summary: str,
    ) -> google_calendar_dto.GoogleCalendarEventDTO:
        encoded_calendar_id = urllib.parse.quote(calendar_id, safe="")
        payload = self._post_json(
            url=f"https://www.googleapis.com/calendar/v3/calendars/{encoded_calendar_id}/events",
            operation_label="creating google calendar event",
            headers={"Authorization": f"Bearer {access_token}"},
            body={
                "summary": summary,
                "start": {
                    "dateTime": start_at.isoformat(),
                    "timeZone": timezone,
                },
                "end": {
                    "dateTime": end_at.isoformat(),
                    "timeZone": timezone,
                },
            },
        )

        event_id = payload.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise service_exceptions.ExternalProviderError("google create event missing id")

        return google_calendar_dto.GoogleCalendarEventDTO(
            event_id=event_id,
            start_at=start_at,
            end_at=end_at,
        )

    def delete_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> None:
        encoded_calendar_id = urllib.parse.quote(calendar_id, safe="")
        encoded_event_id = urllib.parse.quote(event_id, safe="")
        self._delete(
            url=f"https://www.googleapis.com/calendar/v3/calendars/{encoded_calendar_id}/events/{encoded_event_id}",
            operation_label="deleting google calendar event",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def _validate_oauth_settings(self) -> None:
        if not self._settings.google_oauth_client_id:
            raise service_exceptions.ExternalProviderError("GOOGLE_OAUTH_CLIENT_ID is required")
        if not self._settings.google_oauth_client_secret:
            raise service_exceptions.ExternalProviderError("GOOGLE_OAUTH_CLIENT_SECRET is required")
        if not self._settings.google_oauth_redirect_uri:
            raise service_exceptions.ExternalProviderError("GOOGLE_OAUTH_REDIRECT_URI is required")

    def _map_token_payload(
        self, payload: dict[str, object]
    ) -> google_calendar_dto.GoogleOauthTokensDTO:
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise service_exceptions.ExternalProviderError(
                "google oauth response is missing access_token"
            )

        expires_in_raw = payload.get("expires_in")
        expires_in_seconds = 0
        if isinstance(expires_in_raw, int):
            expires_in_seconds = expires_in_raw
        elif isinstance(expires_in_raw, str):
            try:
                expires_in_seconds = int(expires_in_raw)
            except ValueError as error:
                raise service_exceptions.ExternalProviderError(
                    "google oauth response has invalid expires_in"
                ) from error
        if expires_in_seconds <= 0:
            raise service_exceptions.ExternalProviderError(
                "google oauth response has invalid expires_in"
            )

        refresh_token = payload.get("refresh_token")
        normalized_refresh_token: str | None = None
        if isinstance(refresh_token, str) and refresh_token:
            normalized_refresh_token = refresh_token

        scope = payload.get("scope")
        normalized_scope: str | None = None
        if isinstance(scope, str) and scope:
            normalized_scope = scope

        token_type = payload.get("token_type")
        normalized_token_type: str | None = None
        if isinstance(token_type, str) and token_type:
            normalized_token_type = token_type

        return google_calendar_dto.GoogleOauthTokensDTO(
            access_token=access_token,
            refresh_token=normalized_refresh_token,
            expires_in_seconds=expires_in_seconds,
            scope=normalized_scope,
            token_type=normalized_token_type,
        )

    def _post_form(
        self,
        url: str,
        operation_label: str,
        form_data: dict[str, str],
    ) -> dict[str, object]:
        try:
            response = self._client.post(url, data=form_data)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as error:
            raise service_exceptions.ExternalProviderError(
                f"timeout while {operation_label}"
            ) from error
        except httpx.RequestError as error:
            raise service_exceptions.ExternalProviderError(
                f"network error while {operation_label}"
            ) from error
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            detail = self._extract_error_detail(error.response)
            raise service_exceptions.ExternalProviderError(
                f"google rejected request while {operation_label} (status={status_code}, detail={detail})"
            ) from error
        except json.JSONDecodeError as error:
            raise service_exceptions.ExternalProviderError(
                f"invalid json response while {operation_label}"
            ) from error

        if not isinstance(payload, dict):
            raise service_exceptions.ExternalProviderError(
                f"invalid payload while {operation_label}"
            )
        return payload

    def _get_json(
        self,
        url: str,
        operation_label: str,
        headers: dict[str, str],
    ) -> dict[str, object]:
        try:
            response = self._client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as error:
            raise service_exceptions.ExternalProviderError(
                f"timeout while {operation_label}"
            ) from error
        except httpx.RequestError as error:
            raise service_exceptions.ExternalProviderError(
                f"network error while {operation_label}"
            ) from error
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            detail = self._extract_error_detail(error.response)
            raise service_exceptions.ExternalProviderError(
                f"google rejected request while {operation_label} (status={status_code}, detail={detail})"
            ) from error
        except json.JSONDecodeError as error:
            raise service_exceptions.ExternalProviderError(
                f"invalid json response while {operation_label}"
            ) from error

        if not isinstance(payload, dict):
            raise service_exceptions.ExternalProviderError(
                f"invalid payload while {operation_label}"
            )
        return payload

    def _post_json(
        self,
        url: str,
        operation_label: str,
        headers: dict[str, str],
        body: dict[str, object],
    ) -> dict[str, object]:
        try:
            response = self._client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as error:
            raise service_exceptions.ExternalProviderError(
                f"timeout while {operation_label}"
            ) from error
        except httpx.RequestError as error:
            raise service_exceptions.ExternalProviderError(
                f"network error while {operation_label}"
            ) from error
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            detail = self._extract_error_detail(error.response)
            raise service_exceptions.ExternalProviderError(
                f"google rejected request while {operation_label} (status={status_code}, detail={detail})"
            ) from error
        except json.JSONDecodeError as error:
            raise service_exceptions.ExternalProviderError(
                f"invalid json response while {operation_label}"
            ) from error

        if not isinstance(payload, dict):
            raise service_exceptions.ExternalProviderError(
                f"invalid payload while {operation_label}"
            )
        return payload

    def _delete(
        self,
        url: str,
        operation_label: str,
        headers: dict[str, str],
    ) -> None:
        try:
            response = self._client.delete(url, headers=headers)
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise service_exceptions.ExternalProviderError(
                f"timeout while {operation_label}"
            ) from error
        except httpx.RequestError as error:
            raise service_exceptions.ExternalProviderError(
                f"network error while {operation_label}"
            ) from error
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            detail = self._extract_error_detail(error.response)
            raise service_exceptions.ExternalProviderError(
                f"google rejected request while {operation_label} (status={status_code}, detail={detail})"
            ) from error

    def _extract_error_detail(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            text_value = response.text.strip()
            if text_value:
                return text_value[:280]
            return "unknown error"

        if not isinstance(payload, dict):
            return "unknown error"

        error_value = payload.get("error")
        if isinstance(error_value, str) and error_value.strip():
            return error_value.strip()
        if isinstance(error_value, dict):
            message_value = error_value.get("message")
            if isinstance(message_value, str) and message_value.strip():
                return message_value.strip()
        error_description = payload.get("error_description")
        if isinstance(error_description, str) and error_description.strip():
            return error_description.strip()
        return "unknown error"

import datetime

import src.domain.entities.google_calendar_connection as google_calendar_connection_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.google_calendar_connection_repository_port as google_calendar_connection_repository_port
import src.ports.google_calendar_provider_port as google_calendar_provider_port
import src.ports.id_generator_port as id_generator_port
import src.services.dto.google_calendar_dto as google_calendar_dto
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


class GoogleCalendarOnboardingService:
    def __init__(
        self,
        google_calendar_connection_repository: (
            google_calendar_connection_repository_port.GoogleCalendarConnectionRepositoryPort
        ),
        google_calendar_provider: google_calendar_provider_port.GoogleCalendarProviderPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._google_calendar_connection_repository = google_calendar_connection_repository
        self._google_calendar_provider = google_calendar_provider
        self._id_generator = id_generator
        self._clock = clock
        self._oauth_scopes = ["https://www.googleapis.com/auth/calendar"]

    def create_oauth_session(
        self, tenant_id: str, professional_user_id: str
    ) -> google_calendar_dto.GoogleOauthSessionResponseDTO:
        state = self._id_generator.new_token()
        now_value = self._clock.now()
        existing_connection = self._google_calendar_connection_repository.get_by_tenant_id(
            tenant_id
        )

        connection = google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id=tenant_id,
            professional_user_id=professional_user_id,
            status="PENDING",
            calendar_id=existing_connection.calendar_id
            if existing_connection is not None
            else None,
            timezone=existing_connection.timezone if existing_connection is not None else None,
            access_token=existing_connection.access_token
            if existing_connection is not None
            else None,
            refresh_token=existing_connection.refresh_token
            if existing_connection is not None
            else None,
            token_expires_at=existing_connection.token_expires_at
            if existing_connection is not None
            else None,
            oauth_state=state,
            scope=existing_connection.scope if existing_connection is not None else None,
            updated_at=now_value,
            connected_at=existing_connection.connected_at
            if existing_connection is not None
            else None,
        )
        self._google_calendar_connection_repository.save(connection)

        connect_url = self._google_calendar_provider.build_oauth_connect_url(
            state=state,
            scopes=self._oauth_scopes,
        )
        logger.info(
            "google_calendar.onboarding.session_created",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="google_calendar.onboarding.session_created",
                    message="google oauth session created",
                    data={"tenant_id": tenant_id},
                )
            },
        )
        return google_calendar_dto.GoogleOauthSessionResponseDTO(
            state=state,
            connect_url=connect_url,
        )

    def complete_oauth(
        self,
        tenant_id: str,
        professional_user_id: str,
        complete_dto: google_calendar_dto.GoogleOauthCompleteDTO,
    ) -> google_calendar_dto.GoogleCalendarConnectionStatusDTO:
        connection = self._google_calendar_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            raise service_exceptions.EntityNotFoundError("google oauth session not found")

        if connection.oauth_state != complete_dto.state:
            raise service_exceptions.InvalidStateError("google oauth state mismatch")

        return self._finalize_connection(
            connection=connection,
            professional_user_id=professional_user_id,
            code=complete_dto.code,
        )

    def complete_oauth_by_state(
        self, code: str, state: str
    ) -> google_calendar_dto.GoogleCalendarConnectionStatusDTO:
        connection = self._google_calendar_connection_repository.get_by_oauth_state(state)
        if connection is None:
            raise service_exceptions.EntityNotFoundError("google oauth state not found")

        return self._finalize_connection(
            connection=connection,
            professional_user_id=connection.professional_user_id,
            code=code,
        )

    def get_connection_status(
        self, tenant_id: str
    ) -> google_calendar_dto.GoogleCalendarConnectionStatusDTO:
        connection = self._google_calendar_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            return google_calendar_dto.GoogleCalendarConnectionStatusDTO(
                tenant_id=tenant_id,
                status="DISCONNECTED",
                calendar_id=None,
                professional_timezone=None,
                connected_at=None,
            )

        return google_calendar_dto.GoogleCalendarConnectionStatusDTO(
            tenant_id=tenant_id,
            status=connection.status,
            calendar_id=connection.calendar_id,
            professional_timezone=connection.timezone,
            connected_at=connection.connected_at,
        )

    def get_availability(
        self,
        tenant_id: str,
        from_at: datetime.datetime,
        to_at: datetime.datetime,
    ) -> google_calendar_dto.GoogleCalendarAvailabilityResponseDTO:
        connection = self._get_connected_connection_with_fresh_access_token(tenant_id)
        calendar_id = connection.calendar_id
        timezone = connection.timezone
        access_token = connection.access_token
        if calendar_id is None or timezone is None or access_token is None:
            raise service_exceptions.InvalidStateError(
                "google calendar connection is missing required metadata"
            )

        busy_intervals = self._google_calendar_provider.list_busy_intervals(
            access_token=access_token,
            calendar_id=calendar_id,
            time_min=from_at,
            time_max=to_at,
            timezone=timezone,
        )
        return google_calendar_dto.GoogleCalendarAvailabilityResponseDTO(
            tenant_id=tenant_id,
            calendar_id=calendar_id,
            timezone=timezone,
            busy_intervals=busy_intervals,
        )

    def has_conflict(
        self,
        tenant_id: str,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
    ) -> bool:
        availability = self.get_availability(
            tenant_id=tenant_id,
            from_at=start_at,
            to_at=end_at,
        )
        for busy_interval in availability.busy_intervals:
            if self._has_overlap(
                start_at=start_at,
                end_at=end_at,
                busy_start=busy_interval.start_at,
                busy_end=busy_interval.end_at,
            ):
                return True
        return False

    def create_event(
        self,
        tenant_id: str,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        summary: str,
    ) -> google_calendar_dto.GoogleCalendarEventDTO:
        connection = self._get_connected_connection_with_fresh_access_token(tenant_id)
        calendar_id = connection.calendar_id
        timezone = connection.timezone
        access_token = connection.access_token
        if calendar_id is None or timezone is None or access_token is None:
            raise service_exceptions.InvalidStateError(
                "google calendar connection is missing required metadata"
            )

        return self._google_calendar_provider.create_event(
            access_token=access_token,
            calendar_id=calendar_id,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone,
            summary=summary,
        )

    def delete_event(
        self,
        tenant_id: str,
        event_id: str,
    ) -> None:
        connection = self._get_connected_connection_with_fresh_access_token(tenant_id)
        calendar_id = connection.calendar_id
        access_token = connection.access_token
        if calendar_id is None or access_token is None:
            raise service_exceptions.InvalidStateError(
                "google calendar connection is missing required metadata"
            )

        self._google_calendar_provider.delete_event(
            access_token=access_token,
            calendar_id=calendar_id,
            event_id=event_id,
        )

    def update_event(
        self,
        tenant_id: str,
        event_id: str,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        timezone: str,
        summary: str,
    ) -> google_calendar_dto.GoogleCalendarEventDTO:
        connection = self._get_connected_connection_with_fresh_access_token(tenant_id)
        calendar_id = connection.calendar_id
        access_token = connection.access_token
        if calendar_id is None or access_token is None:
            raise service_exceptions.InvalidStateError(
                "google calendar connection is missing required metadata"
            )

        return self._google_calendar_provider.update_event(
            access_token=access_token,
            calendar_id=calendar_id,
            event_id=event_id,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone,
            summary=summary,
        )

    def _finalize_connection(
        self,
        connection: google_calendar_connection_entity.GoogleCalendarConnection,
        professional_user_id: str,
        code: str,
    ) -> google_calendar_dto.GoogleCalendarConnectionStatusDTO:
        tokens = self._google_calendar_provider.exchange_code_for_tokens(code)
        metadata = self._google_calendar_provider.get_primary_calendar_metadata(tokens.access_token)
        now_value = self._clock.now()
        token_expires_at = now_value + datetime.timedelta(seconds=tokens.expires_in_seconds)
        refresh_token = tokens.refresh_token
        if refresh_token is None:
            refresh_token = connection.refresh_token
        if refresh_token is None:
            raise service_exceptions.InvalidStateError(
                "google oauth did not return refresh token and there is no existing refresh token"
            )

        updated_connection = google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id=connection.tenant_id,
            professional_user_id=professional_user_id,
            status="CONNECTED",
            calendar_id=metadata.calendar_id,
            timezone=metadata.timezone,
            access_token=tokens.access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            oauth_state=None,
            scope=tokens.scope,
            updated_at=now_value,
            connected_at=now_value,
        )
        self._google_calendar_connection_repository.save(updated_connection)
        logger.info(
            "google_calendar.onboarding.completed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="google_calendar.onboarding.completed",
                    message="google calendar connected",
                    data={
                        "tenant_id": updated_connection.tenant_id,
                        "calendar_id": updated_connection.calendar_id,
                        "timezone": updated_connection.timezone,
                    },
                )
            },
        )

        return google_calendar_dto.GoogleCalendarConnectionStatusDTO(
            tenant_id=updated_connection.tenant_id,
            status=updated_connection.status,
            calendar_id=updated_connection.calendar_id,
            professional_timezone=updated_connection.timezone,
            connected_at=updated_connection.connected_at,
        )

    def _get_connected_connection_with_fresh_access_token(
        self, tenant_id: str
    ) -> google_calendar_connection_entity.GoogleCalendarConnection:
        connection = self._google_calendar_connection_repository.get_by_tenant_id(tenant_id)
        if connection is None:
            raise service_exceptions.InvalidStateError("google calendar is not connected")
        if connection.status != "CONNECTED":
            raise service_exceptions.InvalidStateError("google calendar is not connected")

        if connection.access_token is None:
            raise service_exceptions.InvalidStateError("google calendar access token is missing")

        token_expires_at = connection.token_expires_at
        now_value = self._clock.now()
        should_refresh = False
        if token_expires_at is None:
            should_refresh = True
        else:
            refresh_margin = datetime.timedelta(seconds=60)
            should_refresh = token_expires_at <= now_value + refresh_margin

        if not should_refresh:
            return connection

        refresh_token = connection.refresh_token
        if refresh_token is None:
            raise service_exceptions.InvalidStateError("google calendar refresh token is missing")

        refreshed_tokens = self._google_calendar_provider.refresh_access_token(refresh_token)
        refreshed_connection = google_calendar_connection_entity.GoogleCalendarConnection(
            tenant_id=connection.tenant_id,
            professional_user_id=connection.professional_user_id,
            status=connection.status,
            calendar_id=connection.calendar_id,
            timezone=connection.timezone,
            access_token=refreshed_tokens.access_token,
            refresh_token=refresh_token,
            token_expires_at=now_value
            + datetime.timedelta(seconds=refreshed_tokens.expires_in_seconds),
            oauth_state=connection.oauth_state,
            scope=refreshed_tokens.scope
            if refreshed_tokens.scope is not None
            else connection.scope,
            updated_at=now_value,
            connected_at=connection.connected_at,
        )
        self._google_calendar_connection_repository.save(refreshed_connection)
        return refreshed_connection

    def _has_overlap(
        self,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        busy_start: datetime.datetime,
        busy_end: datetime.datetime,
    ) -> bool:
        return start_at < busy_end and busy_start < end_at

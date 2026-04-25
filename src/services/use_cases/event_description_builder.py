import typing

import pydantic

import src.domain.entities.agent_profile as agent_profile_entity
import src.infra.logs as app_logs
import src.ports.agent_profile_repository_port as agent_profile_repository_port

logger = app_logs.get_logger(__name__)


class EventDescription(pydantic.BaseModel):
    description: str
    location: str | None = None


class EventDescriptionBuilder:
    """Builds the description and location fields for Google Calendar events.

    Reads AgentProfile from the repository to include office address and arrival
    instructions (PRESENCIAL) or virtual session instructions (VIRTUAL) in the
    event description. The location field is set to the office address for
    PRESENCIAL appointments so it appears prominently in the calendar invitation;
    for VIRTUAL appointments it is left as None (Google already shows
    "Meet video conference" as the location).
    """

    def __init__(
        self,
        agent_profile_repository: agent_profile_repository_port.AgentProfileRepositoryPort,
    ) -> None:
        self._agent_profile_repository = agent_profile_repository

    def build(
        self,
        tenant_id: str,
        modality: typing.Literal["PRESENCIAL", "VIRTUAL"] | None,
        consultation_reason: str | None,
        payment_status: typing.Literal["PENDING", "PAID"] = "PENDING",
    ) -> EventDescription:
        agent_profile = self._agent_profile_repository.get_by_tenant_id(tenant_id)
        description = self._build_description(modality, consultation_reason, agent_profile)
        location = self._resolve_location(modality, agent_profile)
        return EventDescription(description=description, location=location)

    def _build_description(
        self,
        modality: typing.Literal["PRESENCIAL", "VIRTUAL"] | None,
        consultation_reason: str | None,
        agent_profile: agent_profile_entity.AgentProfile | None,
    ) -> str:
        lines: list[str] = []
        if consultation_reason is not None:
            normalized_reason = consultation_reason.strip()
            if normalized_reason:
                lines.append(f"Motivo de consulta: {normalized_reason}")

        if modality == "PRESENCIAL":
            lines.extend(self._build_presencial_lines(agent_profile))
        elif modality == "VIRTUAL":
            lines.extend(self._build_virtual_lines(agent_profile))

        return "\n".join(lines) if lines else ""

    def _build_presencial_lines(
        self,
        agent_profile: agent_profile_entity.AgentProfile | None,
    ) -> list[str]:
        if agent_profile is None or agent_profile.office_location is None:
            logger.warning(
                "event_description_builder.missing_office_location",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="event_description_builder.missing_office_location",
                        message="AgentProfile has no office_location; description will be incomplete",
                        data={},
                    )
                },
            )
            return []

        office = agent_profile.office_location
        lines = [f"Dirección: {office.address}"]
        if office.arrival_instructions is not None:
            lines.append(f"Indicaciones de llegada: {office.arrival_instructions}")
        return lines

    def _build_virtual_lines(
        self,
        agent_profile: agent_profile_entity.AgentProfile | None,
    ) -> list[str]:
        if agent_profile is None or agent_profile.virtual_session_instructions is None:
            return []
        return [agent_profile.virtual_session_instructions]

    def _resolve_location(
        self,
        modality: typing.Literal["PRESENCIAL", "VIRTUAL"] | None,
        agent_profile: agent_profile_entity.AgentProfile | None,
    ) -> str | None:
        if modality != "PRESENCIAL":
            return None
        if agent_profile is None or agent_profile.office_location is None:
            return None
        return agent_profile.office_location.address

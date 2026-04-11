import src.domain.entities.tag as tag_entity
import src.infra.logs as app_logs
import src.ports.clock_port as clock_port
import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.id_generator_port as id_generator_port
import src.ports.tag_repository_port as tag_repository_port
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.dto.tag_dto as tag_dto
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


SCHEDULING_STATUS_TO_TAG_SLUG: dict[str, str] = {
    "AWAITING_CONSULTATION_REVIEW": "awaiting-consultation-review",
    "AWAITING_CONSULTATION_DETAILS": "awaiting-consultation-details",
    "AWAITING_PATIENT_CHOICE": "awaiting-patient-choice",
    "AWAITING_PAYMENT_CONFIRMATION": "awaiting-payment-confirmation",
    "CONSULTATION_REJECTED": "consultation-rejected",
    "CANCELLED": "cancelled",
    "BOOKED": "booked",
    "SESSION_CLOSED": "session-closed",
    "HUMAN_HANDOFF": "human-handoff",
}


SYSTEM_TAG_DEFINITIONS: list[dict[str, str]] = [
    {
        "slug": "awaiting-consultation-review",
        "name": "Esperando revisión",
        "color": "#F59E0B",
    },
    {
        "slug": "awaiting-consultation-details",
        "name": "Esperando detalles",
        "color": "#FBBF24",
    },
    {
        "slug": "awaiting-patient-choice",
        "name": "Esperando elección paciente",
        "color": "#60A5FA",
    },
    {
        "slug": "awaiting-payment-confirmation",
        "name": "Esperando confirmación pago",
        "color": "#A78BFA",
    },
    {
        "slug": "consultation-rejected",
        "name": "Consulta rechazada",
        "color": "#EF4444",
    },
    {
        "slug": "cancelled",
        "name": "Cancelada",
        "color": "#9CA3AF",
    },
    {
        "slug": "booked",
        "name": "Agendada",
        "color": "#10B981",
    },
    {
        "slug": "session-closed",
        "name": "Sesión cerrada",
        "color": "#6B7280",
    },
    {
        "slug": "human-handoff",
        "name": "Atención humana",
        "color": "#EC4899",
    },
]


class TagService:
    def __init__(
        self,
        tag_repository: tag_repository_port.TagRepositoryPort,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
        id_generator: id_generator_port.IdGeneratorPort,
        clock: clock_port.ClockPort,
    ) -> None:
        self._tag_repository = tag_repository
        self._conversation_repository = conversation_repository
        self._id_generator = id_generator
        self._clock = clock

    def ensure_system_tags(self, tenant_id: str) -> dict[str, tag_entity.Tag]:
        tags_by_slug: dict[str, tag_entity.Tag] = {}
        for definition in SYSTEM_TAG_DEFINITIONS:
            slug = definition["slug"]
            existing_tag = self._tag_repository.get_by_slug(tenant_id, slug)
            if existing_tag is not None:
                tags_by_slug[slug] = existing_tag
                continue

            now_value = self._clock.now()
            new_tag = tag_entity.Tag(
                id=self._id_generator.new_id(),
                tenant_id=tenant_id,
                name=definition["name"],
                slug=slug,
                color=definition["color"],
                tag_type="SYSTEM",
                created_at=now_value,
                updated_at=now_value,
            )
            self._tag_repository.save(new_tag)
            tags_by_slug[slug] = new_tag
            logger.info(
                "tag.system_created",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="tag.system_created",
                        message="system tag created lazily",
                        data={
                            "tenant_id": tenant_id,
                            "tag_id": new_tag.id,
                            "slug": slug,
                        },
                    )
                },
            )
        return tags_by_slug

    def list_tags(self, claims: auth_dto.TokenClaimsDTO) -> tag_dto.TagListResponseDTO:
        self._ensure_professional(claims)
        self.ensure_system_tags(claims.tenant_id)
        tags = self._tag_repository.list_by_tenant(claims.tenant_id)
        sorted_tags = sorted(tags, key=lambda item: (item.tag_type, item.name.lower()))
        return tag_dto.TagListResponseDTO(items=[self._to_tag_dto(item) for item in sorted_tags])

    def create_custom_tag(
        self,
        claims: auth_dto.TokenClaimsDTO,
        input_dto: tag_dto.CreateTagDTO,
    ) -> tag_dto.TagDTO:
        self._ensure_professional(claims)
        slug = self._build_custom_slug(input_dto.name)
        existing_tag = self._tag_repository.get_by_slug(claims.tenant_id, slug)
        if existing_tag is not None:
            raise service_exceptions.InvalidStateError("tag with same name already exists")

        now_value = self._clock.now()
        new_tag = tag_entity.Tag(
            id=self._id_generator.new_id(),
            tenant_id=claims.tenant_id,
            name=input_dto.name,
            slug=slug,
            color=input_dto.color,
            tag_type="CUSTOM",
            created_at=now_value,
            updated_at=now_value,
        )
        self._tag_repository.save(new_tag)
        logger.info(
            "tag.custom_created",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="tag.custom_created",
                    message="custom tag created by professional",
                    data={
                        "tenant_id": claims.tenant_id,
                        "tag_id": new_tag.id,
                        "slug": slug,
                    },
                )
            },
        )
        return self._to_tag_dto(new_tag)

    def update_tag(
        self,
        claims: auth_dto.TokenClaimsDTO,
        tag_id: str,
        input_dto: tag_dto.UpdateTagDTO,
    ) -> tag_dto.TagDTO:
        self._ensure_professional(claims)
        existing_tag = self._tag_repository.get_by_id(claims.tenant_id, tag_id)
        if existing_tag is None:
            raise service_exceptions.EntityNotFoundError("tag not found")

        updated_name = existing_tag.name
        updated_slug = existing_tag.slug
        updated_color = existing_tag.color

        if input_dto.color is not None:
            updated_color = input_dto.color

        if existing_tag.tag_type == "SYSTEM":
            if input_dto.name is not None and input_dto.name.strip() != existing_tag.name:
                raise service_exceptions.InvalidStateError("system tag name cannot be modified")
        else:
            if input_dto.name is not None:
                updated_name = input_dto.name
                new_slug = self._build_custom_slug(input_dto.name)
                if new_slug != existing_tag.slug:
                    conflicting_tag = self._tag_repository.get_by_slug(claims.tenant_id, new_slug)
                    if conflicting_tag is not None and conflicting_tag.id != existing_tag.id:
                        raise service_exceptions.InvalidStateError(
                            "tag with same name already exists"
                        )
                    updated_slug = new_slug

        updated_tag = tag_entity.Tag(
            id=existing_tag.id,
            tenant_id=existing_tag.tenant_id,
            name=updated_name,
            slug=updated_slug,
            color=updated_color,
            tag_type=existing_tag.tag_type,
            created_at=existing_tag.created_at,
            updated_at=self._clock.now(),
        )
        self._tag_repository.save(updated_tag)
        logger.info(
            "tag.updated",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="tag.updated",
                    message="tag updated by professional",
                    data={
                        "tenant_id": claims.tenant_id,
                        "tag_id": updated_tag.id,
                        "tag_type": updated_tag.tag_type,
                    },
                )
            },
        )
        return self._to_tag_dto(updated_tag)

    def delete_tag(self, claims: auth_dto.TokenClaimsDTO, tag_id: str) -> None:
        self._ensure_professional(claims)
        existing_tag = self._tag_repository.get_by_id(claims.tenant_id, tag_id)
        if existing_tag is None:
            raise service_exceptions.EntityNotFoundError("tag not found")
        if existing_tag.tag_type == "SYSTEM":
            raise service_exceptions.InvalidStateError("system tags cannot be deleted")

        self._remove_tag_from_all_conversations(claims.tenant_id, tag_id)
        self._tag_repository.delete(claims.tenant_id, tag_id)
        logger.info(
            "tag.deleted",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="tag.deleted",
                    message="custom tag deleted by professional",
                    data={
                        "tenant_id": claims.tenant_id,
                        "tag_id": tag_id,
                    },
                )
            },
        )

    def assign_tag_to_conversation(
        self,
        claims: auth_dto.TokenClaimsDTO,
        conversation_id: str,
        tag_id: str,
    ) -> None:
        self._ensure_professional(claims)
        tag = self._tag_repository.get_by_id(claims.tenant_id, tag_id)
        if tag is None:
            raise service_exceptions.EntityNotFoundError("tag not found")

        conversation = self._conversation_repository.get_conversation_by_id(
            claims.tenant_id, conversation_id
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        conversation.add_tag(tag_id, self._clock.now())
        self._conversation_repository.save_conversation(conversation)
        logger.info(
            "tag.assigned_to_conversation",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="tag.assigned_to_conversation",
                    message="tag assigned to conversation",
                    data={
                        "tenant_id": claims.tenant_id,
                        "tag_id": tag_id,
                        "conversation_id": conversation_id,
                    },
                )
            },
        )

    def remove_tag_from_conversation(
        self,
        claims: auth_dto.TokenClaimsDTO,
        conversation_id: str,
        tag_id: str,
    ) -> None:
        self._ensure_professional(claims)
        conversation = self._conversation_repository.get_conversation_by_id(
            claims.tenant_id, conversation_id
        )
        if conversation is None:
            raise service_exceptions.EntityNotFoundError("conversation not found")

        conversation.remove_tag(tag_id, self._clock.now())
        self._conversation_repository.save_conversation(conversation)
        logger.info(
            "tag.removed_from_conversation",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="tag.removed_from_conversation",
                    message="tag removed from conversation",
                    data={
                        "tenant_id": claims.tenant_id,
                        "tag_id": tag_id,
                        "conversation_id": conversation_id,
                    },
                )
            },
        )

    def sync_scheduling_tags(
        self,
        tenant_id: str,
        conversation_id: str,
        new_status: str,
    ) -> None:
        system_tags_by_slug = self.ensure_system_tags(tenant_id)

        conversation = self._conversation_repository.get_conversation_by_id(
            tenant_id, conversation_id
        )
        if conversation is None:
            logger.warning(
                "tag.sync_scheduling_tags.conversation_missing",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="tag.sync_scheduling_tags.conversation_missing",
                        message="conversation not found while syncing scheduling tags",
                        data={
                            "tenant_id": tenant_id,
                            "conversation_id": conversation_id,
                            "new_status": new_status,
                        },
                    )
                },
            )
            return

        scheduling_system_tag_ids: set[str] = set()
        for slug in SCHEDULING_STATUS_TO_TAG_SLUG.values():
            system_tag = system_tags_by_slug.get(slug)
            if system_tag is not None:
                scheduling_system_tag_ids.add(system_tag.id)

        now_value = self._clock.now()
        mutated = False
        for existing_tag_id in list(conversation.tag_ids):
            if existing_tag_id in scheduling_system_tag_ids:
                conversation.remove_tag(existing_tag_id, now_value)
                mutated = True

        target_slug = SCHEDULING_STATUS_TO_TAG_SLUG.get(new_status)
        if target_slug is not None:
            target_tag = system_tags_by_slug.get(target_slug)
            if target_tag is not None:
                conversation.add_tag(target_tag.id, now_value)
                mutated = True

        if mutated:
            self._conversation_repository.save_conversation(conversation)
            logger.info(
                "tag.sync_scheduling_tags.synced",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="tag.sync_scheduling_tags.synced",
                        message="scheduling tags synced on conversation",
                        data={
                            "tenant_id": tenant_id,
                            "conversation_id": conversation_id,
                            "new_status": new_status,
                            "target_slug": target_slug,
                        },
                    )
                },
            )

    def _remove_tag_from_all_conversations(self, tenant_id: str, tag_id: str) -> None:
        conversations = self._conversation_repository.list_conversations(tenant_id)
        now_value = self._clock.now()
        for conversation in conversations:
            if tag_id not in conversation.tag_ids:
                continue
            conversation.remove_tag(tag_id, now_value)
            self._conversation_repository.save_conversation(conversation)

    def _ensure_professional(self, claims: auth_dto.TokenClaimsDTO) -> None:
        if claims.role != service_constants.DEFAULT_PROFESSIONAL_ROLE:
            raise service_exceptions.AuthorizationError("professional role required")

    def _build_custom_slug(self, name: str) -> str:
        normalized = name.strip().lower()
        slug_characters: list[str] = []
        previous_was_dash = False
        for character in normalized:
            if character.isalnum():
                slug_characters.append(character)
                previous_was_dash = False
            elif character in (" ", "-", "_"):
                if not previous_was_dash and slug_characters:
                    slug_characters.append("-")
                    previous_was_dash = True
        slug = "".join(slug_characters).strip("-")
        if slug == "":
            raise service_exceptions.InvalidStateError("tag name cannot be empty")
        return f"custom-{slug}"

    def _to_tag_dto(self, tag: tag_entity.Tag) -> tag_dto.TagDTO:
        return tag_dto.TagDTO(
            id=tag.id,
            tenant_id=tag.tenant_id,
            name=tag.name,
            slug=tag.slug,
            color=tag.color,
            tag_type=tag.tag_type,
            created_at=tag.created_at,
            updated_at=tag.updated_at,
        )

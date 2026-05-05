import datetime

import src.ports.conversation_repository_port as conversation_repository_port
import src.ports.manual_appointment_repository_port as manual_appointment_repository_port
import src.ports.patient_repository_port as patient_repository_port
import src.ports.scheduled_reminder_repository_port as scheduled_reminder_repository_port
import src.ports.scheduling_repository_port as scheduling_repository_port
import src.ports.tenant_repository_port as tenant_repository_port
import src.ports.user_repository_port as user_repository_port
import src.services.dto.admin_dto as admin_dto


class AdminDashboardService:
    def __init__(
        self,
        tenant_repository: tenant_repository_port.TenantRepositoryPort,
        user_repository: user_repository_port.UserRepositoryPort,
        patient_repository: patient_repository_port.PatientRepositoryPort,
        conversation_repository: conversation_repository_port.ConversationRepositoryPort,
        manual_appointment_repository: (
            manual_appointment_repository_port.ManualAppointmentRepositoryPort
        ),
        scheduling_repository: scheduling_repository_port.SchedulingRepositoryPort,
        scheduled_reminder_repository: (
            scheduled_reminder_repository_port.ScheduledReminderRepositoryPort
        ),
    ) -> None:
        self._tenant_repository = tenant_repository
        self._user_repository = user_repository
        self._patient_repository = patient_repository
        self._conversation_repository = conversation_repository
        self._manual_appointment_repository = manual_appointment_repository
        self._scheduling_repository = scheduling_repository
        self._scheduled_reminder_repository = scheduled_reminder_repository

    def _build_tenant_summary(
        self,
        tenant_id: str,
        tenant_name: str,
        professional_name: str | None,
        now: datetime.datetime,
    ) -> admin_dto.TenantSummaryDTO:
        patient_count = self._patient_repository.count_by_tenant(tenant_id)
        conversation_count = self._conversation_repository.count_conversations(tenant_id)
        upcoming_appointment_count = self._manual_appointment_repository.count_by_tenant(
            tenant_id, status="SCHEDULED"
        )
        pending_reminder_count = self._scheduled_reminder_repository.count_by_tenant(
            tenant_id, status="PENDING"
        )

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        active_today = self._conversation_repository.count_active_since(tenant_id, today_start)

        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        revenue_this_month = self._manual_appointment_repository.sum_paid_revenue_since(
            tenant_id, month_start
        ) + self._scheduling_repository.sum_paid_revenue_since(tenant_id, month_start)

        conversation_activity = self._conversation_repository.get_latest_activity(tenant_id)
        appointment_activity = self._manual_appointment_repository.get_latest_activity(tenant_id)
        last_activity: datetime.datetime | None
        if conversation_activity is not None and appointment_activity is not None:
            last_activity = max(conversation_activity, appointment_activity)
        else:
            last_activity = conversation_activity or appointment_activity

        owner = self._user_repository.get_first_by_tenant(tenant_id)
        owner_email: str | None = owner.email if owner is not None else None
        owner_is_active = owner.is_active if owner is not None else False

        return admin_dto.TenantSummaryDTO(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            professional_name=professional_name,
            patient_count=patient_count,
            conversation_count=conversation_count,
            active_conversations_today=active_today,
            manual_appointment_count_upcoming=upcoming_appointment_count,
            pending_reminder_count=pending_reminder_count,
            total_revenue_cop_this_month=revenue_this_month,
            last_activity_at=last_activity,
            owner_email=owner_email,
            owner_is_active=owner_is_active,
        )

    def list_tenant_summaries(
        self,
        search: str | None = None,
    ) -> list[admin_dto.TenantSummaryDTO]:
        tenants = self._tenant_repository.list_all(include_admin=False)
        now = datetime.datetime.now(tz=datetime.UTC)
        summaries: list[admin_dto.TenantSummaryDTO] = []
        for tenant in tenants:
            if tenant.is_admin_tenant:
                continue
            if search is not None:
                needle = search.casefold()
                if (
                    needle not in tenant.name.casefold()
                    and needle not in (tenant.professional_name or "").casefold()
                ):
                    continue
            summary = self._build_tenant_summary(
                tenant_id=tenant.id,
                tenant_name=tenant.name,
                professional_name=tenant.professional_name,
                now=now,
            )
            summaries.append(summary)
        summaries.sort(key=lambda s: s.tenant_name)
        return summaries

    def get_tenant_summary(self, tenant_id: str) -> admin_dto.TenantSummaryDTO | None:
        tenant = self._tenant_repository.get_by_id(tenant_id)
        if tenant is None or tenant.is_admin_tenant:
            return None
        now = datetime.datetime.now(tz=datetime.UTC)
        return self._build_tenant_summary(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            professional_name=tenant.professional_name,
            now=now,
        )

    def get_global_metrics(self) -> admin_dto.GlobalMetricsDTO:
        tenants = self._tenant_repository.list_all(include_admin=False)
        non_admin_tenants = [t for t in tenants if not t.is_admin_tenant]
        now = datetime.datetime.now(tz=datetime.UTC)

        total_patients = 0
        total_conversations = 0
        total_upcoming = 0
        total_pending_reminders = 0
        control_mode_distribution: dict[str, int] = {}
        tenant_summaries: list[admin_dto.TenantSummaryDTO] = []

        for tenant in non_admin_tenants:
            summary = self._build_tenant_summary(
                tenant_id=tenant.id,
                tenant_name=tenant.name,
                professional_name=tenant.professional_name,
                now=now,
            )
            tenant_summaries.append(summary)
            total_patients += summary.patient_count
            total_conversations += summary.conversation_count
            total_upcoming += summary.manual_appointment_count_upcoming
            total_pending_reminders += summary.pending_reminder_count

            conversations = self._conversation_repository.list_conversations(tenant.id)
            for conv in conversations:
                mode = conv.control_mode
                control_mode_distribution[mode] = control_mode_distribution.get(mode, 0) + 1

        tenants_active = sum(
            1
            for s in tenant_summaries
            if s.active_conversations_today > 0 or s.conversation_count > 0
        )

        top_tenants = sorted(tenant_summaries, key=lambda s: s.conversation_count, reverse=True)[:5]

        return admin_dto.GlobalMetricsDTO(
            tenants_count=len(non_admin_tenants),
            tenants_active=tenants_active,
            total_patients=total_patients,
            total_conversations=total_conversations,
            total_manual_appointments_upcoming=total_upcoming,
            total_pending_reminders=total_pending_reminders,
            control_mode_distribution=control_mode_distribution,
            top_tenants_by_conversations=top_tenants,
        )

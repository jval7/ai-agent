import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.scheduled_reminder as scheduled_reminder_entity
import src.ports.scheduled_reminder_repository_port as scheduled_reminder_repository_port


class FirestoreScheduledReminderRepositoryAdapter(
    scheduled_reminder_repository_port.ScheduledReminderRepositoryPort
):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, reminder: scheduled_reminder_entity.ScheduledReminder) -> None:
        reminder_document = firestore_paths.tenant_scheduled_reminder_document(
            self._client,
            reminder.tenant_id,
            reminder.id,
        )
        reminder_data = firestore_model_mapper.model_to_document(reminder)
        try:
            reminder_document.set(reminder_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save scheduled reminder in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save scheduled reminder in firestore"
            ) from error

    def get_by_id(
        self,
        tenant_id: str,
        reminder_id: str,
    ) -> scheduled_reminder_entity.ScheduledReminder | None:
        reminder_document = firestore_paths.tenant_scheduled_reminder_document(
            self._client,
            tenant_id,
            reminder_id,
        )
        try:
            snapshot = reminder_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read scheduled reminder from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read scheduled reminder from firestore"
            ) from error
        if not snapshot.exists:
            return None

        reminder_raw_data = snapshot.to_dict()
        if reminder_raw_data is None:
            return None

        reminder = firestore_model_mapper.parse_document(
            reminder_raw_data,
            scheduled_reminder_entity.ScheduledReminder,
            "scheduled reminder",
        )
        if reminder.tenant_id != tenant_id:
            return None
        return reminder

    def list_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
    ) -> list[scheduled_reminder_entity.ScheduledReminder]:
        reminders_collection = firestore_paths.tenant_scheduled_reminders_collection(
            self._client,
            tenant_id,
        )
        if status is None:
            query = reminders_collection
        else:
            query = reminders_collection.where("status", "==", status)

        try:
            snapshots = list(query.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list scheduled reminders from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list scheduled reminders from firestore"
            ) from error

        reminders: list[scheduled_reminder_entity.ScheduledReminder] = []
        for snapshot in snapshots:
            reminder_raw_data = snapshot.to_dict()
            if reminder_raw_data is None:
                continue
            reminder = firestore_model_mapper.parse_document(
                reminder_raw_data,
                scheduled_reminder_entity.ScheduledReminder,
                "scheduled reminder",
            )
            if reminder.tenant_id == tenant_id:
                reminders.append(reminder)
        return reminders

    def list_pending_by_source(
        self,
        tenant_id: str,
        source_type: str,
        source_id: str,
    ) -> list[scheduled_reminder_entity.ScheduledReminder]:
        reminders_collection = firestore_paths.tenant_scheduled_reminders_collection(
            self._client,
            tenant_id,
        )
        query = (
            reminders_collection.where("source_type", "==", source_type)
            .where("source_id", "==", source_id)
            .where("status", "==", "PENDING")
        )

        try:
            snapshots = list(query.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list scheduled reminders from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list scheduled reminders from firestore"
            ) from error

        reminders: list[scheduled_reminder_entity.ScheduledReminder] = []
        for snapshot in snapshots:
            reminder_raw_data = snapshot.to_dict()
            if reminder_raw_data is None:
                continue
            reminder = firestore_model_mapper.parse_document(
                reminder_raw_data,
                scheduled_reminder_entity.ScheduledReminder,
                "scheduled reminder",
            )
            if reminder.tenant_id == tenant_id:
                reminders.append(reminder)
        return reminders

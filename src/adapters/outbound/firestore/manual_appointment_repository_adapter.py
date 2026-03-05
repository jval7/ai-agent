import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.manual_appointment as manual_appointment_entity
import src.ports.manual_appointment_repository_port as manual_appointment_repository_port


class FirestoreManualAppointmentRepositoryAdapter(
    manual_appointment_repository_port.ManualAppointmentRepositoryPort
):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, appointment: manual_appointment_entity.ManualAppointment) -> None:
        appointment_document = firestore_paths.tenant_manual_appointment_document(
            self._client,
            appointment.tenant_id,
            appointment.id,
        )
        appointment_data = firestore_model_mapper.model_to_document(appointment)
        try:
            appointment_document.set(appointment_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save manual appointment in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save manual appointment in firestore"
            ) from error

    def get_by_id(
        self,
        tenant_id: str,
        appointment_id: str,
    ) -> manual_appointment_entity.ManualAppointment | None:
        appointment_document = firestore_paths.tenant_manual_appointment_document(
            self._client,
            tenant_id,
            appointment_id,
        )
        try:
            snapshot = appointment_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read manual appointment from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read manual appointment from firestore"
            ) from error
        if not snapshot.exists:
            return None

        appointment_raw_data = snapshot.to_dict()
        if appointment_raw_data is None:
            return None

        appointment = firestore_model_mapper.parse_document(
            appointment_raw_data,
            manual_appointment_entity.ManualAppointment,
            "manual appointment",
        )
        if appointment.tenant_id != tenant_id:
            return None
        return appointment

    def list_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
    ) -> list[manual_appointment_entity.ManualAppointment]:
        appointments_collection = firestore_paths.tenant_manual_appointments_collection(
            self._client,
            tenant_id,
        )
        if status is None:
            query = appointments_collection
        else:
            query = appointments_collection.where("status", "==", status)

        try:
            snapshots = list(query.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list manual appointments from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list manual appointments from firestore"
            ) from error

        appointments: list[manual_appointment_entity.ManualAppointment] = []
        for snapshot in snapshots:
            appointment_raw_data = snapshot.to_dict()
            if appointment_raw_data is None:
                continue
            appointment = firestore_model_mapper.parse_document(
                appointment_raw_data,
                manual_appointment_entity.ManualAppointment,
                "manual appointment",
            )
            if appointment.tenant_id == tenant_id:
                appointments.append(appointment)
        return appointments

    def list_by_patient(
        self,
        tenant_id: str,
        patient_whatsapp_user_id: str,
        status: str | None = None,
    ) -> list[manual_appointment_entity.ManualAppointment]:
        appointments_collection = firestore_paths.tenant_manual_appointments_collection(
            self._client,
            tenant_id,
        )
        query = appointments_collection.where(
            "patient_whatsapp_user_id",
            "==",
            patient_whatsapp_user_id,
        )
        if status is not None:
            query = query.where("status", "==", status)

        try:
            snapshots = list(query.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list manual appointments from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list manual appointments from firestore"
            ) from error

        appointments: list[manual_appointment_entity.ManualAppointment] = []
        for snapshot in snapshots:
            appointment_raw_data = snapshot.to_dict()
            if appointment_raw_data is None:
                continue
            appointment = firestore_model_mapper.parse_document(
                appointment_raw_data,
                manual_appointment_entity.ManualAppointment,
                "manual appointment",
            )
            if appointment.tenant_id == tenant_id:
                appointments.append(appointment)
        return appointments

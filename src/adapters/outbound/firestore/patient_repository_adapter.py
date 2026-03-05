import google.api_core.exceptions as google_api_exceptions
import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.errors as firestore_errors
import src.adapters.outbound.firestore.model_mapper as firestore_model_mapper
import src.adapters.outbound.firestore.paths as firestore_paths
import src.domain.entities.patient as patient_entity
import src.ports.patient_repository_port as patient_repository_port


class FirestorePatientRepositoryAdapter(patient_repository_port.PatientRepositoryPort):
    def __init__(self, client: google_cloud_firestore.Client) -> None:
        self._client = client

    def save(self, patient: patient_entity.Patient) -> None:
        patient_document = firestore_paths.tenant_patient_document(
            self._client,
            patient.tenant_id,
            patient.whatsapp_user_id,
        )
        patient_data = firestore_model_mapper.model_to_document(patient)
        try:
            patient_document.set(patient_data)
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save patient in firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to save patient in firestore"
            ) from error

    def get_by_whatsapp_user(
        self,
        tenant_id: str,
        whatsapp_user_id: str,
    ) -> patient_entity.Patient | None:
        patient_document = firestore_paths.tenant_patient_document(
            self._client,
            tenant_id,
            whatsapp_user_id,
        )
        try:
            snapshot = patient_document.get()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read patient from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to read patient from firestore"
            ) from error
        if not snapshot.exists:
            return None

        patient_raw_data = snapshot.to_dict()
        if patient_raw_data is None:
            return None
        patient = firestore_model_mapper.parse_document(
            patient_raw_data,
            patient_entity.Patient,
            "patient",
        )
        if patient.tenant_id != tenant_id:
            return None
        return patient

    def list_by_tenant(self, tenant_id: str) -> list[patient_entity.Patient]:
        patients_collection = firestore_paths.tenant_document(self._client, tenant_id).collection(
            firestore_paths.PATIENTS_COLLECTION
        )
        try:
            snapshots = list(patients_collection.stream())
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list patients from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to list patients from firestore"
            ) from error

        patients: list[patient_entity.Patient] = []
        for snapshot in snapshots:
            patient_raw_data = snapshot.to_dict()
            if patient_raw_data is None:
                continue
            patient = firestore_model_mapper.parse_document(
                patient_raw_data,
                patient_entity.Patient,
                "patient",
            )
            if patient.tenant_id == tenant_id:
                patients.append(patient)
        return patients

    def delete(self, tenant_id: str, whatsapp_user_id: str) -> None:
        patient_document = firestore_paths.tenant_patient_document(
            self._client,
            tenant_id,
            whatsapp_user_id,
        )
        try:
            patient_document.delete()
        except google_api_exceptions.GoogleAPICallError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete patient from firestore"
            ) from error
        except google_api_exceptions.RetryError as error:
            raise firestore_errors.FirestoreRepositoryError(
                "failed to delete patient from firestore"
            ) from error

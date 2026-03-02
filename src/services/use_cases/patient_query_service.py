import src.domain.entities.patient as patient_entity
import src.ports.patient_repository_port as patient_repository_port
import src.services.constants as service_constants
import src.services.dto.auth_dto as auth_dto
import src.services.dto.patient_dto as patient_dto
import src.services.exceptions as service_exceptions


class PatientQueryService:
    def __init__(
        self,
        patient_repository: patient_repository_port.PatientRepositoryPort,
    ) -> None:
        self._patient_repository = patient_repository

    def list_patients(self, claims: auth_dto.TokenClaimsDTO) -> patient_dto.PatientListResponseDTO:
        self._ensure_owner(claims)
        patients = self._patient_repository.list_by_tenant(claims.tenant_id)
        sorted_patients = sorted(patients, key=lambda item: item.created_at, reverse=True)
        return patient_dto.PatientListResponseDTO(
            items=[self._to_patient_dto(item) for item in sorted_patients]
        )

    def get_patient(
        self,
        claims: auth_dto.TokenClaimsDTO,
        whatsapp_user_id: str,
    ) -> patient_dto.PatientDTO:
        self._ensure_owner(claims)
        patient = self._patient_repository.get_by_whatsapp_user(claims.tenant_id, whatsapp_user_id)
        if patient is None:
            raise service_exceptions.EntityNotFoundError("patient not found")
        return self._to_patient_dto(patient)

    def _ensure_owner(self, claims: auth_dto.TokenClaimsDTO) -> None:
        if claims.role != service_constants.DEFAULT_OWNER_ROLE:
            raise service_exceptions.AuthorizationError("owner role required")

    def _to_patient_dto(
        self,
        patient: patient_entity.Patient,
    ) -> patient_dto.PatientDTO:
        return patient_dto.PatientDTO(
            tenant_id=patient.tenant_id,
            whatsapp_user_id=patient.whatsapp_user_id,
            first_name=patient.first_name,
            last_name=patient.last_name,
            email=patient.email,
            age=patient.age,
            consultation_reason=patient.consultation_reason,
            location=patient.location,
            phone=patient.phone,
            created_at=patient.created_at,
        )

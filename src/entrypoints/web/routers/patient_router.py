import fastapi

import src.entrypoints.web.dependencies as http_dependencies
import src.infra.container as app_container
import src.services.dto.auth_dto as auth_dto
import src.services.dto.patient_dto as patient_dto

router = fastapi.APIRouter(prefix="/v1/patients", tags=["patients"])


@router.get("", response_model=patient_dto.PatientListResponseDTO)
def list_patients(
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> patient_dto.PatientListResponseDTO:
    return container.patient_query_service.list_patients(claims)


@router.get("/{whatsapp_user_id}", response_model=patient_dto.PatientDTO)
def get_patient(
    whatsapp_user_id: str,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> patient_dto.PatientDTO:
    return container.patient_query_service.get_patient(claims, whatsapp_user_id)


@router.post("", response_model=patient_dto.PatientDTO)
def create_patient(
    create_dto: patient_dto.CreatePatientDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> patient_dto.PatientDTO:
    return container.patient_query_service.create_patient(claims, create_dto)


@router.put("/{whatsapp_user_id}", response_model=patient_dto.PatientDTO)
def update_patient(
    whatsapp_user_id: str,
    update_dto: patient_dto.UpdatePatientDTO,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> patient_dto.PatientDTO:
    return container.patient_query_service.update_patient(claims, whatsapp_user_id, update_dto)


@router.delete("/{whatsapp_user_id}", status_code=fastapi.status.HTTP_204_NO_CONTENT)
def delete_patient(
    whatsapp_user_id: str,
    claims: auth_dto.TokenClaimsDTO = fastapi.Depends(http_dependencies.get_current_claims),
    container: app_container.AppContainer = fastapi.Depends(http_dependencies.get_container),
) -> None:
    container.patient_query_service.delete_patient(claims, whatsapp_user_id)

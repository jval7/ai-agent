import datetime

import pytest

import src.adapters.outbound.inmemory.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.patient as patient_entity
import src.services.dto.auth_dto as auth_dto
import src.services.exceptions as service_exceptions
import src.services.use_cases.patient_query_service as patient_query_service


def build_service() -> tuple[
    patient_query_service.PatientQueryService,
    patient_repository_adapter.InMemoryPatientRepositoryAdapter,
]:
    store = in_memory_store.InMemoryStore()
    repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
    service = patient_query_service.PatientQueryService(patient_repository=repository)
    return service, repository


def build_claims(role: str) -> auth_dto.TokenClaimsDTO:
    return auth_dto.TokenClaimsDTO(
        sub="user-1",
        tenant_id="tenant-1",
        role=role,
        exp=2000000000,
        jti="jti-1",
        token_kind="access",
    )


def test_list_patients_requires_owner_role() -> None:
    service, _ = build_service()

    with pytest.raises(service_exceptions.AuthorizationError):
        service.list_patients(build_claims("agent"))


def test_get_patient_raises_not_found() -> None:
    service, _ = build_service()

    with pytest.raises(service_exceptions.EntityNotFoundError):
        service.get_patient(build_claims("owner"), "wa-404")


def test_list_patients_returns_sorted_items() -> None:
    service, repository = build_service()
    repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            consultation_reason="Ansiedad",
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )
    repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-2",
            first_name="John",
            last_name="Smith",
            email="john@example.com",
            age=34,
            consultation_reason="Sueno",
            location="Medellin",
            phone="573001445566",
            created_at=datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC),
        )
    )

    response = service.list_patients(build_claims("owner"))

    assert len(response.items) == 2
    assert response.items[0].whatsapp_user_id == "wa-2"
    assert response.items[1].whatsapp_user_id == "wa-1"


def test_get_patient_returns_single_patient() -> None:
    service, repository = build_service()
    repository.save(
        patient_entity.Patient(
            tenant_id="tenant-1",
            whatsapp_user_id="wa-1",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            age=29,
            consultation_reason="Ansiedad",
            location="Bogota",
            phone="573001112233",
            created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
    )

    response = service.get_patient(build_claims("owner"), "wa-1")

    assert response.whatsapp_user_id == "wa-1"
    assert response.first_name == "Jane"

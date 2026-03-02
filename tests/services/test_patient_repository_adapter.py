import datetime

import src.adapters.outbound.inmemory.patient_repository_adapter as patient_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.domain.entities.patient as patient_entity


def test_patient_repository_save_and_get_by_whatsapp_user() -> None:
    store = in_memory_store.InMemoryStore()
    repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
    patient = patient_entity.Patient(
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

    repository.save(patient)

    restored_patient = repository.get_by_whatsapp_user("tenant-1", "wa-1")
    assert restored_patient is not None
    assert restored_patient.first_name == "Jane"
    assert repository.get_by_whatsapp_user("tenant-2", "wa-1") is None


def test_patient_repository_list_by_tenant_returns_only_tenant_items() -> None:
    store = in_memory_store.InMemoryStore()
    repository = patient_repository_adapter.InMemoryPatientRepositoryAdapter(store)
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
            tenant_id="tenant-2",
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

    tenant_1_items = repository.list_by_tenant("tenant-1")

    assert len(tenant_1_items) == 1
    assert tenant_1_items[0].whatsapp_user_id == "wa-1"

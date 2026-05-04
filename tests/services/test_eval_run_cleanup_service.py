"""Tests para EvalRunCleanupService — cascade delete de corridas de evaluación."""

import datetime

import src.adapters.outbound.inmemory.agent_profile_repository_adapter as agent_profile_repository_adapter
import src.adapters.outbound.inmemory.eval_run_repository_adapter as eval_run_repository_adapter
import src.adapters.outbound.inmemory.refresh_token_repository_adapter as refresh_token_repository_adapter
import src.adapters.outbound.inmemory.store as in_memory_store
import src.adapters.outbound.inmemory.tenant_repository_adapter as tenant_repository_adapter
import src.adapters.outbound.inmemory.user_repository_adapter as user_repository_adapter
import src.adapters.outbound.inmemory.whatsapp_connection_repository_adapter as whatsapp_connection_repository_adapter
import src.adapters.outbound.security.jwt_provider_adapter as jwt_provider_adapter
import src.adapters.outbound.security.password_hasher_adapter as password_hasher_adapter
import src.domain.entities.eval_run as eval_run_entity
import src.domain.entities.tenant as tenant_entity
import src.services.use_cases.auth_service as auth_service_mod
import src.services.use_cases.eval_run_cleanup_service as eval_run_cleanup_service
import src.services.use_cases.eval_tenant_service as eval_tenant_service_mod
import tests.fakes.fake_adapters as fake_adapters

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _make_run(
    run_id: str,
    shape_name: str,
    eval_tenant_id: str | None = None,
) -> eval_run_entity.EvalRun:
    return eval_run_entity.EvalRun(
        run_id=run_id,
        shape_name=shape_name,
        started_at=_NOW,
        total_personas=1,
        ok=1,
        fail=0,
        skipped=False,
        eval_tenant_id=eval_tenant_id,
    )


def _make_conversation(persona_id: str) -> eval_run_entity.EvalRunConversationSnapshot:
    return eval_run_entity.EvalRunConversationSnapshot(
        persona_id=persona_id,
        combos_satisfied=[["new_patient"]],
        status="ok",
        elapsed_seconds=1.0,
    )


def _build_services(
    id_values: list[str] | None = None,
) -> tuple[
    eval_run_cleanup_service.EvalRunCleanupService,
    eval_run_repository_adapter.InMemoryEvalRunRepositoryAdapter,
    tenant_repository_adapter.InMemoryTenantRepositoryAdapter,
    eval_tenant_service_mod.EvalTenantService,
]:
    if id_values is None:
        id_values = [
            "tenant-1",
            "user-1",
            "jti-access-1",
            "jti-refresh-1",
            "tenant-2",
            "user-2",
            "jti-access-2",
            "jti-refresh-2",
        ]

    store = in_memory_store.InMemoryStore()
    tenant_repo = tenant_repository_adapter.InMemoryTenantRepositoryAdapter(store)
    user_repo = user_repository_adapter.InMemoryUserRepositoryAdapter(store)
    agent_profile_repo = agent_profile_repository_adapter.InMemoryAgentProfileRepositoryAdapter(
        store
    )
    wa_repo = whatsapp_connection_repository_adapter.InMemoryWhatsappConnectionRepositoryAdapter(
        store
    )
    refresh_token_repo = refresh_token_repository_adapter.InMemoryRefreshTokenRepositoryAdapter()
    eval_run_repo = eval_run_repository_adapter.InMemoryEvalRunRepositoryAdapter()

    clock = fake_adapters.FixedClock(_NOW)
    id_generator = fake_adapters.SequenceIdGenerator(id_values)
    hasher = password_hasher_adapter.Pbkdf2PasswordHasherAdapter()
    jwt_provider = jwt_provider_adapter.Hs256JwtProviderAdapter(secret="test-secret", clock=clock)

    auth_svc = auth_service_mod.AuthService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        password_hasher=hasher,
        jwt_provider=jwt_provider,
        refresh_token_repository=refresh_token_repo,
        id_generator=id_generator,
        clock=clock,
        default_system_prompt="test-prompt",
        access_ttl_seconds=600,
        refresh_ttl_seconds=3600,
    )
    eval_tenant_svc = eval_tenant_service_mod.EvalTenantService(
        tenant_repository=tenant_repo,
        user_repository=user_repo,
        agent_profile_repository=agent_profile_repo,
        whatsapp_connection_repository=wa_repo,
        password_hasher=hasher,
        auth_service=auth_svc,
        id_generator=id_generator,
        clock=clock,
    )
    cleanup_svc = eval_run_cleanup_service.EvalRunCleanupService(
        eval_run_repository=eval_run_repo,
        tenant_repository=tenant_repo,
        eval_tenant_service=eval_tenant_svc,
    )
    return cleanup_svc, eval_run_repo, tenant_repo, eval_tenant_svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cascade_deletes_all_run_docs_and_conversations() -> None:
    """Borra todos los docs {run_id}_* y sus sub-collections."""
    cleanup_svc, eval_run_repo, _tenant_repo, _ = _build_services()

    run_a = _make_run("run-xyz", "psicologa")
    run_b = _make_run("run-xyz", "ortodoncista")
    eval_run_repo.save_run(run_a)
    eval_run_repo.save_run(run_b)
    eval_run_repo.save_conversation("run-xyz_psicologa", _make_conversation("persona-1"))
    eval_run_repo.save_conversation("run-xyz_ortodoncista", _make_conversation("persona-2"))

    stats = cleanup_svc.delete_eval_run_cascade("run-xyz")

    assert stats.eval_runs_deleted == 2
    assert stats.tenants_deleted == 0
    assert eval_run_repo.get_run("run-xyz_psicologa") is None
    assert eval_run_repo.get_run("run-xyz_ortodoncista") is None
    assert eval_run_repo.get_conversations("run-xyz_psicologa") == []
    assert eval_run_repo.get_conversations("run-xyz_ortodoncista") == []


def test_cascade_deletes_eval_tenant_when_present() -> None:
    """Si el run tiene eval_tenant_id apuntando a un eval tenant, lo borra."""
    cleanup_svc, eval_run_repo, tenant_repo, eval_tenant_svc = _build_services()

    # Crear un eval tenant real via el servicio
    created = eval_tenant_svc.create_eval_tenant(run_id="run-with-tenant", shape_name="psicologa")
    tenant_id = created.tenant_id

    run = _make_run("run-with-tenant", "psicologa", eval_tenant_id=tenant_id)
    eval_run_repo.save_run(run)

    stats = cleanup_svc.delete_eval_run_cascade("run-with-tenant")

    assert stats.eval_runs_deleted == 1
    assert stats.tenants_deleted == 1
    assert tenant_repo.get_by_id(tenant_id) is None
    assert eval_run_repo.get_run("run-with-tenant_psicologa") is None


def test_cascade_does_not_raise_when_tenant_missing() -> None:
    """Si el tenant ya no existe, no levanta excepción — best-effort."""
    cleanup_svc, eval_run_repo, _tenant_repo, _ = _build_services()

    run = _make_run("run-ghost", "psicologa", eval_tenant_id="nonexistent-tenant-id")
    eval_run_repo.save_run(run)

    stats = cleanup_svc.delete_eval_run_cascade("run-ghost")

    # El run igual se borra
    assert stats.eval_runs_deleted == 1
    # El tenant no se contabiliza porque nunca existió
    assert stats.tenants_deleted == 0


def test_cascade_does_not_delete_non_eval_tenant() -> None:
    """Un tenant regular (is_eval_tenant=False) NO se toca."""
    cleanup_svc, eval_run_repo, tenant_repo, _ = _build_services()

    regular_tenant = tenant_entity.Tenant(
        id="regular-tenant",
        name="Real Clinic",
        created_at=_NOW,
        updated_at=_NOW,
        is_eval_tenant=False,
    )
    tenant_repo.save(regular_tenant)

    run = _make_run("run-regular", "psicologa", eval_tenant_id="regular-tenant")
    eval_run_repo.save_run(run)

    stats = cleanup_svc.delete_eval_run_cascade("run-regular")

    # Run se borra, tenant se preserva
    assert stats.eval_runs_deleted == 1
    assert stats.tenants_deleted == 0
    assert tenant_repo.get_by_id("regular-tenant") is not None


def test_stats_correct_when_no_run_docs_exist() -> None:
    """Si no hay docs para ese run_id, retorna zeros."""
    cleanup_svc, _eval_run_repo, _tenant_repo, _ = _build_services()

    stats = cleanup_svc.delete_eval_run_cascade("run-nonexistent")

    assert stats.eval_runs_deleted == 0
    assert stats.tenants_deleted == 0


def test_stats_correct_with_multiple_shapes_and_tenants() -> None:
    """Múltiples shapes con tenant propio → stats correctas."""
    cleanup_svc, eval_run_repo, tenant_repo, eval_tenant_svc = _build_services(
        id_values=[
            "tenant-1",
            "user-1",
            "jti-a1",
            "jti-r1",
            "tenant-2",
            "user-2",
            "jti-a2",
            "jti-r2",
        ]
    )

    created_a = eval_tenant_svc.create_eval_tenant(run_id="run-multi", shape_name="psicologa")
    created_b = eval_tenant_svc.create_eval_tenant(run_id="run-multi", shape_name="ortodoncista")

    eval_run_repo.save_run(_make_run("run-multi", "psicologa", eval_tenant_id=created_a.tenant_id))
    eval_run_repo.save_run(
        _make_run("run-multi", "ortodoncista", eval_tenant_id=created_b.tenant_id)
    )

    stats = cleanup_svc.delete_eval_run_cascade("run-multi")

    assert stats.eval_runs_deleted == 2
    assert stats.tenants_deleted == 2
    assert tenant_repo.get_by_id(created_a.tenant_id) is None
    assert tenant_repo.get_by_id(created_b.tenant_id) is None

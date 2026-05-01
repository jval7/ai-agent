"""EvalQueryService — consulta de shapes (filesystem), personas (módulo Python)
y eval_runs (Firestore via port) para el dashboard de evaluación.

Nota de arquitectura: este servicio importa `scripts.personas` y `scripts.coverage`
directamente. Es una excepción intencional a la regla "scripts no en src" — el
dashboard necesita la misma fuente de verdad que el runner, y duplicar las listas
introduciría drift. Los módulos `scripts.*` son read-only desde la perspectiva
del servicio.
"""

import pathlib

import scripts.coverage as coverage_module
import scripts.personas as personas_module
import src.domain.entities.eval_run as eval_run_entity
import src.ports.eval_run_repository_port as eval_run_repository_port
import src.services.agentic.prompts.professional_profile_xml_renderer as xml_renderer
import src.services.dto.eval_dto as eval_dto


class EvalQueryService:
    def __init__(
        self,
        eval_run_repository: eval_run_repository_port.EvalRunRepositoryPort,
        shapes_directory: pathlib.Path,
    ) -> None:
        self._eval_run_repository = eval_run_repository
        self._shapes_directory = shapes_directory

    def list_shapes(self) -> list[eval_dto.ShapeDTO]:
        shapes = coverage_module.load_shapes_from_dir(self._shapes_directory)
        result: list[eval_dto.ShapeDTO] = []
        for shape in shapes:
            rendered = xml_renderer.render_system_prompt_xml(shape.agent_profile)
            required_combos: list[list[str]] = [
                [str(cap) for cap in combo] for combo in shape.metadata.required_combos
            ]
            result.append(
                eval_dto.ShapeDTO(
                    name=shape.metadata.name,
                    description=shape.metadata.description,
                    required_combos=required_combos,
                    rendered_system_prompt=rendered,
                )
            )
        return result

    def list_personas(self) -> list[eval_dto.PersonaDTO]:
        result: list[eval_dto.PersonaDTO] = []
        for persona in personas_module.PSICOLOGA_PERSONAS:
            result.append(
                eval_dto.PersonaDTO(
                    id=persona.id,
                    display_name=persona.display_name,
                    capabilities=list(persona.capabilities),
                    profile_group="psicologa",
                )
            )
        for persona in personas_module.ORTODONCIA_PERSONAS:
            result.append(
                eval_dto.PersonaDTO(
                    id=persona.id,
                    display_name=persona.display_name,
                    capabilities=list(persona.capabilities),
                    profile_group="ortodoncista",
                )
            )
        return result

    def list_prompt_versions(self) -> list[eval_dto.PromptVersionDTO]:
        # Placeholder hasta que aterrice el plan PromptVersion en Firestore.
        return [eval_dto.PromptVersionDTO(id="current", label="Versión actual", active=True)]

    def list_runs(self, limit: int = 50) -> list[eval_dto.EvalRunListItemDTO]:
        runs = self._eval_run_repository.list_runs(limit=limit)
        return [_run_to_list_item(run) for run in runs]

    def get_run(self, run_doc_id: str) -> eval_dto.EvalRunDetailDTO | None:
        run = self._eval_run_repository.get_run(run_doc_id)
        if run is None:
            return None
        conversations = self._eval_run_repository.get_conversations(run_doc_id)
        # El doc_id canónico siempre se computa desde la entidad (Opción C).
        computed_doc_id = f"{run.run_id}_{run.shape_name}"
        return _run_to_detail(run, computed_doc_id, conversations)


# ---------------------------------------------------------------------------
# Helpers de mapeo entity → DTO
# ---------------------------------------------------------------------------


def _run_to_list_item(run: eval_run_entity.EvalRun) -> eval_dto.EvalRunListItemDTO:
    # Opción C: el service construye el doc_id como "{run_id}_{shape_name}".
    # El par (run_id, shape_name) identifica unívocamente el documento en Firestore,
    # lo que hace que la concatenación sea determinista y sin colisiones dentro de
    # un mismo run (un run produce exactamente un documento por shape).
    run_doc_id = f"{run.run_id}_{run.shape_name}"
    return eval_dto.EvalRunListItemDTO(
        run_doc_id=run_doc_id,
        run_id=run.run_id,
        shape_name=run.shape_name,
        started_at=run.started_at,
        finished_at=run.finished_at,
        total_personas=run.total_personas,
        ok=run.ok,
        fail=run.fail,
        skipped=run.skipped,
    )


def _judge_verdict_to_dto(
    verdict: eval_run_entity.JudgeVerdict,
) -> eval_dto.JudgeVerdictDTO:
    verifications = [
        eval_dto.CapabilityVerificationDTO(
            capability=v.capability,
            verified=v.verified,
            evidence=v.evidence,
            reasoning=v.reasoning,
        )
        for v in verdict.verifications
    ]
    return eval_dto.JudgeVerdictDTO(
        declared_capabilities=verdict.declared_capabilities,
        verifications=verifications,
        overall=verdict.overall,
        judge_model=verdict.judge_model,
        judged_at=verdict.judged_at,
        error=verdict.error,
    )


def _conversation_to_dto(
    conv: eval_run_entity.EvalRunConversationSnapshot,
) -> eval_dto.EvalRunConversationSnapshotDTO:
    transcript = [
        eval_dto.EvalRunConversationMessageDTO(
            direction=msg.direction,
            content=msg.content,
            timestamp=msg.timestamp,
        )
        for msg in conv.transcript
    ]
    judge_verdict_dto: eval_dto.JudgeVerdictDTO | None = None
    if conv.judge_verdict is not None:
        judge_verdict_dto = _judge_verdict_to_dto(conv.judge_verdict)
    return eval_dto.EvalRunConversationSnapshotDTO(
        persona_id=conv.persona_id,
        combos_satisfied=conv.combos_satisfied,
        status=conv.status,
        elapsed_seconds=conv.elapsed_seconds,
        conversation_id=conv.conversation_id,
        scheduling_request_id=conv.scheduling_request_id,
        final_status=conv.final_status,
        transcript=transcript,
        error=conv.error,
        judge_verdict=judge_verdict_dto,
    )


def _run_to_detail(
    run: eval_run_entity.EvalRun,
    run_doc_id: str,
    conversations: list[eval_run_entity.EvalRunConversationSnapshot],
) -> eval_dto.EvalRunDetailDTO:
    return eval_dto.EvalRunDetailDTO(
        run_doc_id=run_doc_id,
        run_id=run.run_id,
        shape_name=run.shape_name,
        prompt_version_id=run.prompt_version_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        total_personas=run.total_personas,
        ok=run.ok,
        fail=run.fail,
        skipped=run.skipped,
        uncovered_combos=run.uncovered_combos,
        eval_tenant_id=run.eval_tenant_id,
        conversations=[_conversation_to_dto(c) for c in conversations],
    )

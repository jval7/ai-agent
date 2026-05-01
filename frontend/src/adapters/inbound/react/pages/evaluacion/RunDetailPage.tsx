import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import type * as evaluationModel from "@domain/models/evaluation";

const OVERALL_BADGE: Record<
  evaluationModel.EvalJudgeVerdict["overall"],
  { label: string; className: string }
> = {
  all_verified: { label: "all_verified", className: "bg-green-100 text-green-700" },
  partial: { label: "partial", className: "bg-amber-100 text-amber-700" },
  none: { label: "none", className: "bg-red-100 text-red-700" }
};

function CapabilityChip(props: {
  verification: evaluationModel.EvalCapabilityVerification;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { verification, expanded, onToggle } = props;
  const chipClass = verification.verified
    ? "bg-green-100 text-green-800 border-green-200"
    : "bg-red-100 text-red-800 border-red-200";
  const icon = verification.verified ? "✓" : "✗";
  const hasDetail = verification.evidence !== null || verification.reasoning !== null;

  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50">
      <button
        className={`flex w-full items-center gap-2 rounded-lg border px-3 py-1.5 text-left text-xs font-semibold ${chipClass}`}
        disabled={!hasDetail}
        onClick={onToggle}
        type="button"
      >
        <span>{icon}</span>
        <span>{verification.capability}</span>
        {hasDetail ? <span className="ml-auto opacity-60">{expanded ? "▲" : "▼"}</span> : null}
      </button>

      {expanded && hasDetail ? (
        <div className="px-3 pb-3 pt-2 text-xs text-slate-600">
          {verification.evidence !== null ? (
            <p className="mb-1 italic text-slate-700">&ldquo;{verification.evidence}&rdquo;</p>
          ) : null}
          {verification.reasoning !== null ? (
            <p className="text-slate-500">{verification.reasoning}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function JudgeVerdictSection(props: { verdict: evaluationModel.EvalJudgeVerdict | null }) {
  const { verdict } = props;
  const [expandedCaps, setExpandedCaps] = reactModule.useState<Set<string>>(new Set());

  if (verdict === null) {
    return <p className="text-xs italic text-slate-400">Sin verificación del juez.</p>;
  }

  const verifiedCount = verdict.verifications.filter((v) => v.verified).length;
  const total = verdict.verifications.length;
  const badge = OVERALL_BADGE[verdict.overall];

  function toggleCap(cap: string): void {
    setExpandedCaps((prev) => {
      const next = new Set(prev);
      if (next.has(cap)) {
        next.delete(cap);
      } else {
        next.add(cap);
      }
      return next;
    });
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Verificación del juez
        </p>
        <span
          className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${badge.className}`}
        >
          {badge.label}
        </span>
        <span className="text-xs text-slate-500">
          {verifiedCount} de {total} capabilities verificadas
        </span>
      </div>

      {verdict.error !== null ? (
        <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          El juez falló: {verdict.error}
        </div>
      ) : null}

      {verdict.verifications.length === 0 ? (
        <p className="text-xs text-slate-400">Sin verifications disponibles.</p>
      ) : (
        <div className="space-y-1.5">
          {verdict.verifications.map((v) => (
            <CapabilityChip
              expanded={expandedCaps.has(v.capability)}
              key={v.capability}
              onToggle={() => {
                toggleCap(v.capability);
              }}
              verification={v}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function formatDateShort(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function TranscriptBubble(props: { message: evaluationModel.EvalRunConversationMessage }) {
  const isInbound = props.message.direction === "INBOUND";
  return (
    <div
      className={[
        "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm",
        isInbound ? "mr-auto bg-slate-100 text-slate-800" : "ml-auto bg-brand-teal text-white"
      ].join(" ")}
    >
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide opacity-70">
        {isInbound ? "Paciente" : "Agente"}
      </p>
      <p className="whitespace-pre-wrap break-words">{props.message.content}</p>
      <p className="mt-2 text-[11px] opacity-70">
        {new Date(props.message.timestamp).toLocaleTimeString("es-CO", {
          hour: "2-digit",
          minute: "2-digit"
        })}
      </p>
    </div>
  );
}

function ConversationCard(props: { conv: evaluationModel.EvalRunConversationSnapshot }) {
  const [expanded, setExpanded] = reactModule.useState(false);
  const { conv } = props;

  const statusClass: Record<"ok" | "fail" | "skipped", string> = {
    ok: "bg-green-100 text-green-700",
    fail: "bg-red-100 text-red-700",
    skipped: "bg-amber-100 text-amber-700"
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <button
        className="flex w-full items-start justify-between gap-4 px-4 py-3 text-left"
        onClick={() => {
          setExpanded((v) => !v);
        }}
        type="button"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-mono text-xs font-semibold text-slate-700">{conv.personaId}</p>
            <span
              className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${statusClass[conv.status]}`}
            >
              {conv.status}
            </span>
            {conv.elapsedSeconds !== null ? (
              <span className="text-xs text-slate-400">{conv.elapsedSeconds.toFixed(1)}s</span>
            ) : null}
          </div>

          <div className="mt-1 flex flex-wrap gap-1">
            {conv.combosSatisfied.map((combo, ci) => (
              <span
                className="inline-block rounded-full bg-brand-teal/10 px-2 py-0.5 text-xs text-brand-teal"
                key={ci}
              >
                {combo.join(" + ")}
              </span>
            ))}
          </div>

          {conv.finalStatus !== null ? (
            <p className="mt-1 text-xs text-slate-500">Estado final: {conv.finalStatus}</p>
          ) : null}

          {conv.error !== null ? <p className="mt-1 text-xs text-red-600">{conv.error}</p> : null}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {conv.conversationId !== null ? (
            <reactRouterDomModule.Link
              className="text-xs font-semibold text-brand-teal hover:underline"
              onClick={(e) => {
                e.stopPropagation();
              }}
              to={`/inbox`}
            >
              Inbox
            </reactRouterDomModule.Link>
          ) : null}
          <span className="text-xs text-slate-400">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {expanded ? (
        <div className="space-y-4 border-t border-slate-100 px-4 pb-4 pt-3">
          <JudgeVerdictSection verdict={conv.judgeVerdict} />
          {conv.transcript.length === 0 ? (
            <p className="text-xs text-slate-400">Sin mensajes en el transcript.</p>
          ) : (
            conv.transcript.map((msg, i) => <TranscriptBubble key={i} message={msg} />)
          )}
        </div>
      ) : null}
    </div>
  );
}

export function RunDetailPage() {
  const { runDocId } = reactRouterDomModule.useParams<{ runDocId: string }>();
  const navigate = reactRouterDomModule.useNavigate();
  const appContainer = appContainerContextModule.useAppContainer();

  const runQuery = reactQueryModule.useQuery({
    queryKey: ["eval-run", runDocId],
    queryFn: () => {
      if (runDocId === undefined) {
        throw new Error("runDocId es requerido");
      }
      return appContainer.evaluationUseCase.getRun(runDocId);
    },
    enabled: runDocId !== undefined,
    staleTime: Infinity,
    retry: (failureCount, error: unknown) => {
      if (
        error !== null &&
        typeof error === "object" &&
        "statusCode" in error &&
        (error as { statusCode: number }).statusCode === 404
      ) {
        return false;
      }
      return failureCount < 2;
    }
  });

  return (
    <appShellModule.AppShell>
      <div className="flex h-full flex-col overflow-auto p-4 md:p-6">
        <div className="mb-4 flex items-center gap-2">
          <button
            className="text-xs font-semibold text-brand-teal hover:underline"
            onClick={() => {
              navigate("/evaluacion");
            }}
            type="button"
          >
            ← Evaluación
          </button>
          <span className="text-xs text-slate-400">/</span>
          <span className="text-xs text-slate-500">Detalle de corrida</span>
        </div>

        {runQuery.isLoading ? <p className="text-sm text-slate-500">Cargando detalle...</p> : null}

        {runQuery.isError ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3">
            <p className="text-sm text-red-700">
              No se pudo cargar el detalle de la corrida. Verificá que el ID exista.
            </p>
            <button
              className="mt-2 text-xs font-semibold text-red-700 underline"
              onClick={() => {
                void runQuery.refetch();
              }}
              type="button"
            >
              Reintentar
            </button>
          </div>
        ) : null}

        {runQuery.data !== undefined ? (
          <div className="space-y-4">
            {/* Header card */}
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Shape
                  </p>
                  <p className="mt-1 font-mono text-sm font-semibold text-slate-800">
                    {runQuery.data.shapeName}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Run ID
                  </p>
                  <p className="mt-1 font-mono text-xs text-slate-600">{runQuery.data.runId}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Inicio
                  </p>
                  <p className="mt-1 text-xs text-slate-600">
                    {formatDateShort(runQuery.data.startedAt)}
                  </p>
                </div>
                {runQuery.data.finishedAt !== null ? (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Fin
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {formatDateShort(runQuery.data.finishedAt)}
                    </p>
                  </div>
                ) : null}
              </div>

              <div className="mt-4 flex gap-6">
                <div className="text-center">
                  <p className="text-2xl font-bold text-slate-800">{runQuery.data.totalPersonas}</p>
                  <p className="text-xs text-slate-500">Total</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-600">{runQuery.data.ok}</p>
                  <p className="text-xs text-slate-500">OK</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-red-600">{runQuery.data.fail}</p>
                  <p className="text-xs text-slate-500">Fail</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-amber-600">{runQuery.data.skipped}</p>
                  <p className="text-xs text-slate-500">Skip</p>
                </div>
              </div>
            </div>

            {/* Conversations */}
            <div>
              <p className="mb-3 text-sm font-semibold text-slate-700">
                Conversaciones ({runQuery.data.conversations.length})
              </p>
              {runQuery.data.conversations.length === 0 ? (
                <p className="text-sm text-slate-500">No hay conversaciones en esta corrida.</p>
              ) : (
                <div className="space-y-3">
                  {runQuery.data.conversations.map((conv) => (
                    <ConversationCard conv={conv} key={conv.personaId} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </appShellModule.AppShell>
  );
}

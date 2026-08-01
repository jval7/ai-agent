import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as evaluationModel from "@domain/models/evaluation";

// ---------------------------------------------------------------------------
// Delete banner
// ---------------------------------------------------------------------------

interface DeleteBanner {
  type: "success" | "error";
  message: string;
}

function DeleteResultBanner(props: { banner: DeleteBanner; onClose: () => void }) {
  const { banner, onClose } = props;
  const isSuccess = banner.type === "success";
  return (
    <div
      className={[
        "mb-3 flex items-center justify-between rounded-lg border px-4 py-2.5 text-sm",
        isSuccess
          ? "border-green-200 bg-green-50 text-green-800"
          : "border-red-200 bg-red-50 text-red-800"
      ].join(" ")}
    >
      <span>{banner.message}</span>
      <button className="ml-4 text-xs font-semibold underline" onClick={onClose} type="button">
        Cerrar
      </button>
    </div>
  );
}

const runsQueryKey = ["eval-runs"] as const;
const promptVersionsQueryKey = ["eval-prompt-versions"] as const;

function formatDateShort(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

// ---------------------------------------------------------------------------
// Effective status helper (mirrors RunDetailPage)
// ---------------------------------------------------------------------------

type EffectiveStatus = "ok" | "partial" | "fail" | "skipped";

function getEffectiveStatus(conv: evaluationModel.EvalRunConversationSnapshot): EffectiveStatus {
  if (conv.status === "fail") return "fail";
  if (conv.status === "skipped") return "skipped";
  const overall = conv.judgeVerdict?.overall;
  if (overall === "partial" || overall === "none") return "partial";
  return "ok";
}

// ---------------------------------------------------------------------------
// Run group types
// ---------------------------------------------------------------------------

type GroupStatus = "ok" | "fail" | "skipped" | "mixed";

interface RunGroup {
  runId: string;
  shapes: evaluationModel.EvalRunListItem[];
  totalOk: number;
  totalFail: number;
  totalPersonas: number;
  startedAt: string;
  finishedAt: string | null;
  status: GroupStatus;
}

function computeGroupStatus(shapes: evaluationModel.EvalRunListItem[]): GroupStatus {
  const allSkipped = shapes.every((s) => s.skipped);
  if (allSkipped) return "skipped";

  const hasFail = shapes.some((s) => s.fail > 0);
  const hasOk = shapes.some((s) => !s.skipped && s.fail === 0);

  if (hasFail && hasOk) return "mixed";
  if (hasFail) return "fail";
  return "ok";
}

function groupRuns(runs: evaluationModel.EvalRunListItem[]): RunGroup[] {
  const map = new Map<string, evaluationModel.EvalRunListItem[]>();

  for (const run of runs) {
    const existing = map.get(run.runId);
    if (existing !== undefined) {
      existing.push(run);
    } else {
      map.set(run.runId, [run]);
    }
  }

  const groups: RunGroup[] = [];

  for (const [runId, shapes] of map.entries()) {
    const startedAt = shapes.reduce(
      (min, s) => (s.startedAt < min ? s.startedAt : min),
      shapes[0]?.startedAt ?? ""
    );

    const finishedAts = shapes.map((s) => s.finishedAt).filter((f): f is string => f !== null);
    const finishedAt =
      finishedAts.length === shapes.length
        ? finishedAts.reduce((max, f) => (f > max ? f : max), finishedAts[0] ?? "")
        : null;

    groups.push({
      runId,
      shapes,
      totalOk: shapes.reduce((acc, s) => acc + s.ok, 0),
      totalFail: shapes.reduce((acc, s) => acc + s.fail, 0),
      totalPersonas: shapes.reduce((acc, s) => acc + s.totalPersonas, 0),
      startedAt,
      finishedAt,
      status: computeGroupStatus(shapes)
    });
  }

  // Sort descending by startedAt
  groups.sort((a, b) => (b.startedAt > a.startedAt ? 1 : -1));

  return groups;
}

// ---------------------------------------------------------------------------
// Status badges
// ---------------------------------------------------------------------------

function GroupStatusBadge(props: {
  status: GroupStatus;
  totalOk: number;
  totalFail: number;
  totalPartial: number;
}) {
  const { status, totalOk, totalFail, totalPartial } = props;

  if (status === "fail") {
    return (
      <span className="inline-block rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
        {totalFail} error{totalFail !== 1 ? "es" : ""}
      </span>
    );
  }
  if (status === "mixed") {
    return (
      <span className="inline-block rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-orange-700">
        {totalOk} OK / {totalFail} FAIL
      </span>
    );
  }
  if (status === "skipped") {
    return (
      <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
        omitido
      </span>
    );
  }
  // ok — may have partials
  if (totalPartial > 0) {
    return (
      <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
        {totalOk} OK / {totalPartial} Partial
      </span>
    );
  }
  return (
    <span className="inline-block rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
      {totalOk} OK
    </span>
  );
}

// ---------------------------------------------------------------------------
// Caps fallidas inline — sub-row para una shape row
// ---------------------------------------------------------------------------

interface FailedCapSummary {
  personaId: string;
  caps: { capability: string; reasoning: string | null }[];
}

function extractFailedCaps(detail: evaluationModel.EvalRunDetail): FailedCapSummary[] {
  const result: FailedCapSummary[] = [];
  for (const conv of detail.conversations) {
    const eff = getEffectiveStatus(conv);
    if (eff !== "partial" && eff !== "fail") continue;
    if (conv.judgeVerdict === null) continue;

    const failedVerifications = conv.judgeVerdict.verifications.filter((v) => !v.verified);
    if (failedVerifications.length === 0) continue;

    result.push({
      personaId: conv.personaId,
      caps: failedVerifications.map((v) => ({
        capability: v.capability,
        reasoning: v.reasoning ?? null
      }))
    });
  }
  return result;
}

function FailedCapsPanel(props: { runDocId: string }) {
  const { runDocId } = props;
  const appContainer = appContainerContextModule.useAppContainer();

  const detailQuery = reactQueryModule.useQuery({
    queryKey: ["eval-run", runDocId],
    queryFn: () => appContainer.evaluationUseCase.getRun(runDocId),
    staleTime: Infinity
  });

  if (detailQuery.isLoading) {
    return (
      <tr>
        <td colSpan={8} className="bg-amber-50 px-8 py-3 text-xs text-slate-500">
          Cargando caps fallidas...
        </td>
      </tr>
    );
  }

  if (detailQuery.isError || detailQuery.data === undefined) {
    return (
      <tr>
        <td colSpan={8} className="bg-amber-50 px-8 py-3 text-xs text-red-600">
          No se pudo cargar el detalle.
        </td>
      </tr>
    );
  }

  const failed = extractFailedCaps(detailQuery.data);

  if (failed.length === 0) {
    return (
      <tr>
        <td colSpan={8} className="bg-amber-50 px-8 py-3 text-xs text-slate-500 italic">
          Sin caps fallidas.
        </td>
      </tr>
    );
  }

  return (
    <tr>
      <td colSpan={8} className="bg-amber-50 px-8 py-4">
        <div className="space-y-3">
          {failed.map((item) => (
            <div key={item.personaId}>
              <p className="mb-1 font-mono text-xs font-semibold text-slate-700">
                {item.personaId}
              </p>
              <div className="space-y-1">
                {item.caps.map((cap) => (
                  <div
                    key={cap.capability}
                    className="rounded-lg border border-red-200 bg-white px-3 py-2"
                  >
                    <p className="text-xs font-semibold text-red-700">{cap.capability}</p>
                    {cap.reasoning !== null ? (
                      <p className="mt-0.5 text-xs text-slate-500 leading-snug">{cap.reasoning}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Shape child row with caps count + inline expand
// ---------------------------------------------------------------------------

function countFailedCapsFromDetail(detail: evaluationModel.EvalRunDetail): number {
  let count = 0;
  for (const conv of detail.conversations) {
    if (conv.judgeVerdict === null) continue;
    count += conv.judgeVerdict.verifications.filter((v) => !v.verified).length;
  }
  return count;
}

function ShapeRow(props: { run: evaluationModel.EvalRunListItem }) {
  const { run } = props;
  const navigate = reactRouterDomModule.useNavigate();
  const appContainer = appContainerContextModule.useAppContainer();
  const [capsExpanded, setCapsExpanded] = reactModule.useState(false);

  // Prefetch detail to get failed caps count — only when group is already
  // expanded (parent renders this component), so we fetch eagerly.
  const detailQuery = reactQueryModule.useQuery({
    queryKey: ["eval-run", run.runDocId],
    queryFn: () => appContainer.evaluationUseCase.getRun(run.runDocId),
    staleTime: Infinity
  });

  const failedCapsCount =
    detailQuery.data !== undefined ? countFailedCapsFromDetail(detailQuery.data) : null;

  function handleRowClick(): void {
    void navigate(`/evaluacion/runs/${run.runDocId}`);
  }

  function handleCapsToggle(e: reactModule.MouseEvent): void {
    e.stopPropagation();
    setCapsExpanded((v) => !v);
  }

  return (
    <>
      <tr
        className="cursor-pointer bg-white hover:bg-slate-50 transition-colors"
        onClick={handleRowClick}
      >
        <td className="w-6 py-2" />
        <td className="py-2 pr-4 font-mono text-xs text-slate-600">
          <span className="ml-2 flex items-center gap-1 text-slate-400">
            <span>└</span>
            <span className="text-slate-700">{run.shapeName}</span>
          </span>
        </td>
        <td className="py-2 pr-4 text-xs text-slate-500">{formatDateShort(run.startedAt)}</td>
        <td className="py-2 pr-4 text-right text-xs text-slate-600">{run.totalPersonas}</td>
        <td className="py-2 pr-4 text-right text-xs font-semibold text-green-700">{run.ok}</td>
        <td className="py-2 pr-4 text-right text-xs font-semibold text-red-700">{run.fail}</td>
        {/* Caps fallidas column */}
        <td className="py-2 pr-4 text-xs" onClick={handleCapsToggle}>
          {detailQuery.isLoading ? (
            <span className="text-slate-400">...</span>
          ) : failedCapsCount !== null && failedCapsCount > 0 ? (
            <button
              className="flex items-center gap-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700 hover:bg-amber-100 transition-colors"
              type="button"
            >
              <span>
                {failedCapsCount} cap{failedCapsCount !== 1 ? "s" : ""} fallida
                {failedCapsCount !== 1 ? "s" : ""}
              </span>
              <span className="opacity-70">{capsExpanded ? "▲" : "▼"}</span>
            </button>
          ) : (
            <span className="text-slate-300">—</span>
          )}
        </td>
        <td
          className="py-2 pr-4"
          onClick={(e) => {
            e.stopPropagation();
          }}
        >
          <reactRouterDomModule.Link
            className="text-xs font-semibold text-brand-teal hover:underline"
            to={`/evaluacion/runs/${run.runDocId}`}
          >
            Ver →
          </reactRouterDomModule.Link>
        </td>
      </tr>

      {capsExpanded ? <FailedCapsPanel runDocId={run.runDocId} /> : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Grouped row component
// ---------------------------------------------------------------------------

function RunGroupRow(props: {
  group: RunGroup;
  onDelete: (runId: string) => Promise<void>;
  isDeleting: boolean;
}) {
  const { group, onDelete, isDeleting } = props;
  const [expanded, setExpanded] = reactModule.useState(false);
  const queryClient = reactQueryModule.useQueryClient();

  // Read already-cached shape details (populated by ShapeRow queries) to
  // compute the partial count for the group badge. No new fetches here —
  // ShapeRow handles fetching when it mounts.
  const totalPartial = group.shapes.reduce((acc, shape) => {
    const cached = queryClient.getQueryData<evaluationModel.EvalRunDetail>([
      "eval-run",
      shape.runDocId
    ]);
    if (cached === undefined) return acc;
    return acc + cached.conversations.filter((c) => getEffectiveStatus(c) === "partial").length;
  }, 0);

  const groupRowBg =
    group.status === "fail"
      ? "bg-red-50 hover:bg-red-100"
      : group.status === "mixed"
        ? "bg-orange-50 hover:bg-orange-100"
        : "bg-slate-50 hover:bg-slate-100";

  return (
    <>
      {/* Group row */}
      <tr
        className={["cursor-pointer transition-colors", groupRowBg].join(" ")}
        onClick={() => {
          setExpanded((v) => !v);
        }}
      >
        <td className="px-4 py-3" colSpan={2}>
          <div className="flex items-center gap-2">
            <span
              className={["text-slate-400 transition-transform", expanded ? "rotate-180" : ""].join(
                " "
              )}
            >
              <ChevronDownIcon />
            </span>
            <span className="font-mono text-xs font-semibold text-slate-800">{group.runId}</span>
            <span className="text-xs text-slate-500">
              — {group.shapes.length} shape{group.shapes.length !== 1 ? "s" : ""}
            </span>
          </div>
        </td>
        <td className="px-4 py-3 text-xs text-slate-600">{formatDateShort(group.startedAt)}</td>
        <td className="px-4 py-3 text-right text-xs text-slate-600">{group.totalPersonas}</td>
        <td className="px-4 py-3 text-right text-xs font-semibold text-green-700">
          {group.totalOk}
        </td>
        <td className="px-4 py-3 text-right text-xs font-semibold text-red-700">
          {group.totalFail}
        </td>
        <td className="px-4 py-3">
          <GroupStatusBadge
            status={group.status}
            totalFail={group.totalFail}
            totalOk={group.totalOk}
            totalPartial={totalPartial}
          />
        </td>
        <td
          className="px-4 py-3"
          onClick={(e) => {
            e.stopPropagation();
          }}
        >
          <button
            className="rounded-md border border-red-200 bg-white px-2.5 py-1 text-xs font-semibold text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isDeleting}
            onClick={(e) => {
              e.stopPropagation();
              void onDelete(group.runId);
            }}
            type="button"
          >
            {isDeleting ? "Borrando..." : "Borrar"}
          </button>
        </td>
      </tr>

      {/* Child shape rows */}
      {expanded ? group.shapes.map((run) => <ShapeRow key={run.runDocId} run={run} />) : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Flat row (used when shape filter is active)
// ---------------------------------------------------------------------------

function FlatRunRow(props: { run: evaluationModel.EvalRunListItem }) {
  const { run } = props;
  const navigate = reactRouterDomModule.useNavigate();

  return (
    <tr
      className="cursor-pointer hover:bg-slate-50 transition-colors"
      onClick={() => {
        void navigate(`/evaluacion/runs/${run.runDocId}`);
      }}
    >
      <td className="px-4 py-3 font-mono text-xs text-slate-700" colSpan={2}>
        {run.shapeName}
      </td>
      <td className="px-4 py-3 text-xs text-slate-600">{formatDateShort(run.startedAt)}</td>
      <td className="px-4 py-3 text-right text-xs text-slate-600">{run.totalPersonas}</td>
      <td className="px-4 py-3 text-right text-xs font-semibold text-green-700">{run.ok}</td>
      <td className="px-4 py-3 text-right text-xs font-semibold text-red-700">{run.fail}</td>
      <td className="px-4 py-3" colSpan={2}>
        <reactRouterDomModule.Link
          className="text-xs font-semibold text-brand-teal hover:underline"
          onClick={(e) => {
            e.stopPropagation();
          }}
          to={`/evaluacion/runs/${run.runDocId}`}
        >
          Ver →
        </reactRouterDomModule.Link>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// ChevronDownIcon
// ---------------------------------------------------------------------------

function ChevronDownIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Main tab
// ---------------------------------------------------------------------------

export function RunsTab() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  const [shapeFilter, setShapeFilter] = reactModule.useState<string>("__all__");
  const [deletingRunId, setDeletingRunId] = reactModule.useState<string | null>(null);
  const [banner, setBanner] = reactModule.useState<DeleteBanner | null>(null);

  async function handleDeleteRun(runId: string): Promise<void> {
    const confirmText = `¿Borrar la corrida ${runId}? Esto borra TODO: tenants efímeros que aún existan, conversaciones, scheduling requests, patients, y los reportes de Firestore. No se puede deshacer.`;
    if (!window.confirm(confirmText)) return;

    setDeletingRunId(runId);
    setBanner(null);
    try {
      const result = await appContainer.evaluationUseCase.deleteRun(runId);
      await queryClient.invalidateQueries({ queryKey: runsQueryKey });
      setBanner({
        type: "success",
        message: `Corrida borrada — ${result.evalRunsDeleted} report(s) / ${result.tenantsDeleted} tenant(s) eliminados`
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error desconocido al borrar la corrida";
      setBanner({ type: "error", message });
    } finally {
      setDeletingRunId(null);
    }
  }

  const runsQuery = reactQueryModule.useQuery({
    queryKey: runsQueryKey,
    queryFn: () => appContainer.evaluationUseCase.listRuns(50),
    staleTime: 30_000,
    refetchOnWindowFocus: true
  });

  const promptVersionsQuery = reactQueryModule.useQuery({
    queryKey: promptVersionsQueryKey,
    queryFn: () => appContainer.evaluationUseCase.listPromptVersions(),
    staleTime: Infinity
  });

  if (runsQuery.isLoading) {
    return <p className="text-sm text-slate-500">Cargando corridas...</p>;
  }

  if (runsQuery.isError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3">
        <p className="text-sm text-red-700">
          No se pudieron cargar las corridas. Intentá de nuevo.
        </p>
        <button
          className="mt-2 text-xs font-semibold text-red-700 underline"
          onClick={() => {
            void runsQuery.refetch();
          }}
          type="button"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const runs = runsQuery.data ?? [];

  const shapeOptions = Array.from(new Set(runs.map((r) => r.shapeName))).sort();

  const filteredRuns: evaluationModel.EvalRunListItem[] =
    shapeFilter === "__all__" ? runs : runs.filter((r) => r.shapeName === shapeFilter);

  const isFiltered = shapeFilter !== "__all__";
  const groups = isFiltered ? [] : groupRuns(filteredRuns);

  const activeVersion = promptVersionsQuery.data?.find((v) => v.active);
  const activeVersionLabel = activeVersion?.label ?? "Versión actual";

  return (
    <div className="space-y-4">
      {banner !== null ? (
        <DeleteResultBanner
          banner={banner}
          onClose={() => {
            setBanner(null);
          }}
        />
      ) : null}

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-slate-600" htmlFor="shape-filter">
            Shape
          </label>
          <select
            className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700 shadow-sm"
            id="shape-filter"
            onChange={(e) => {
              setShapeFilter(e.target.value);
            }}
            value={shapeFilter}
          >
            <option value="__all__">Todas</option>
            {shapeOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-slate-600" htmlFor="version-filter">
            Versión de prompt
          </label>
          <select
            className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-400 shadow-sm"
            disabled
            id="version-filter"
          >
            <option>{activeVersionLabel}</option>
          </select>
        </div>
      </div>

      {filteredRuns.length === 0 ? (
        <p className="text-sm text-slate-500">
          Aún no hay corridas.{" "}
          <code className="rounded bg-slate-100 px-1 text-xs">
            uv run python scripts/load_test.py --eval-mode
          </code>
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="w-6 px-2 py-3" />
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {isFiltered ? "Shape" : "Corrida / Shape"}
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Inicio
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Total
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                  OK
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Fail
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Estado / Caps
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Detalle
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isFiltered
                ? filteredRuns.map((run) => <FlatRunRow key={run.runDocId} run={run} />)
                : groups.map((group) => (
                    <RunGroupRow
                      group={group}
                      isDeleting={deletingRunId === group.runId}
                      key={group.runId}
                      onDelete={handleDeleteRun}
                    />
                  ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

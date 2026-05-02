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

function GroupStatusBadge(props: { status: GroupStatus; totalOk: number; totalFail: number }) {
  const { status, totalOk, totalFail } = props;

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
  return (
    <span className="inline-block rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
      {totalOk} OK
    </span>
  );
}

function ShapeStatusBadge(props: { run: evaluationModel.EvalRunListItem }) {
  const { run } = props;
  if (run.fail > 0) {
    return (
      <span className="inline-block rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
        FAIL
      </span>
    );
  }
  if (run.skipped) {
    return (
      <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
        omitido
      </span>
    );
  }
  return (
    <span className="inline-block rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
      OK
    </span>
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
      {expanded
        ? group.shapes.map((run) => (
            <tr className="bg-white hover:bg-slate-50" key={run.runDocId}>
              <td className="w-6 py-2" />
              <td className="py-2 pr-4 font-mono text-xs text-slate-600">
                <span className="ml-2 flex items-center gap-1 text-slate-400">
                  <span>└</span>
                  <span className="text-slate-700">{run.shapeName}</span>
                </span>
              </td>
              <td className="py-2 pr-4 text-xs text-slate-500">{formatDateShort(run.startedAt)}</td>
              <td className="py-2 pr-4 text-right text-xs text-slate-600">{run.totalPersonas}</td>
              <td className="py-2 pr-4 text-right text-xs font-semibold text-green-700">
                {run.ok}
              </td>
              <td className="py-2 pr-4 text-right text-xs font-semibold text-red-700">
                {run.fail}
              </td>
              <td className="py-2 pr-4">
                <ShapeStatusBadge run={run} />
              </td>
              <td className="py-2 pr-4">
                <reactRouterDomModule.Link
                  className="text-xs font-semibold text-brand-teal hover:underline"
                  to={`/evaluacion/runs/${run.runDocId}`}
                >
                  Ver →
                </reactRouterDomModule.Link>
              </td>
            </tr>
          ))
        : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Flat row (used when shape filter is active)
// ---------------------------------------------------------------------------

function FlatRunRow(props: { run: evaluationModel.EvalRunListItem }) {
  const { run } = props;
  return (
    <tr className="hover:bg-slate-50" key={run.runDocId}>
      <td className="px-4 py-3 font-mono text-xs text-slate-700" colSpan={2}>
        {run.shapeName}
      </td>
      <td className="px-4 py-3 text-xs text-slate-600">{formatDateShort(run.startedAt)}</td>
      <td className="px-4 py-3 text-right text-xs text-slate-600">{run.totalPersonas}</td>
      <td className="px-4 py-3 text-right text-xs font-semibold text-green-700">{run.ok}</td>
      <td className="px-4 py-3 text-right text-xs font-semibold text-red-700">{run.fail}</td>
      <td className="px-4 py-3">
        <ShapeStatusBadge run={run} />
      </td>
      <td className="px-4 py-3">
        <reactRouterDomModule.Link
          className="text-xs font-semibold text-brand-teal hover:underline"
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

    const adminSecret = window.prompt("Pegá el EVAL_ADMIN_SECRET para confirmar:");
    if (adminSecret === null || adminSecret.trim() === "") return;

    setDeletingRunId(runId);
    setBanner(null);
    try {
      const result = await appContainer.evaluationUseCase.deleteRun(runId, adminSecret.trim());
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
                  Estado
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

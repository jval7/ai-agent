import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as evaluationModel from "@domain/models/evaluation";

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

function RunStatusBadge(props: { ok: number; fail: number; skipped: number }) {
  if (props.fail > 0) {
    return (
      <span className="inline-block rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
        {props.fail} error{props.fail !== 1 ? "es" : ""}
      </span>
    );
  }
  if (props.skipped > 0) {
    return (
      <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
        {props.skipped} omitido{props.skipped !== 1 ? "s" : ""}
      </span>
    );
  }
  return (
    <span className="inline-block rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
      OK
    </span>
  );
}

export function RunsTab() {
  const appContainer = appContainerContextModule.useAppContainer();
  const [shapeFilter, setShapeFilter] = reactModule.useState<string>("__all__");

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

  const activeVersion = promptVersionsQuery.data?.find((v) => v.active);
  const activeVersionLabel = activeVersion?.label ?? "Versión actual";

  return (
    <div className="space-y-4">
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
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Shape
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
              {filteredRuns.map((run) => (
                <tr className="hover:bg-slate-50" key={run.runDocId}>
                  <td className="px-4 py-3 font-mono text-xs text-slate-700">{run.shapeName}</td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {formatDateShort(run.startedAt)}
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-slate-600">
                    {run.totalPersonas}
                  </td>
                  <td className="px-4 py-3 text-right text-xs font-semibold text-green-700">
                    {run.ok}
                  </td>
                  <td className="px-4 py-3 text-right text-xs font-semibold text-red-700">
                    {run.fail}
                  </td>
                  <td className="px-4 py-3">
                    <RunStatusBadge fail={run.fail} ok={run.ok} skipped={run.skipped} />
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
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

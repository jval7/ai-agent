import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as evaluationModel from "@domain/models/evaluation";

const shapesQueryKey = ["eval-shapes"] as const;

function ShapeRow(props: { shape: evaluationModel.EvalShape }) {
  const [expanded, setExpanded] = reactModule.useState(false);

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
          <p className="text-sm font-semibold text-slate-800">{props.shape.name}</p>
          <p className="mt-0.5 text-xs text-slate-500">{props.shape.description}</p>
          <div className="mt-2 flex flex-wrap gap-1">
            {props.shape.requiredCombos.map((combo, ci) => (
              <span
                className="inline-block rounded-full bg-brand-teal/10 px-2 py-0.5 text-xs text-brand-teal"
                key={ci}
              >
                {combo.join(" + ")}
              </span>
            ))}
            {props.shape.requiredCombos.length === 0 ? (
              <span className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                sin combos requeridos
              </span>
            ) : null}
          </div>
        </div>
        <span className="shrink-0 text-xs text-slate-400">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded ? (
        <div className="border-t border-slate-100 px-4 pb-4 pt-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            System prompt renderizado
          </p>
          <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">
            {props.shape.renderedSystemPrompt}
          </pre>
        </div>
      ) : null}
    </div>
  );
}

export function ShapesTab() {
  const appContainer = appContainerContextModule.useAppContainer();

  const shapesQuery = reactQueryModule.useQuery({
    queryKey: shapesQueryKey,
    queryFn: () => appContainer.evaluationUseCase.listShapes(),
    staleTime: Infinity
  });

  if (shapesQuery.isLoading) {
    return <p className="text-sm text-slate-500">Cargando shapes...</p>;
  }

  if (shapesQuery.isError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3">
        <p className="text-sm text-red-700">No se pudieron cargar los shapes. Intentá de nuevo.</p>
        <button
          className="mt-2 text-xs font-semibold text-red-700 underline"
          onClick={() => {
            void shapesQuery.refetch();
          }}
          type="button"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const shapes = shapesQuery.data ?? [];

  if (shapes.length === 0) {
    return <p className="text-sm text-slate-500">No hay shapes registradas.</p>;
  }

  return (
    <div className="space-y-3">
      {shapes.map((shape) => (
        <ShapeRow key={shape.name} shape={shape} />
      ))}
    </div>
  );
}

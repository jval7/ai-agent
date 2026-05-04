import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as evaluationModel from "@domain/models/evaluation";

const capabilitiesQueryKey = ["eval-capabilities"] as const;

function categoryLabel(category: evaluationModel.EvalCapabilityCategory): string {
  if (category === "location") return "Location";
  if (category === "cohort") return "Cohort";
  return "Behavior";
}

const categoryOrder: evaluationModel.EvalCapabilityCategory[] = ["location", "cohort", "behavior"];

const operationalKeywords = [
  "EL RUNNER",
  "pre-seed",
  "cascade",
  "borra",
  "elimina",
  "operacional",
  "tenant",
  "efímero"
];

function hasOperationalImpact(text: string): boolean {
  const lower = text.toLowerCase();
  return operationalKeywords.some((kw) => lower.includes(kw.toLowerCase()));
}

function ImplicationsCell(props: { implications: string }) {
  const { implications } = props;
  const isHighlighted = hasOperationalImpact(implications);
  return (
    <span
      className={
        isHighlighted ? "font-medium text-red-700 underline decoration-red-300" : "text-slate-600"
      }
    >
      {implications}
    </span>
  );
}

function CategorySection(props: {
  category: evaluationModel.EvalCapabilityCategory;
  items: evaluationModel.EvalCapabilityDoc[];
}) {
  const { category, items } = props;
  if (items.length === 0) return null;
  return (
    <div>
      <div className="sticky top-0 border-b border-slate-200 bg-slate-100 px-4 py-2">
        <span className="text-xs font-bold uppercase tracking-wide text-slate-600">
          {categoryLabel(category)}
        </span>
        <span className="ml-2 text-xs text-slate-400">
          {items.length} capability{items.length !== 1 ? "s" : ""}
        </span>
      </div>
      <table className="w-full text-sm">
        <tbody className="divide-y divide-slate-100">
          {items.map((cap) => (
            <tr className="hover:bg-slate-50" key={cap.id}>
              <td className="w-56 px-4 py-2.5 align-top">
                <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800">
                  {cap.id}
                </code>
              </td>
              <td className="px-4 py-2.5 align-top text-xs text-slate-700">{cap.description}</td>
              <td className="px-4 py-2.5 align-top text-xs">
                <ImplicationsCell implications={cap.implications} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CapabilitiesTab() {
  const appContainer = appContainerContextModule.useAppContainer();

  const query = reactQueryModule.useQuery({
    queryKey: capabilitiesQueryKey,
    queryFn: () => appContainer.evaluationUseCase.listCapabilities(),
    staleTime: Infinity
  });

  if (query.isLoading) {
    return <p className="text-sm text-slate-500">Cargando capabilities...</p>;
  }

  if (query.isError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3">
        <p className="text-sm text-red-700">
          No se pudieron cargar las capabilities. Intentá de nuevo.
        </p>
        <button
          className="mt-2 text-xs font-semibold text-red-700 underline"
          onClick={() => {
            void query.refetch();
          }}
          type="button"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const capabilities = query.data ?? [];

  const byCategory = new Map<
    evaluationModel.EvalCapabilityCategory,
    evaluationModel.EvalCapabilityDoc[]
  >();
  for (const category of categoryOrder) {
    byCategory.set(category, []);
  }
  for (const cap of capabilities) {
    const bucket = byCategory.get(cap.category);
    if (bucket !== undefined) {
      bucket.push(cap);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        Glossary de las 11 capabilities que el evaluador puede verificar. Las implications en{" "}
        <span className="font-medium text-red-700">rojo</span> indican impacto operacional o
        dependencia del RUNNER.
      </p>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {/* Column headers */}
        <div className="border-b border-slate-200 bg-slate-50">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="w-56 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  ID
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Descripcion
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Implications
                </th>
              </tr>
            </thead>
          </table>
        </div>

        {capabilities.length === 0 ? (
          <p className="px-4 py-4 text-sm text-slate-500">Sin capabilities registradas.</p>
        ) : (
          categoryOrder.map((cat) => (
            <CategorySection category={cat} items={byCategory.get(cat) ?? []} key={cat} />
          ))
        )}
      </div>
    </div>
  );
}

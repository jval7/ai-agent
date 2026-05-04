import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";

const personasQueryKey = ["eval-personas"] as const;

// `profile_group` es string libre (Fix B4). Conocemos los grupos historicos
// y los rotulamos lindo; cualquier grupo nuevo se muestra tal como viene.

function formatProfileGroup(group: string): string {
  // Lookup explícito por if-else para evitar warnings de object-injection del linter.
  if (group === "psicologa") return "Psicología";
  if (group === "ortodoncista") return "Ortodoncia";
  return group;
}

export function PersonasTab() {
  const appContainer = appContainerContextModule.useAppContainer();

  const personasQuery = reactQueryModule.useQuery({
    queryKey: personasQueryKey,
    queryFn: () => appContainer.evaluationUseCase.listPersonas(),
    staleTime: Infinity
  });

  if (personasQuery.isLoading) {
    return <p className="text-sm text-slate-500">Cargando personas...</p>;
  }

  if (personasQuery.isError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3">
        <p className="text-sm text-red-700">
          No se pudieron cargar las personas. Intentá de nuevo.
        </p>
        <button
          className="mt-2 text-xs font-semibold text-red-700 underline"
          onClick={() => {
            void personasQuery.refetch();
          }}
          type="button"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const personas = personasQuery.data ?? [];

  if (personas.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No hay personas registradas. Generá una con{" "}
        <code className="rounded bg-slate-100 px-1 text-xs">/persona-from-combo</code>.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100 bg-slate-50">
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              ID
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              Nombre
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              Perfil
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              Capabilities
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {personas.map((persona) => (
            <tr className="hover:bg-slate-50" key={persona.id}>
              <td className="px-4 py-3 font-mono text-xs text-slate-600">{persona.id}</td>
              <td className="px-4 py-3 text-slate-800">{persona.displayName}</td>
              <td className="px-4 py-3 text-xs text-slate-600">
                {formatProfileGroup(persona.profileGroup)}
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {persona.capabilities.map((cap) => (
                    <span
                      className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                      key={cap}
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

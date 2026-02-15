import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as apiErrorModule from "@shared/http/api_error";

const queryKey = ["system-prompt"] as const;

export function PromptPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const promptQuery = reactQueryModule.useQuery({
    queryKey,
    queryFn: () => appContainer.agentUseCase.getSystemPrompt()
  });

  const [systemPrompt, setSystemPrompt] = reactModule.useState("");

  reactModule.useEffect(() => {
    if (promptQuery.data !== undefined) {
      setSystemPrompt(promptQuery.data.systemPrompt);
    }
  }, [promptQuery.data]);

  const updateMutation = reactQueryModule.useMutation({
    mutationFn: () => appContainer.agentUseCase.updateSystemPrompt(systemPrompt),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey });
    }
  });

  const errorMessage =
    updateMutation.error instanceof apiErrorModule.ApiError
      ? updateMutation.error.message
      : promptQuery.error instanceof apiErrorModule.ApiError
        ? promptQuery.error.message
        : updateMutation.error instanceof TypeError || promptQuery.error instanceof TypeError
          ? "No se pudo conectar con el backend."
          : null;

  return (
    <appShellModule.AppShell>
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold text-brand-ink">System Prompt</h2>
        <p className="mt-1 text-sm text-slate-600">
          Define el comportamiento base del agente por tenant.
        </p>

        <textarea
          className="mt-4 min-h-[220px] w-full rounded-md border border-slate-300 px-3 py-2 text-sm leading-6 focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/30"
          onChange={(event) => {
            setSystemPrompt(event.target.value);
          }}
          value={systemPrompt}
        />

        {errorMessage !== null ? (
          <p className="mt-3 rounded-md bg-red-100 px-3 py-2 text-sm text-red-700">
            {errorMessage}
          </p>
        ) : null}

        <div className="mt-4 flex gap-3">
          <button
            className="rounded-md bg-brand-teal px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={updateMutation.isPending || promptQuery.isLoading}
            onClick={() => {
              updateMutation.mutate();
            }}
            type="button"
          >
            {updateMutation.isPending ? "Guardando..." : "Guardar prompt"}
          </button>
        </div>
      </section>
    </appShellModule.AppShell>
  );
}

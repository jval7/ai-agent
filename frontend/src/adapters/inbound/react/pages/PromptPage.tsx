import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as uiErrorModule from "@shared/http/ui_error";

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

  const errorMessage = uiErrorModule.resolveUiErrorMessage([
    updateMutation.error,
    promptQuery.error
  ]);

  return (
    <appShellModule.AppShell>
      <section className="max-w-4xl rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
        <h2 className="text-xl font-semibold text-brand-ink">System Prompt</h2>
        <p className="mt-1 text-sm text-slate-600">
          Define el comportamiento base del agente por tenant.
        </p>

        <textarea
          className="mt-4 min-h-[350px] w-full rounded-lg border border-border-subtle px-3 py-2 text-sm leading-6 transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
          onChange={(event) => {
            setSystemPrompt(event.target.value);
          }}
          value={systemPrompt}
        />

        {errorMessage !== null ? (
          <errorBannerModule.ErrorBanner className="mt-3" message={errorMessage} />
        ) : null}

        <div className="mt-4 flex gap-3">
          <button
            className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
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

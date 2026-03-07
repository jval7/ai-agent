import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as uiErrorModule from "@shared/http/ui_error";

const promptQueryKey = ["system-prompt"] as const;
const settingsQueryKey = ["agent-settings"] as const;

export function PromptPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const promptQuery = reactQueryModule.useQuery({
    queryKey: promptQueryKey,
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
      await queryClient.invalidateQueries({ queryKey: promptQueryKey });
    }
  });

  const settingsQuery = reactQueryModule.useQuery({
    queryKey: settingsQueryKey,
    queryFn: () => appContainer.agentUseCase.getAgentSettings()
  });

  const [debounceDelay, setDebounceDelay] = reactModule.useState(0);

  reactModule.useEffect(() => {
    if (settingsQuery.data !== undefined) {
      setDebounceDelay(settingsQuery.data.messageDebounceDelaySeconds);
    }
  }, [settingsQuery.data]);

  const settingsMutation = reactQueryModule.useMutation({
    mutationFn: () => appContainer.agentUseCase.updateAgentSettings(debounceDelay),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: settingsQueryKey });
    }
  });

  const promptErrorMessage = uiErrorModule.resolveUiErrorMessage([
    updateMutation.error,
    promptQuery.error
  ]);

  const settingsErrorMessage = uiErrorModule.resolveUiErrorMessage([
    settingsMutation.error,
    settingsQuery.error
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

        {promptErrorMessage !== null ? (
          <errorBannerModule.ErrorBanner className="mt-3" message={promptErrorMessage} />
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

      <section className="mt-6 max-w-4xl rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
        <h2 className="text-xl font-semibold text-brand-ink">Configuraciones</h2>
        <p className="mt-1 text-sm text-slate-600">Ajustes de comportamiento del agente.</p>

        <div className="mt-4">
          <label className="block text-sm font-medium text-slate-700" htmlFor="debounce-delay">
            Delay de respuesta (segundos)
          </label>
          <p className="mt-0.5 text-xs text-slate-500">
            Tiempo de espera despues de procesar un mensaje antes de responder. Permite capturar
            mensajes adicionales enviados en rafaga. 0 = sin espera.
          </p>
          <input
            className="mt-2 w-24 rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
            id="debounce-delay"
            max={30}
            min={0}
            onChange={(event) => {
              setDebounceDelay(Number(event.target.value));
            }}
            step={1}
            type="number"
            value={debounceDelay}
          />
        </div>

        {settingsErrorMessage !== null ? (
          <errorBannerModule.ErrorBanner className="mt-3" message={settingsErrorMessage} />
        ) : null}

        <div className="mt-4 flex gap-3">
          <button
            className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
            disabled={settingsMutation.isPending || settingsQuery.isLoading}
            onClick={() => {
              settingsMutation.mutate();
            }}
            type="button"
          >
            {settingsMutation.isPending ? "Guardando..." : "Guardar configuracion"}
          </button>
        </div>
      </section>
    </appShellModule.AppShell>
  );
}

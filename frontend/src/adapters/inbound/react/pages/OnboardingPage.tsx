import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import * as uiErrorModule from "@shared/http/ui_error";

const queryKey = ["whatsapp-connection"] as const;

export function OnboardingPage() {
  const appContainer = appContainerContextModule.useAppContainer();

  const connectionQuery = reactQueryModule.useQuery({
    queryKey,
    queryFn: () => appContainer.onboardingUseCase.getConnectionStatus()
  });

  const queryClient = reactQueryModule.useQueryClient();
  const sessionMutation = reactQueryModule.useMutation({
    mutationFn: () => appContainer.onboardingUseCase.createEmbeddedSignupSession(),
    onSuccess: (session) => {
      window.location.assign(session.connectUrl);
    }
  });

  let statusElement: JSX.Element = (
    <statusBadgeModule.StatusBadge label="cargando" tone="neutral" />
  );

  if (connectionQuery.data !== undefined) {
    const status = connectionQuery.data.status;
    if (status === "CONNECTED") {
      statusElement = <statusBadgeModule.StatusBadge label="CONNECTED" tone="success" />;
    } else if (status === "PENDING") {
      statusElement = <statusBadgeModule.StatusBadge label="PENDING" tone="warning" />;
    } else {
      statusElement = <statusBadgeModule.StatusBadge label="DISCONNECTED" tone="danger" />;
    }
  }

  const errorMessage = uiErrorModule.resolveUiErrorMessage([
    sessionMutation.error,
    connectionQuery.error
  ]);

  return (
    <appShellModule.AppShell>
      <section className="grid gap-6 md:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-brand-ink">Estado de conexión de WhatsApp</h2>
          <p className="mt-1 text-sm text-slate-600">
            Conecta la línea de negocio para empezar a responder mensajes.
          </p>

          <div className="mt-4 flex items-center gap-2">
            <span className="text-sm font-medium text-slate-700">Estado actual:</span>
            {statusElement}
          </div>

          {connectionQuery.data !== undefined ? (
            <div className="mt-4 space-y-2 text-sm text-slate-700">
              <p>
                <strong>Tenant:</strong> {connectionQuery.data.tenantId}
              </p>
              <p>
                <strong>Phone Number ID:</strong> {connectionQuery.data.phoneNumberId ?? "-"}
              </p>
              <p>
                <strong>Business Account ID:</strong>{" "}
                {connectionQuery.data.businessAccountId ?? "-"}
              </p>
            </div>
          ) : null}

          {errorMessage !== null ? (
            <errorBannerModule.ErrorBanner className="mt-4" message={errorMessage} />
          ) : null}

          <div className="mt-6 flex gap-3">
            <button
              className="rounded-md bg-brand-teal px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={sessionMutation.isPending}
              onClick={() => {
                sessionMutation.mutate();
              }}
              type="button"
            >
              {sessionMutation.isPending ? "Abriendo Meta..." : "Conectar con Meta"}
            </button>

            <button
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
              onClick={() => {
                void queryClient.invalidateQueries({ queryKey });
              }}
              type="button"
            >
              Refrescar estado
            </button>
          </div>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-brand-ink">Flujo rápido</h3>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-700">
            <li>Haz clic en “Conectar con Meta”.</li>
            <li>Acepta permisos en Meta.</li>
            <li>Vuelve a esta vista y refresca estado.</li>
            <li>Cuando quede en CONNECTED, continúa a Inbox.</li>
          </ol>
        </article>
      </section>
    </appShellModule.AppShell>
  );
}

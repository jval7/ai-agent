import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import * as uiErrorModule from "@shared/http/ui_error";
import * as dateUtilsModule from "@shared/utils/date";

const whatsappConnectionQueryKey = ["whatsapp-connection"] as const;
const googleCalendarConnectionQueryKey = ["google-calendar-connection"] as const;
const onboardingStatusQueryKey = ["onboarding-status"] as const;

function buildConnectionStatusBadge(status: string | undefined): JSX.Element {
  if (status === undefined) {
    return <statusBadgeModule.StatusBadge label="cargando" tone="neutral" />;
  }

  if (status === "CONNECTED") {
    return <statusBadgeModule.StatusBadge label="CONNECTED" tone="success" />;
  }
  if (status === "PENDING") {
    return <statusBadgeModule.StatusBadge label="PENDING" tone="warning" />;
  }
  return <statusBadgeModule.StatusBadge label="DISCONNECTED" tone="danger" />;
}

export function OnboardingPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const navigate = reactRouterDomModule.useNavigate();
  const location = reactRouterDomModule.useLocation();
  const searchParams = reactModule.useMemo(
    () => new URLSearchParams(location.search),
    [location.search]
  );

  const whatsappConnectionQuery = reactQueryModule.useQuery({
    queryKey: whatsappConnectionQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getWhatsappConnectionStatus()
  });

  const googleCalendarConnectionQuery = reactQueryModule.useQuery({
    queryKey: googleCalendarConnectionQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getGoogleCalendarConnectionStatus()
  });

  const onboardingStatusQuery = reactQueryModule.useQuery({
    queryKey: onboardingStatusQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getOnboardingStatus()
  });

  const queryClient = reactQueryModule.useQueryClient();
  const whatsappSessionMutation = reactQueryModule.useMutation({
    mutationFn: () => appContainer.onboardingUseCase.createWhatsappSession(),
    onSuccess: (session) => {
      window.location.assign(session.connectUrl);
    }
  });
  const googleSessionMutation = reactQueryModule.useMutation({
    mutationFn: () => appContainer.onboardingUseCase.createGoogleSession(),
    onSuccess: (session) => {
      window.location.assign(session.connectUrl);
    }
  });

  const statusBadgeElement =
    onboardingStatusQuery.data?.ready === true ? (
      <statusBadgeModule.StatusBadge label="READY" tone="success" />
    ) : (
      <statusBadgeModule.StatusBadge label="PENDIENTE" tone="warning" />
    );

  const errorMessage = uiErrorModule.resolveUiErrorMessage([
    whatsappSessionMutation.error,
    googleSessionMutation.error,
    whatsappConnectionQuery.error,
    googleCalendarConnectionQuery.error,
    onboardingStatusQuery.error
  ]);

  const metaOAuthStatus = searchParams.get("meta_oauth");
  const googleOAuthStatus = searchParams.get("google_oauth");
  const callbackReason = searchParams.get("reason");
  const callbackCode = searchParams.get("status");

  return (
    <appShellModule.AppShell>
      <section className="space-y-4">
        {metaOAuthStatus === "connected" ? (
          <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            WhatsApp conectado correctamente.
          </div>
        ) : null}
        {googleOAuthStatus === "connected" ? (
          <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            Google Calendar conectado correctamente.
          </div>
        ) : null}
        {metaOAuthStatus === "error" || googleOAuthStatus === "error" ? (
          <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            Error en callback OAuth.
            {callbackCode !== null ? ` status=${callbackCode}.` : ""}
            {callbackReason !== null ? ` ${callbackReason}` : ""}
          </div>
        ) : null}
      </section>

      <section className="mt-4 grid max-w-5xl gap-6 md:grid-cols-2">
        <article className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
          <h2 className="text-xl font-semibold text-brand-ink">Estado de WhatsApp</h2>
          <p className="mt-1 text-sm text-slate-600">
            Conecta la línea de negocio para recibir y responder chats.
          </p>
          <div className="mt-4 flex items-center gap-2">
            <span className="text-sm font-medium text-slate-700">Estado actual:</span>
            {buildConnectionStatusBadge(whatsappConnectionQuery.data?.status)}
          </div>
          {whatsappConnectionQuery.data !== undefined ? (
            <div className="mt-4 space-y-2 text-sm text-slate-700">
              <p>
                <strong>Tenant:</strong> {whatsappConnectionQuery.data.tenantId}
              </p>
              <p>
                <strong>Phone Number ID:</strong>{" "}
                {whatsappConnectionQuery.data.phoneNumberId ?? "-"}
              </p>
              <p>
                <strong>Business Account ID:</strong>{" "}
                {whatsappConnectionQuery.data.businessAccountId ?? "-"}
              </p>
            </div>
          ) : null}

          <div className="mt-6">
            <button
              className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
              disabled={whatsappSessionMutation.isPending}
              onClick={() => {
                whatsappSessionMutation.mutate();
              }}
              type="button"
            >
              {whatsappSessionMutation.isPending ? "Abriendo Meta..." : "Conectar con Meta"}
            </button>
          </div>
        </article>

        <article className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
          <h2 className="text-xl font-semibold text-brand-ink">Estado de Google Calendar</h2>
          <p className="mt-1 text-sm text-slate-600">
            Conecta el calendario principal del profesional para disponibilidad y agenda.
          </p>
          <div className="mt-4 flex items-center gap-2">
            <span className="text-sm font-medium text-slate-700">Estado actual:</span>
            {buildConnectionStatusBadge(googleCalendarConnectionQuery.data?.status)}
          </div>
          {googleCalendarConnectionQuery.data !== undefined ? (
            <div className="mt-4 space-y-2 text-sm text-slate-700">
              <p>
                <strong>Tenant:</strong> {googleCalendarConnectionQuery.data.tenantId}
              </p>
              <p>
                <strong>Calendar ID:</strong> {googleCalendarConnectionQuery.data.calendarId ?? "-"}
              </p>
              <p>
                <strong>Timezone:</strong>{" "}
                {googleCalendarConnectionQuery.data.professionalTimezone ?? "-"}
              </p>
              <p>
                <strong>Connected At:</strong>{" "}
                {googleCalendarConnectionQuery.data.connectedAt !== null
                  ? dateUtilsModule.formatDateTime(googleCalendarConnectionQuery.data.connectedAt)
                  : "-"}
              </p>
            </div>
          ) : null}

          <div className="mt-6">
            <button
              className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
              disabled={googleSessionMutation.isPending}
              onClick={() => {
                googleSessionMutation.mutate();
              }}
              type="button"
            >
              {googleSessionMutation.isPending ? "Abriendo Google..." : "Conectar Google Calendar"}
            </button>
          </div>
        </article>
      </section>

      <section className="mt-6 grid max-w-5xl gap-6 md:grid-cols-2">
        <article className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
          <h3 className="text-lg font-semibold text-brand-ink">Estado general de onboarding</h3>
          <div className="mt-3 flex items-center gap-2">
            <span className="text-sm font-medium text-slate-700">Estado:</span>
            {statusBadgeElement}
          </div>
          <div className="mt-4 space-y-2 text-sm text-slate-700">
            <p>
              WhatsApp conectado:{" "}
              {onboardingStatusQuery.data?.whatsappConnected === true ? "sí" : "no"}
            </p>
            <p>
              Google Calendar conectado:{" "}
              {onboardingStatusQuery.data?.googleCalendarConnected === true ? "sí" : "no"}
            </p>
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
              onClick={() => {
                void queryClient.invalidateQueries({ queryKey: whatsappConnectionQueryKey });
                void queryClient.invalidateQueries({ queryKey: googleCalendarConnectionQueryKey });
                void queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey });
              }}
              type="button"
            >
              Refrescar estado
            </button>
            <button
              className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
              disabled={onboardingStatusQuery.data?.ready !== true}
              onClick={() => {
                void navigate("/inbox");
              }}
              type="button"
            >
              Ir a Inbox
            </button>
          </div>
        </article>

        <article className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
          <h3 className="text-lg font-semibold text-brand-ink">Flujo recomendado</h3>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-700">
            <li>Conecta WhatsApp y Google Calendar.</li>
            <li>Refresca el estado general.</li>
            <li>Cuando quede READY, entra a Inbox y Agenda.</li>
          </ol>
        </article>
      </section>

      {errorMessage !== null ? (
        <errorBannerModule.ErrorBanner className="mt-4" message={errorMessage} />
      ) : null}
    </appShellModule.AppShell>
  );
}

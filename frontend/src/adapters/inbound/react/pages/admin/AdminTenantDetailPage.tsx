import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import { Avatar } from "@adapters/inbound/react/components/Avatar";
import { AgendaView } from "@adapters/inbound/react/pages/views/AgendaView";
import { ClientsView } from "@adapters/inbound/react/pages/views/ClientsView";
import { ConfiguracionesView } from "@adapters/inbound/react/pages/views/ConfiguracionesView";
import { FinanzasView } from "@adapters/inbound/react/pages/views/FinanzasView";
import { InboxView } from "@adapters/inbound/react/pages/views/InboxView";
import { RecordatoriosView } from "@adapters/inbound/react/pages/views/RecordatoriosView";
import * as uiErrorModule from "@shared/http/ui_error";
import * as dateUtilsModule from "@shared/utils/date";

type Tab =
  | "resumen"
  | "pacientes"
  | "conversaciones"
  | "citas"
  | "finanzas"
  | "recordatorios"
  | "configuracion";

const TABS: { id: Tab; label: string }[] = [
  { id: "resumen", label: "Resumen" },
  { id: "pacientes", label: "Pacientes" },
  { id: "conversaciones", label: "Conversaciones" },
  { id: "citas", label: "Citas" },
  { id: "finanzas", label: "Finanzas" },
  { id: "recordatorios", label: "Recordatorios" },
  { id: "configuracion", label: "Configuración" }
];

function isValidTab(value: string | undefined): value is Tab {
  return TABS.some((t) => t.id === value);
}

function formatCop(amount: number): string {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0
  }).format(amount);
}

function ResumenTab({ tenantId }: { tenantId: string }) {
  const appContainer = appContainerContextModule.useAppContainer();
  const summaryQuery = reactQueryModule.useQuery({
    queryKey: ["admin", tenantId, "summary"],
    queryFn: () => appContainer.api.adminGetTenantSummary(tenantId)
  });

  const s = summaryQuery.data;
  if (summaryQuery.isLoading) {
    return <p className="text-sm text-slate-500">Cargando resumen...</p>;
  }
  if (s === undefined) {
    return null;
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[
        { label: "Pacientes", value: s.patientCount },
        { label: "Conversaciones", value: s.conversationCount },
        { label: "Conversaciones hoy", value: s.activeConversationsToday },
        { label: "Citas próximas", value: s.manualAppointmentCountUpcoming },
        { label: "Recordatorios pendientes", value: s.pendingReminderCount },
        { label: "Ingresos mes", value: formatCop(s.totalRevenueCopThisMonth) }
      ].map((item) => (
        <div
          className="rounded-xl border border-border-subtle bg-white p-5 shadow-card"
          key={item.label}
        >
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {item.label}
          </p>
          <p className="mt-1 text-2xl font-bold text-brand-ink">{item.value}</p>
        </div>
      ))}
      {s.lastActivityAt !== null ? (
        <div className="rounded-xl border border-border-subtle bg-white p-5 shadow-card sm:col-span-2 lg:col-span-3">
          <p className="text-xs text-slate-500">
            Última actividad: {dateUtilsModule.formatDateTime(s.lastActivityAt)}
          </p>
        </div>
      ) : null}
    </div>
  );
}

export function AdminTenantDetailPage() {
  const { tenantId, tab } = reactRouterDomModule.useParams<{
    tenantId: string;
    tab?: string;
  }>();
  const navigate = reactRouterDomModule.useNavigate();
  const appContainer = appContainerContextModule.useAppContainer();

  const activeTab: Tab = isValidTab(tab) ? tab : "resumen";

  const summaryQuery = reactQueryModule.useQuery({
    queryKey: ["admin", tenantId, "summary"],
    queryFn: () => appContainer.api.adminGetTenantSummary(tenantId ?? ""),
    enabled: tenantId !== undefined
  });

  const errorMessage = uiErrorModule.resolveUiErrorMessage([summaryQuery.error]);

  if (tenantId === undefined) {
    return <p className="text-sm text-red-500">tenantId no encontrado en la URL.</p>;
  }

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">
        Estás operando como administrador sobre{" "}
        <strong>{summaryQuery.data?.tenantName ?? tenantId}</strong>. Cualquier acción afectará
        producción.
      </div>

      {errorMessage !== null ? <errorBannerModule.ErrorBanner message={errorMessage} /> : null}

      <div className="flex items-center gap-4">
        <reactRouterDomModule.Link className="text-sm text-brand-teal hover:underline" to="/admin">
          ← Volver
        </reactRouterDomModule.Link>
        {summaryQuery.data !== undefined ? (
          <div className="flex items-center gap-3">
            <Avatar name={summaryQuery.data.professionalName} size="lg" />
            <div>
              <p className="font-semibold text-brand-ink">{summaryQuery.data.professionalName}</p>
              <p className="text-xs text-slate-500">{summaryQuery.data.ownerEmail}</p>
            </div>
            <statusBadgeModule.StatusBadge
              label={summaryQuery.data.ownerIsActive ? "Activo" : "Inactivo"}
              tone={summaryQuery.data.ownerIsActive ? "success" : "neutral"}
            />
          </div>
        ) : null}
      </div>

      <nav className="flex gap-1 overflow-x-auto rounded-lg bg-slate-100 p-1">
        {TABS.map((t) => (
          <button
            className={[
              "shrink-0 rounded-md px-3 py-2 text-sm font-semibold transition-colors",
              activeTab === t.id
                ? "bg-white text-brand-ink shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            ].join(" ")}
            key={t.id}
            onClick={() => {
              void navigate(`/admin/tenants/${tenantId}/${t.id}`);
            }}
            type="button"
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div>
        {activeTab === "resumen" ? <ResumenTab tenantId={tenantId} /> : null}
        {activeTab === "pacientes" ? <ClientsView tenantId={tenantId} /> : null}
        {activeTab === "conversaciones" ? <InboxView tenantId={tenantId} /> : null}
        {activeTab === "citas" ? <AgendaView tenantId={tenantId} /> : null}
        {activeTab === "finanzas" ? <FinanzasView tenantId={tenantId} /> : null}
        {activeTab === "recordatorios" ? <RecordatoriosView tenantId={tenantId} /> : null}
        {activeTab === "configuracion" ? <ConfiguracionesView tenantId={tenantId} /> : null}
      </div>
    </section>
  );
}

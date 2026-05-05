import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import { Avatar } from "@adapters/inbound/react/components/Avatar";
import { ClientsView } from "@adapters/inbound/react/pages/views/ClientsView";
import { ConfiguracionesView } from "@adapters/inbound/react/pages/views/ConfiguracionesView";
import { FinanzasView } from "@adapters/inbound/react/pages/views/FinanzasView";
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

function ConversacionesTab({ tenantId }: { tenantId: string }) {
  const appContainer = appContainerContextModule.useAppContainer();
  const [selectedId, setSelectedId] = reactModule.useState<string | null>(null);

  const convsQuery = reactQueryModule.useQuery({
    queryKey: ["admin", tenantId, "conversations"],
    queryFn: () => appContainer.api.adminListConversations(tenantId)
  });

  const messagesQuery = reactQueryModule.useQuery({
    queryKey: ["admin", tenantId, "conversation-messages", selectedId],
    enabled: selectedId !== null,
    queryFn: () => appContainer.api.adminListConversationMessages(tenantId, selectedId ?? "")
  });

  return (
    <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
      <div className="max-h-[60vh] overflow-auto rounded-xl border border-border-subtle bg-white shadow-card">
        {convsQuery.isLoading ? <p className="p-4 text-sm text-slate-500">Cargando...</p> : null}
        {convsQuery.data?.map((conv) => (
          <button
            className={[
              "w-full border-b border-border-subtle p-3 text-left text-sm transition-colors last:border-b-0 hover:bg-slate-50",
              selectedId === conv.conversationId ? "bg-brand-accent-light" : ""
            ].join(" ")}
            key={conv.conversationId}
            onClick={() => setSelectedId(conv.conversationId)}
            type="button"
          >
            <p className="truncate font-medium text-brand-ink">
              {conv.contactName ?? conv.whatsappUserId}
            </p>
            <p className="truncate text-xs text-slate-500">{conv.lastMessagePreview ?? "—"}</p>
            <div className="mt-1">
              <statusBadgeModule.StatusBadge
                label={conv.controlMode}
                tone={conv.controlMode === "AI" ? "success" : "warning"}
              />
            </div>
          </button>
        ))}
      </div>
      <div className="max-h-[60vh] overflow-auto rounded-xl border border-border-subtle bg-white p-4 shadow-card">
        {selectedId === null ? (
          <p className="text-sm text-slate-500">Selecciona una conversación.</p>
        ) : messagesQuery.isLoading ? (
          <p className="text-sm text-slate-500">Cargando mensajes...</p>
        ) : (
          <div className="space-y-3">
            {messagesQuery.data?.map((msg) => {
              const isInbound = msg.direction === "INBOUND";
              return (
                <div
                  className={[
                    "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm",
                    isInbound
                      ? "mr-auto bg-slate-100 text-slate-800"
                      : "ml-auto bg-brand-teal text-white"
                  ].join(" ")}
                  key={msg.messageId}
                >
                  <p className="mb-1 text-[11px] font-semibold uppercase opacity-70">{msg.role}</p>
                  <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                  <p className="mt-1 text-[11px] opacity-70">
                    {dateUtilsModule.formatDateTime(msg.createdAt)}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function CitasTab({ tenantId }: { tenantId: string }) {
  const appContainer = appContainerContextModule.useAppContainer();
  const citasQuery = reactQueryModule.useQuery({
    queryKey: ["admin", tenantId, "manual-appointments"],
    queryFn: () => appContainer.api.adminListManualAppointments(tenantId)
  });

  return (
    <div className="rounded-xl border border-border-subtle bg-white shadow-card">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border-subtle bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3">Paciente</th>
              <th className="px-4 py-3">Inicio</th>
              <th className="px-4 py-3">Estado</th>
              <th className="px-4 py-3">Pago</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {citasQuery.isLoading ? (
              <tr>
                <td className="px-4 py-4 text-slate-500" colSpan={4}>
                  Cargando citas...
                </td>
              </tr>
            ) : null}
            {citasQuery.data?.map((appt) => (
              <tr key={appt.appointmentId}>
                <td className="px-4 py-3">{appt.patientWhatsappUserId}</td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {dateUtilsModule.formatDateTime(appt.startAt)}
                </td>
                <td className="px-4 py-3">
                  <statusBadgeModule.StatusBadge label={appt.status} tone="neutral" />
                </td>
                <td className="px-4 py-3">
                  <statusBadgeModule.StatusBadge
                    label={appt.paymentStatus}
                    tone={appt.paymentStatus === "PAID" ? "success" : "warning"}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
            onClick={() => navigate(`/admin/tenants/${tenantId}/${t.id}`)}
            type="button"
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div>
        {activeTab === "resumen" ? <ResumenTab tenantId={tenantId} /> : null}
        {activeTab === "pacientes" ? <ClientsView tenantId={tenantId} /> : null}
        {activeTab === "conversaciones" ? <ConversacionesTab tenantId={tenantId} /> : null}
        {activeTab === "citas" ? <CitasTab tenantId={tenantId} /> : null}
        {activeTab === "finanzas" ? <FinanzasView tenantId={tenantId} /> : null}
        {activeTab === "recordatorios" ? <RecordatoriosView tenantId={tenantId} /> : null}
        {activeTab === "configuracion" ? <ConfiguracionesView tenantId={tenantId} /> : null}
      </div>
    </section>
  );
}

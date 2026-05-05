import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import { Avatar } from "@adapters/inbound/react/components/Avatar";
import * as uiErrorModule from "@shared/http/ui_error";
import * as dateUtilsModule from "@shared/utils/date";
import type * as patientModel from "@domain/models/patient";
import { NewPatientModal } from "@adapters/inbound/react/components/NewPatientModal";

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

function PacientesTab({ tenantId }: { tenantId: string }) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  const [search, setSearch] = reactModule.useState("");
  const [isNewOpen, setIsNewOpen] = reactModule.useState(false);
  const [selectedId, setSelectedId] = reactModule.useState<string | null>(null);

  const listQuery = reactQueryModule.useQuery({
    queryKey: ["admin", tenantId, "patients", search],
    queryFn: () =>
      appContainer.api.adminListPatients(
        tenantId,
        search.trim() !== "" ? { search: search.trim() } : undefined
      )
  });

  const createMutation = reactQueryModule.useMutation({
    mutationFn: (input: patientModel.CreatePatientInput) =>
      appContainer.api.adminCreatePatient(tenantId, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", tenantId, "patients"] });
    }
  });

  const removeMutation = reactQueryModule.useMutation({
    mutationFn: (whatsappUserId: string) =>
      appContainer.api.adminRemovePatient(tenantId, whatsappUserId),
    onSuccess: async () => {
      setSelectedId(null);
      await queryClient.invalidateQueries({ queryKey: ["admin", tenantId, "patients"] });
    }
  });

  const selected = listQuery.data?.find((p) => p.whatsappUserId === selectedId) ?? null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <input
          className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-teal focus:outline-none"
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar paciente..."
          type="search"
          value={search}
        />
        <button
          className="rounded-lg bg-brand-teal px-3 py-2 text-sm font-semibold text-white hover:bg-brand-teal-hover"
          onClick={() => setIsNewOpen(true)}
          type="button"
        >
          + Nuevo
        </button>
      </div>
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <div className="max-h-[60vh] overflow-auto rounded-xl border border-border-subtle bg-white shadow-card">
          {listQuery.isLoading ? <p className="p-4 text-sm text-slate-500">Cargando...</p> : null}
          {listQuery.data?.map((p) => (
            <button
              className={[
                "w-full border-b border-border-subtle p-3 text-left text-sm transition-colors last:border-b-0 hover:bg-slate-50",
                selectedId === p.whatsappUserId ? "bg-brand-accent-light font-semibold" : ""
              ].join(" ")}
              key={p.whatsappUserId}
              onClick={() => setSelectedId(p.whatsappUserId)}
              type="button"
            >
              <p className="font-medium text-brand-ink">
                {p.firstName} {p.lastName}
              </p>
              <p className="text-xs text-slate-500">{p.whatsappUserId}</p>
            </button>
          ))}
        </div>
        <div className="rounded-xl border border-border-subtle bg-white p-4 shadow-card">
          {selected === null ? (
            <p className="text-sm text-slate-500">Selecciona un paciente para ver detalles.</p>
          ) : (
            <div className="space-y-2 text-sm text-slate-700">
              <p>
                <strong>Nombre:</strong> {selected.firstName} {selected.lastName}
              </p>
              <p>
                <strong>WhatsApp ID:</strong> {selected.whatsappUserId}
              </p>
              <p>
                <strong>Email:</strong> {selected.email}
              </p>
              <p>
                <strong>Edad:</strong> {selected.age}
              </p>
              <p>
                <strong>Ubicación:</strong> {selected.location}
              </p>
              <div className="pt-2">
                <button
                  className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:opacity-60"
                  disabled={removeMutation.isPending}
                  onClick={() => {
                    if (
                      !window.confirm("¿Eliminar este paciente? Esta acción no se puede deshacer.")
                    )
                      return;
                    removeMutation.mutate(selected.whatsappUserId);
                  }}
                  type="button"
                >
                  {removeMutation.isPending ? "Eliminando..." : "Eliminar paciente"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
      <NewPatientModal
        isOpen={isNewOpen}
        isSubmitting={createMutation.isPending}
        onClose={() => setIsNewOpen(false)}
        onCreated={(id) => setSelectedId(id)}
        onSubmit={async (input) => {
          await createMutation.mutateAsync(input);
        }}
      />
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

function RecordatoriosTab({ tenantId }: { tenantId: string }) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  const remindersQuery = reactQueryModule.useQuery({
    queryKey: ["admin", tenantId, "reminders"],
    queryFn: () => appContainer.api.adminListReminders(tenantId)
  });

  const sendNowMutation = reactQueryModule.useMutation({
    mutationFn: (reminderId: string) => appContainer.api.adminSendReminderNow(tenantId, reminderId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", tenantId, "reminders"] });
    }
  });

  return (
    <div className="rounded-xl border border-border-subtle bg-white shadow-card">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border-subtle bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3">Paciente</th>
              <th className="px-4 py-3">Cita</th>
              <th className="px-4 py-3">Programado para</th>
              <th className="px-4 py-3">Estado</th>
              <th className="px-4 py-3">Acción</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {remindersQuery.isLoading ? (
              <tr>
                <td className="px-4 py-4 text-slate-500" colSpan={5}>
                  Cargando recordatorios...
                </td>
              </tr>
            ) : null}
            {remindersQuery.data?.items.map((r) => (
              <tr key={r.reminderId}>
                <td className="px-4 py-3">{r.patientName}</td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {dateUtilsModule.formatDateTime(r.appointmentStartAt)}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  {dateUtilsModule.formatDateTime(r.reminderScheduledFor)}
                </td>
                <td className="px-4 py-3">
                  <statusBadgeModule.StatusBadge
                    label={r.status}
                    tone={
                      r.status === "SENT"
                        ? "success"
                        : r.status === "FAILED"
                          ? "danger"
                          : r.status === "PENDING"
                            ? "warning"
                            : "neutral"
                    }
                  />
                </td>
                <td className="px-4 py-3">
                  {r.status === "PENDING" ? (
                    <button
                      className="rounded-md bg-brand-teal px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-teal-hover disabled:opacity-60"
                      disabled={sendNowMutation.isPending}
                      onClick={() => sendNowMutation.mutate(r.reminderId)}
                      type="button"
                    >
                      Enviar ahora
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ConfiguracionTab({ tenantId }: { tenantId: string }) {
  const appContainer = appContainerContextModule.useAppContainer();
  const promptQuery = reactQueryModule.useQuery({
    queryKey: ["admin", tenantId, "system-prompt"],
    queryFn: () => appContainer.api.adminGetSystemPrompt(tenantId)
  });

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border-subtle bg-white p-5 shadow-card">
        <h3 className="mb-3 text-sm font-semibold text-brand-ink">System Prompt</h3>
        {promptQuery.isLoading ? (
          <p className="text-sm text-slate-500">Cargando...</p>
        ) : (
          <pre className="max-h-60 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700 whitespace-pre-wrap">
            {promptQuery.data?.systemPrompt ?? "Sin prompt configurado."}
          </pre>
        )}
      </div>
    </div>
  );
}

function FinanzasTab({ tenantId }: { tenantId: string }) {
  const appContainer = appContainerContextModule.useAppContainer();
  const appointmentsQuery = reactQueryModule.useQuery({
    queryKey: ["admin", tenantId, "manual-appointments-finanzas"],
    queryFn: () => appContainer.api.adminListManualAppointments(tenantId)
  });

  const paidTotal =
    appointmentsQuery.data
      ?.filter((a) => a.paymentStatus === "PAID")
      .reduce((acc, a) => acc + (a.paymentAmountCop ?? 0), 0) ?? 0;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border-subtle bg-white p-5 shadow-card">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Total cobrado (manual, este mes)
        </p>
        <p className="mt-1 text-2xl font-bold text-brand-ink">
          {new Intl.NumberFormat("es-CO", {
            style: "currency",
            currency: "COP",
            maximumFractionDigits: 0
          }).format(paidTotal)}
        </p>
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
        {activeTab === "pacientes" ? <PacientesTab tenantId={tenantId} /> : null}
        {activeTab === "conversaciones" ? <ConversacionesTab tenantId={tenantId} /> : null}
        {activeTab === "citas" ? <CitasTab tenantId={tenantId} /> : null}
        {activeTab === "finanzas" ? <FinanzasTab tenantId={tenantId} /> : null}
        {activeTab === "recordatorios" ? <RecordatoriosTab tenantId={tenantId} /> : null}
        {activeTab === "configuracion" ? <ConfiguracionTab tenantId={tenantId} /> : null}
      </div>
    </section>
  );
}

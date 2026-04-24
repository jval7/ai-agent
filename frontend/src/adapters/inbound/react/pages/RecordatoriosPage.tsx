import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import * as dateModule from "@shared/utils/date";

const STATUS_FILTERS = [
  { value: undefined, label: "Todos" },
  { value: "PENDING", label: "Pendientes" },
  { value: "SENT", label: "Enviados" },
  { value: "FAILED", label: "Error" },
  { value: "CANCELLED", label: "Cancelados" }
] as const;

type StatusFilterValue = (typeof STATUS_FILTERS)[number]["value"];

function getStatusBadgeProps(status: string): {
  tone: statusBadgeModule.StatusBadgeTone;
  label: string;
} {
  if (status === "PENDING") return { tone: "warning", label: "PENDIENTE" };
  if (status === "SENT") return { tone: "success", label: "ENVIADO" };
  if (status === "FAILED") return { tone: "danger", label: "ERROR" };
  if (status === "CANCELLED") return { tone: "neutral", label: "CANCELADO" };
  return { tone: "neutral", label: status };
}

function getSourceLabel(sourceType: string): string {
  if (sourceType === "SCHEDULING_REQUEST") return "Agendamiento";
  if (sourceType === "MANUAL_APPOINTMENT") return "Cita manual";
  return sourceType;
}

function BellEmptyIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-12 w-12 text-slate-300"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      viewBox="0 0 24 24"
    >
      <path
        d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function RecordatoriosPage() {
  const appContainer = appContainerContextModule.useAppContainer();

  const [statusFilter, setStatusFilter] = reactModule.useState<StatusFilterValue>(undefined);

  const remindersQuery = reactQueryModule.useQuery({
    queryKey: ["reminders", statusFilter],
    queryFn: () => appContainer.reminderUseCase.listReminders(statusFilter)
  });

  const reminders = remindersQuery.data?.items ?? [];

  return (
    <appShellModule.AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-ink">Recordatorios</h1>
        <p className="mt-1 text-sm text-slate-500">
          Recordatorios de cita programados automaticamente.
        </p>
      </div>

      <nav className="mb-4 flex gap-1 border-b border-border-subtle">
        {STATUS_FILTERS.map((filter) => (
          <button
            className={[
              "px-4 py-2.5 text-sm font-medium transition-colors",
              statusFilter === filter.value
                ? "border-b-2 border-brand-teal text-brand-teal"
                : "text-slate-500 hover:text-slate-700"
            ].join(" ")}
            key={filter.label}
            onClick={() => {
              setStatusFilter(filter.value);
            }}
            type="button"
          >
            {filter.label}
          </button>
        ))}
      </nav>

      {remindersQuery.isLoading ? (
        <div className="flex items-center justify-center py-16 text-sm text-slate-500">
          Cargando recordatorios...
        </div>
      ) : reminders.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16">
          <BellEmptyIcon />
          <p className="mt-4 text-sm font-medium text-slate-600">No hay recordatorios</p>
          <p className="mt-1 text-xs text-slate-400">
            Los recordatorios programados apareceran aqui.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border-subtle bg-white shadow-card">
          <table className="min-w-full divide-y divide-border-subtle">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Paciente
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Fecha cita
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Fecha recordatorio
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Plantilla
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Origen
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Estado
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Motivo
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {reminders.map((reminder) => {
                const badgeProps = getStatusBadgeProps(reminder.status);
                return (
                  <tr key={reminder.reminderId} className="transition-colors hover:bg-slate-50">
                    <td className="px-6 py-4 text-sm font-medium text-brand-ink">
                      {reminder.patientName}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      {dateModule.formatDateTime(reminder.appointmentStartAt)}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      {dateModule.formatDateTime(reminder.reminderScheduledFor)}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600">{reminder.templateName}</td>
                    <td className="px-6 py-4 text-sm text-slate-600">
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                        {getSourceLabel(reminder.sourceType)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <statusBadgeModule.StatusBadge
                        label={badgeProps.label}
                        tone={badgeProps.tone}
                      />
                    </td>
                    <td className="max-w-md px-6 py-4 text-sm text-slate-600">
                      {reminder.failureReason !== null && reminder.failureReason !== "" ? (
                        <span className="block break-words" title={reminder.failureReason}>
                          {reminder.failureReason}
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </appShellModule.AppShell>
  );
}

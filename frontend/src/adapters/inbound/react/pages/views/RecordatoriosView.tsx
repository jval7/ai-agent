import * as reactModule from "react";

import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import * as useRemindersQueryModule from "@adapters/inbound/react/hooks/useRemindersQuery";
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

function SendNowIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path
        d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function RecordatoriosView({ tenantId }: { tenantId?: string }) {
  const [statusFilter, setStatusFilter] = reactModule.useState<StatusFilterValue>(undefined);

  const remindersQuery = useRemindersQueryModule.useRemindersQuery(statusFilter, tenantId);
  const sendNowMutation = useRemindersQueryModule.useSendReminderNowMutation(tenantId);

  const handleSendNow = (reminderId: string, patientName: string, isRetry: boolean) => {
    const verb = isRetry ? "Reintentar el recordatorio para" : "Enviar recordatorio a";
    if (!window.confirm(`¿${verb} ${patientName} ahora?`)) {
      return;
    }
    sendNowMutation.mutate(reminderId);
  };

  const reminders = remindersQuery.data?.items ?? [];

  return (
    <>
      {tenantId === undefined ? (
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-brand-ink">Recordatorios</h1>
          <p className="mt-1 text-sm text-slate-500">
            Recordatorios de cita programados automaticamente.
          </p>
        </div>
      ) : null}

      <nav className="mb-4 -mx-3 flex gap-1 overflow-x-auto border-b border-border-subtle px-3 sm:mx-0 sm:px-0">
        {STATUS_FILTERS.map((filter) => (
          <button
            className={[
              "shrink-0 px-3 py-2.5 text-sm font-medium transition-colors sm:px-4",
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
        <>
          <ul className="space-y-3 md:hidden">
            {reminders.map((reminder) => {
              const badgeProps = getStatusBadgeProps(reminder.status);
              const canAct = reminder.status === "PENDING" || reminder.status === "FAILED";
              const isFailed = reminder.status === "FAILED";
              const isSending =
                sendNowMutation.isPending && sendNowMutation.variables === reminder.reminderId;
              return (
                <li
                  className="rounded-2xl border border-border-subtle bg-white p-4 shadow-card"
                  key={reminder.reminderId}
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold text-brand-ink">{reminder.patientName}</p>
                    <statusBadgeModule.StatusBadge
                      label={badgeProps.label}
                      tone={badgeProps.tone}
                    />
                  </div>
                  <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                    <div>
                      <dt className="font-medium uppercase tracking-wide text-slate-400">
                        Fecha cita
                      </dt>
                      <dd className="mt-0.5 text-slate-700">
                        {dateModule.formatDateTime(reminder.appointmentStartAt)}
                      </dd>
                    </div>
                    <div>
                      <dt className="font-medium uppercase tracking-wide text-slate-400">
                        Recordatorio
                      </dt>
                      <dd className="mt-0.5 text-slate-700">
                        {dateModule.formatDateTime(reminder.reminderScheduledFor)}
                      </dd>
                    </div>
                    <div className="col-span-2">
                      <dt className="font-medium uppercase tracking-wide text-slate-400">
                        Plantilla
                      </dt>
                      <dd className="mt-0.5 flex flex-wrap items-center gap-2 text-slate-700">
                        <span>{reminder.templateName}</span>
                        <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                          {getSourceLabel(reminder.sourceType)}
                        </span>
                      </dd>
                    </div>
                    {reminder.failureReason !== null && reminder.failureReason !== "" ? (
                      <div className="col-span-2">
                        <dt className="font-medium uppercase tracking-wide text-slate-400">
                          Motivo
                        </dt>
                        <dd
                          className="mt-0.5 line-clamp-3 break-words text-slate-700"
                          title={reminder.failureReason}
                        >
                          {reminder.failureReason}
                        </dd>
                      </div>
                    ) : null}
                  </dl>
                  {canAct ? (
                    <div className="mt-4 flex justify-end">
                      <button
                        aria-label={
                          isFailed ? "Reintentar recordatorio" : "Enviar recordatorio ahora"
                        }
                        className="inline-flex items-center gap-2 rounded-lg border border-brand-teal px-3 py-1.5 text-xs font-medium text-brand-teal transition-colors hover:bg-brand-teal/10 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={isSending}
                        onClick={() => {
                          handleSendNow(reminder.reminderId, reminder.patientName, isFailed);
                        }}
                        type="button"
                      >
                        <SendNowIcon />
                        <span>{isFailed ? "Reintentar" : "Enviar ahora"}</span>
                      </button>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
          <div className="hidden overflow-hidden rounded-2xl border border-border-subtle bg-white shadow-card md:block">
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
                  <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Acciones
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
                      <td className="max-w-xs px-6 py-4 text-sm text-slate-600">
                        {reminder.failureReason !== null && reminder.failureReason !== "" ? (
                          <span className="line-clamp-2 break-words" title={reminder.failureReason}>
                            {reminder.failureReason}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-right text-sm">
                        {reminder.status === "PENDING" || reminder.status === "FAILED" ? (
                          <button
                            aria-label={
                              reminder.status === "FAILED"
                                ? "Reintentar recordatorio"
                                : "Enviar recordatorio ahora"
                            }
                            className="inline-flex items-center justify-center rounded-lg border border-brand-teal p-2 text-brand-teal transition-colors hover:bg-brand-teal/10 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={
                              sendNowMutation.isPending &&
                              sendNowMutation.variables === reminder.reminderId
                            }
                            onClick={() => {
                              handleSendNow(
                                reminder.reminderId,
                                reminder.patientName,
                                reminder.status === "FAILED"
                              );
                            }}
                            title={reminder.status === "FAILED" ? "Reintentar" : "Enviar ahora"}
                            type="button"
                          >
                            <SendNowIcon />
                          </button>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}

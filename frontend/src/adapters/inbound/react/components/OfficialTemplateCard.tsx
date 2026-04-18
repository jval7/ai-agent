import type * as whatsappTemplateModel from "@domain/models/whatsapp_template";

import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";

function resolveKindLabel(kind: whatsappTemplateModel.OfficialReminderKind): string {
  if (kind === "PAYMENT") {
    return "Recordatorio de pago + cita";
  }
  return "Recordatorio de asistencia";
}

function resolveKindBodyPreview(kind: whatsappTemplateModel.OfficialReminderKind): string {
  if (kind === "PAYMENT") {
    return "Hola {{1}}, te recordamos tu cita agendada para el {{2}}. Aún no hemos recibido tu pago; por favor recuerda pagarlo antes de la cita para confirmarla.";
  }
  return "Hola {{1}}, te recordamos tu cita agendada para el {{2}}. Te esperamos. Responde este mensaje si necesitas reagendar.";
}

function resolveMetaStatusBadgeProps(
  metaStatus: whatsappTemplateModel.OfficialTemplateMetaStatus
): { label: string; tone: statusBadgeModule.StatusBadgeTone } {
  if (metaStatus === "PENDING") {
    return { label: "Pendiente de review", tone: "warning" };
  }
  if (metaStatus === "APPROVED") {
    return { label: "Activa", tone: "success" };
  }
  if (metaStatus === "REJECTED") {
    return { label: "Rechazada", tone: "danger" };
  }
  if (metaStatus === "DISABLED") {
    return { label: "Deshabilitada en Meta", tone: "neutral" };
  }
  return { label: "No activada", tone: "neutral" };
}

function buildMetaStatusBadge(
  metaStatus: whatsappTemplateModel.OfficialTemplateMetaStatus
): JSX.Element {
  const { label, tone } = resolveMetaStatusBadgeProps(metaStatus);
  return <statusBadgeModule.StatusBadge label={label} tone={tone} />;
}

interface OfficialTemplateCardProps {
  kind: whatsappTemplateModel.OfficialReminderKind;
  status: whatsappTemplateModel.OfficialTemplateStatus;
  onActivate: () => void;
  onDeactivate: () => void;
  isMutating: boolean;
}

export function OfficialTemplateCard(props: OfficialTemplateCardProps) {
  const { kind, status, onActivate, onDeactivate, isMutating } = props;
  const canActivate = status.metaStatus === "NOT_CREATED";

  return (
    <div className="rounded-xl border border-border-subtle bg-slate-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-brand-ink">{resolveKindLabel(kind)}</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">
            {resolveKindBodyPreview(kind)}
          </p>
        </div>
        <div className="shrink-0">{buildMetaStatusBadge(status.metaStatus)}</div>
      </div>

      {status.rejectionReason !== null ? (
        <p className="mt-2 text-xs text-red-600">Motivo de rechazo: {status.rejectionReason}</p>
      ) : null}

      <div className="mt-3">
        {canActivate ? (
          <button
            className="rounded-lg bg-brand-teal px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isMutating}
            onClick={onActivate}
            type="button"
          >
            {isMutating ? "Procesando..." : "Activar"}
          </button>
        ) : (
          <button
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isMutating}
            onClick={onDeactivate}
            type="button"
          >
            {isMutating ? "Procesando..." : "Desactivar"}
          </button>
        )}
      </div>
    </div>
  );
}

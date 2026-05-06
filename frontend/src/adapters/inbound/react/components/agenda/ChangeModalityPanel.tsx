import * as luxonModule from "luxon";

import type { BookedAppointment } from "@adapters/inbound/react/hooks/useBookedAppointments";

interface ChangeModalityPanelProps {
  selectedBookedAppointment: BookedAppointment;
  timezone: string;
  isSaving: boolean;
  onConfirm: (payload: {
    source: "BOT" | "MANUAL";
    id: string;
    newModality: "PRESENCIAL" | "VIRTUAL";
  }) => void;
  onCancel: () => void;
  /** Optional wrapper className override — used to distinguish main vs drawer contexts */
  wrapperClassName?: string;
}

function resolveCurrentModality(appointment: BookedAppointment): "PRESENCIAL" | "VIRTUAL" {
  if (appointment.source === "MANUAL" && appointment.manualAppointment !== null) {
    return appointment.manualAppointment.isVirtual ? "VIRTUAL" : "PRESENCIAL";
  }
  return appointment.request?.appointmentModality === "PRESENCIAL" ? "PRESENCIAL" : "VIRTUAL";
}

export function ChangeModalityPanel({
  selectedBookedAppointment,
  timezone,
  isSaving,
  onConfirm,
  onCancel,
  wrapperClassName = "rounded-lg border border-border-subtle p-4 space-y-4"
}: ChangeModalityPanelProps) {
  const currentModality = resolveCurrentModality(selectedBookedAppointment);
  const targetModality: "PRESENCIAL" | "VIRTUAL" =
    currentModality === "PRESENCIAL" ? "VIRTUAL" : "PRESENCIAL";
  const currentLabel = currentModality === "VIRTUAL" ? "virtual" : "presencial";
  const targetLabel = targetModality === "VIRTUAL" ? "virtual" : "presencial";
  const formattedDate = luxonModule.DateTime.fromISO(
    selectedBookedAppointment.startAt.toISO() ?? "",
    { setZone: true }
  )
    .setZone(timezone)
    .setLocale("es")
    .toFormat("EEE dd LLL yyyy");

  const handleConfirm = () => {
    const source = selectedBookedAppointment.source;
    const id =
      source === "BOT"
        ? (selectedBookedAppointment.requestId ?? "")
        : (selectedBookedAppointment.manualAppointmentId ?? "");
    if (id === "") {
      return;
    }
    onConfirm({ source, id, newModality: targetModality });
  };

  return (
    <div className={wrapperClassName}>
      <div>
        <p className="text-sm font-semibold text-brand-ink">Cambiar modalidad</p>
        <p className="text-xs text-slate-500 mt-0.5">
          {`¿Cambiar la cita de ${selectedBookedAppointment.patientDisplayName} del ${formattedDate} de ${currentLabel} a ${targetLabel}?`}
        </p>
        <p className="text-xs text-slate-500 mt-1">
          Se enviará automáticamente un correo al paciente con los nuevos datos del evento.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isSaving}
          onClick={handleConfirm}
          type="button"
        >
          {isSaving ? "Guardando..." : "Confirmar cambio"}
        </button>
        <button
          className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
          onClick={onCancel}
          type="button"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}

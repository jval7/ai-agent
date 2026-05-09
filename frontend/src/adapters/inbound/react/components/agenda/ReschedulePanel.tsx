import * as slotPickerModule from "@adapters/inbound/react/components/SlotPicker";
import type { BookedAppointment } from "@adapters/inbound/react/hooks/useBookedAppointments";
import type * as calendarUtilsModule from "@shared/utils/calendar";

const colombiaTimezone = "America/Bogota";

interface ReschedulePanelProps {
  selectedBookedAppointment: BookedAppointment;
  rescheduleBusyIntervals: calendarUtilsModule.BusyIntervalRange[];
  rescheduleSelectedSlots: { slotId: string; startAt: string; endAt: string; timezone: string }[];
  onSelectedSlotsChange: (
    slots: { slotId: string; startAt: string; endAt: string; timezone: string }[]
  ) => void;
  isLoadingAvailability: boolean;
  onMonthChange: (month: { year: number; month: number }) => void;
  isSaving: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  /** Optional wrapper className override — used to distinguish main vs drawer contexts */
  wrapperClassName?: string;
}

export function ReschedulePanel({
  selectedBookedAppointment,
  rescheduleBusyIntervals,
  rescheduleSelectedSlots,
  onSelectedSlotsChange,
  isLoadingAvailability,
  onMonthChange,
  isSaving,
  onConfirm,
  onCancel,
  wrapperClassName = "rounded-lg border border-border-subtle p-4 space-y-4"
}: ReschedulePanelProps) {
  const requestId =
    selectedBookedAppointment.source === "MANUAL"
      ? (selectedBookedAppointment.manualAppointmentId ?? "reschedule")
      : (selectedBookedAppointment.requestId ?? "reschedule");

  return (
    <div className={wrapperClassName} data-testid="reschedule-slotpicker-panel">
      <div>
        <p className="text-sm font-semibold text-brand-ink">Reprogramar cita</p>
        <p className="text-xs text-slate-500 mt-0.5">Selecciona un nuevo horario disponible.</p>
      </div>
      <slotPickerModule.SlotPicker
        timezone={colombiaTimezone}
        busyIntervals={rescheduleBusyIntervals}
        requestId={requestId}
        selectedSlots={rescheduleSelectedSlots}
        onSelectedSlotsChange={(slots) => onSelectedSlotsChange(slots.slice(-1))}
        isLoadingAvailability={isLoadingAvailability}
        onMonthChange={onMonthChange}
      />
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
          disabled={rescheduleSelectedSlots.length !== 1 || isSaving}
          onClick={onConfirm}
          type="button"
        >
          {isSaving ? "Guardando..." : "Guardar reprogramación"}
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

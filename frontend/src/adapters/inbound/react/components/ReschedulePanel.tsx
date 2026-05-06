import * as slotPickerModule from "@adapters/inbound/react/components/SlotPicker";
import type * as calendarUtilsModule from "@shared/utils/calendar";

import { colombiaTimezone } from "@adapters/inbound/react/hooks/useBookedAppointments";
import type { BookedAppointment } from "@adapters/inbound/react/hooks/useBookedAppointments";
import type { SelectedSlot } from "@adapters/inbound/react/hooks/useReschedule";

interface ReschedulePanelProps {
  selectedBookedAppointment: BookedAppointment;
  rescheduleBusyIntervals: calendarUtilsModule.BusyIntervalRange[];
  rescheduleSelectedSlots: SelectedSlot[];
  isLoadingAvailability: boolean;
  isPending: boolean;
  testId?: string;
  onSelectedSlotsChange: (slots: SelectedSlot[]) => void;
  onMonthChange: (month: { year: number; month: number }) => void;
  onConfirm: (slot: SelectedSlot) => void;
  onCancel: () => void;
}

export function ReschedulePanel({
  selectedBookedAppointment,
  rescheduleBusyIntervals,
  rescheduleSelectedSlots,
  isLoadingAvailability,
  isPending,
  testId,
  onSelectedSlotsChange,
  onMonthChange,
  onConfirm,
  onCancel
}: ReschedulePanelProps) {
  const requestId =
    selectedBookedAppointment.source === "MANUAL"
      ? (selectedBookedAppointment.manualAppointmentId ?? "reschedule")
      : (selectedBookedAppointment.requestId ?? "reschedule");

  return (
    <div className="rounded-lg border border-border-subtle p-4 space-y-4" data-testid={testId}>
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
          disabled={rescheduleSelectedSlots.length !== 1 || isPending}
          onClick={() => {
            const slot = rescheduleSelectedSlots[0];
            if (slot === undefined) {
              return;
            }
            onConfirm(slot);
          }}
          type="button"
        >
          {isPending ? "Guardando..." : "Guardar reprogramación"}
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

import * as slotPickerModule from "@adapters/inbound/react/components/SlotPicker";
import type * as calendarUtilsModule from "@shared/utils/calendar";

interface ReschedulePanelProps {
  timezone: string;
  busyIntervals: calendarUtilsModule.BusyIntervalRange[];
  requestId: string;
  selectedSlots: { slotId: string; startAt: string; endAt: string; timezone: string }[];
  onSelectedSlotsChange: (
    slots: { slotId: string; startAt: string; endAt: string; timezone: string }[]
  ) => void;
  isLoadingAvailability: boolean;
  onMonthChange: (month: { year: number; month: number }) => void;
  isSaving: boolean;
  onSave: () => void;
  onCancel: () => void;
  /** Extra wrapper class for variants (inline panel vs drawer) */
  className?: string;
  /** data-testid for testing */
  testId?: string;
}

export function ReschedulePanel({
  timezone,
  busyIntervals,
  requestId,
  selectedSlots,
  onSelectedSlotsChange,
  isLoadingAvailability,
  onMonthChange,
  isSaving,
  onSave,
  onCancel,
  className = "rounded-lg border border-border-subtle p-4 space-y-4",
  testId
}: ReschedulePanelProps) {
  return (
    <div className={className} data-testid={testId}>
      <div>
        <p className="text-sm font-semibold text-brand-ink">Reprogramar cita</p>
        <p className="text-xs text-slate-500 mt-0.5">Selecciona un nuevo horario disponible.</p>
      </div>
      <slotPickerModule.SlotPicker
        timezone={timezone}
        busyIntervals={busyIntervals}
        requestId={requestId}
        selectedSlots={selectedSlots}
        onSelectedSlotsChange={(slots) => onSelectedSlotsChange(slots.slice(-1))}
        isLoadingAvailability={isLoadingAvailability}
        onMonthChange={onMonthChange}
      />
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
          disabled={selectedSlots.length !== 1 || isSaving}
          onClick={onSave}
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

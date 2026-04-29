import * as reactModule from "react";
import * as luxonModule from "luxon";
import * as calendarUtilsModule from "@shared/utils/calendar";

interface SlotPickerProps {
  timezone: string;
  busyIntervals: calendarUtilsModule.BusyIntervalRange[];
  requestId: string;
  selectedSlots: { slotId: string; startAt: string; endAt: string; timezone: string }[];
  onSelectedSlotsChange: (
    slots: { slotId: string; startAt: string; endAt: string; timezone: string }[]
  ) => void;
  isLoadingAvailability: boolean;
  onMonthChange?: (month: { year: number; month: number }) => void;
}

const DURATION_PRESETS_MINUTES = [15, 30, 45, 60, 90, 120];
const DEFAULT_DURATION_MINUTES = 60;

export function SlotPicker(props: SlotPickerProps) {
  const now = luxonModule.DateTime.now().setZone(props.timezone);

  const [visibleMonth, setVisibleMonth] = reactModule.useState<{ year: number; month: number }>(
    () => ({ year: now.year, month: now.month })
  );
  const [selectedDayIso, setSelectedDayIso] = reactModule.useState<string>("");
  const [durationMinutes, setDurationMinutes] =
    reactModule.useState<number>(DEFAULT_DURATION_MINUTES);

  const firstDayOfMonth = luxonModule.DateTime.fromObject(
    { year: visibleMonth.year, month: visibleMonth.month, day: 1 },
    { zone: props.timezone }
  );
  // weekday: 1=Mon ... 7=Sun in Luxon; we want Sun=0 offset
  const weekdayOffset = firstDayOfMonth.isValid ? firstDayOfMonth.weekday % 7 : 0;
  const daysInMonthCount = firstDayOfMonth.isValid ? (firstDayOfMonth.daysInMonth ?? 0) : 0;

  const dayCells: (luxonModule.DateTime | null)[] = [
    ...Array.from({ length: weekdayOffset }, () => null),
    ...Array.from({ length: daysInMonthCount }, (_, index) =>
      firstDayOfMonth.set({ day: index + 1 })
    )
  ];

  const todayIso = now.toISODate() ?? "";

  const calendarSlots = reactModule.useMemo(() => {
    if (selectedDayIso === "") {
      return [];
    }
    return calendarUtilsModule.buildCalendarSlotCandidates({
      requestId: props.requestId,
      timezone: props.timezone,
      selectedDayIso,
      busyIntervals: props.busyIntervals,
      now,
      slotDurationMinutes: durationMinutes,
      startHour: 7,
      endHour: 22
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    props.requestId,
    props.timezone,
    selectedDayIso,
    props.busyIntervals,
    now.toMillis(),
    durationMinutes
  ]);

  function handleDurationChange(nextMinutes: number) {
    setDurationMinutes(nextMinutes);
    if (props.selectedSlots.length > 0) {
      props.onSelectedSlotsChange([]);
    }
  }

  const morningSlots = calendarSlots.filter((slot) => slot.hour >= 7 && slot.hour < 12);
  const afternoonSlots = calendarSlots.filter((slot) => slot.hour >= 12 && slot.hour < 18);
  const eveningSlots = calendarSlots.filter((slot) => slot.hour >= 18 && slot.hour < 22);

  const selectedSlotIds = new Set(props.selectedSlots.map((slot) => slot.slotId));

  function formatSlotLabel(slot: calendarUtilsModule.CalendarSlotCandidate): string {
    const startDt = luxonModule.DateTime.fromISO(slot.startAt, { zone: props.timezone });
    if (!startDt.isValid) {
      const h = slot.hour;
      if (h === 0) return "12 AM";
      if (h < 12) return `${h} AM`;
      if (h === 12) return "12 PM";
      return `${h - 12} PM`;
    }
    if (startDt.minute !== 0) {
      return startDt.toFormat("h:mm a");
    }
    return startDt.toFormat("h a");
  }

  function handleSlotClick(slot: calendarUtilsModule.CalendarSlotCandidate) {
    if (slot.isBusy || slot.isPast) {
      return;
    }
    if (selectedSlotIds.has(slot.slotId)) {
      props.onSelectedSlotsChange(props.selectedSlots.filter((s) => s.slotId !== slot.slotId));
    } else {
      props.onSelectedSlotsChange([
        ...props.selectedSlots,
        { slotId: slot.slotId, startAt: slot.startAt, endAt: slot.endAt, timezone: slot.timezone }
      ]);
    }
  }

  const monthName = luxonModule.Info.months("long", { locale: "es" })[visibleMonth.month - 1] ?? "";

  // Busy appointments for selected day
  const selectedDayBusyAppointments = reactModule.useMemo(() => {
    if (selectedDayIso === "") {
      return [];
    }
    const dayStart = luxonModule.DateTime.fromISO(selectedDayIso, {
      zone: props.timezone
    }).startOf("day");
    const dayEnd = dayStart.endOf("day");
    return props.busyIntervals.filter((interval) => {
      return interval.start < dayEnd && dayStart < interval.end;
    });
  }, [selectedDayIso, props.busyIntervals, props.timezone]);

  function renderSlotGroup(label: string, slots: calendarUtilsModule.CalendarSlotCandidate[]) {
    if (slots.length === 0) {
      return null;
    }
    return (
      <div className="mb-3">
        <p className="text-xs font-semibold text-slate-500 mb-1">{label}</p>
        <div className="flex flex-wrap gap-1.5">
          {slots.map((slot) => {
            const isSelected = selectedSlotIds.has(slot.slotId);
            const isDisabled = slot.isBusy || slot.isPast;
            let chipClass: string;
            if (isDisabled) {
              chipClass =
                "bg-slate-50 text-slate-300 line-through rounded-full px-2.5 py-1 text-xs cursor-not-allowed";
            } else if (isSelected) {
              chipClass =
                "bg-brand-teal text-white border border-brand-teal rounded-full px-2.5 py-1 text-xs";
            } else {
              chipClass =
                "border border-slate-200 bg-white text-slate-700 hover:border-brand-teal hover:text-brand-teal rounded-full px-2.5 py-1 text-xs cursor-pointer";
            }
            return (
              <button
                className={chipClass}
                disabled={isDisabled}
                key={slot.slotId}
                onClick={() => handleSlotClick(slot)}
                type="button"
              >
                {formatSlotLabel(slot)}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Calendar navigation */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <button
            className="p-1 rounded hover:bg-slate-100 text-slate-600"
            onClick={() => {
              const prev = firstDayOfMonth.minus({ months: 1 });
              const newMonth = { year: prev.year, month: prev.month };
              setVisibleMonth(newMonth);
              props.onMonthChange?.(newMonth);
            }}
            type="button"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path d="M15 19l-7-7 7-7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <span className="text-sm font-semibold text-slate-700 capitalize">
            {monthName} {visibleMonth.year}
          </span>
          <button
            className="p-1 rounded hover:bg-slate-100 text-slate-600"
            onClick={() => {
              const next = firstDayOfMonth.plus({ months: 1 });
              const newMonth = { year: next.year, month: next.month };
              setVisibleMonth(newMonth);
              props.onMonthChange?.(newMonth);
            }}
            type="button"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {/* Weekday headers */}
        <div className="grid grid-cols-7 text-center text-xs font-semibold text-slate-500 mb-1">
          {calendarUtilsModule.weekDayLabels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>

        {/* Day cells */}
        <div className="grid grid-cols-7 gap-0.5">
          {dayCells.map((dateCell, index) => {
            if (dateCell === null) {
              return <div className="h-8" key={`empty-${index}`} />;
            }
            const isoDate = dateCell.toISODate() ?? "";
            const isSelected = isoDate === selectedDayIso;
            const isPast = isoDate < todayIso;
            const isToday = isoDate === todayIso;

            const dayStart = dateCell.startOf("day");
            const dayEnd = dateCell.endOf("day");
            const hasBusy = props.busyIntervals.some(
              (interval) => interval.start < dayEnd && dayStart < interval.end
            );

            let buttonClass: string;
            if (isPast) {
              buttonClass =
                "w-8 h-8 mx-auto flex items-center justify-center text-xs text-slate-300 cursor-default";
            } else if (isSelected) {
              buttonClass =
                "w-8 h-8 mx-auto flex items-center justify-center text-xs bg-brand-teal text-white rounded-full";
            } else if (isToday) {
              buttonClass =
                "w-8 h-8 mx-auto flex items-center justify-center text-xs font-bold text-brand-teal hover:bg-slate-100 rounded-full";
            } else {
              buttonClass =
                "w-8 h-8 mx-auto flex items-center justify-center text-xs text-slate-700 hover:bg-slate-100 rounded-full";
            }

            return (
              <div className="flex flex-col items-center" key={isoDate || `day-${index}`}>
                <button
                  className={buttonClass}
                  disabled={isPast}
                  onClick={() => {
                    if (!isPast && isoDate !== "") {
                      setSelectedDayIso(isoDate);
                    }
                  }}
                  type="button"
                >
                  {dateCell.day}
                </button>
                {hasBusy && !isPast ? (
                  <div className="w-1 h-1 rounded-full bg-brand-teal mt-0.5" />
                ) : (
                  <div className="w-1 h-1 mt-0.5" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Loading indicator */}
      {props.isLoadingAvailability ? (
        <p className="text-xs text-slate-400">Cargando disponibilidad...</p>
      ) : null}

      {/* Busy appointments for selected day */}
      {selectedDayIso !== "" && selectedDayBusyAppointments.length > 0 ? (
        <div>
          <p className="text-xs font-semibold text-slate-600 mb-1">Citas del día</p>
          {selectedDayBusyAppointments.map((interval, index) => (
            <p className="text-xs text-slate-500" key={index}>
              {interval.start.toFormat("h:mm a")} - {interval.end.toFormat("h:mm a")}
            </p>
          ))}
        </div>
      ) : null}

      {/* Duration selector + Time grid */}
      {selectedDayIso !== "" ? (
        <div>
          <div className="mb-3">
            <label
              className="block text-xs font-semibold text-slate-600 mb-1"
              htmlFor={`slot-duration-${props.requestId}`}
            >
              Duración de la sesión
            </label>
            <select
              className="w-full sm:w-auto rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal"
              id={`slot-duration-${props.requestId}`}
              onChange={(event) => {
                handleDurationChange(Number(event.target.value));
              }}
              value={durationMinutes}
            >
              {DURATION_PRESETS_MINUTES.map((minutes) => (
                <option key={minutes} value={minutes}>
                  {minutes} min
                </option>
              ))}
            </select>
          </div>
          {renderSlotGroup("Mañana", morningSlots)}
          {renderSlotGroup("Tarde", afternoonSlots)}
          {renderSlotGroup("Noche", eveningSlots)}
        </div>
      ) : null}

      {/* Selected slots summary */}
      {props.selectedSlots.length > 0 ? (
        <div>
          <p className="text-xs font-semibold text-slate-600 mb-1">Horarios seleccionados</p>
          <div className="flex flex-wrap gap-1.5">
            {props.selectedSlots.map((slot) => {
              const startDt = luxonModule.DateTime.fromISO(slot.startAt, {
                zone: slot.timezone
              }).setLocale("es");
              const label = startDt.isValid ? startDt.toFormat("LLL dd, h:mm a") : slot.startAt;
              return (
                <span
                  className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 rounded-full px-2.5 py-1 text-xs"
                  key={slot.slotId}
                >
                  {label}
                  <button
                    className="text-emerald-500 hover:text-emerald-700"
                    onClick={() => {
                      props.onSelectedSlotsChange(
                        props.selectedSlots.filter((s) => s.slotId !== slot.slotId)
                      );
                    }}
                    type="button"
                  >
                    ×
                  </button>
                </span>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

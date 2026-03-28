import * as luxonModule from "luxon";
import type * as googleCalendarModel from "@domain/models/google_calendar";

export const weekDayLabels = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

export interface BusyIntervalRange {
  start: luxonModule.DateTime;
  end: luxonModule.DateTime;
}

export interface CalendarSlotCandidate {
  slotId: string;
  startAt: string;
  endAt: string;
  timezone: string;
  isBusy: boolean;
  isPast: boolean;
  hour: number; // the hour (0-23) for easy filtering
}

export function buildCalendarSlotCandidates(params: {
  requestId: string;
  timezone: string;
  selectedDayIso: string;
  busyIntervals: BusyIntervalRange[];
  now: luxonModule.DateTime;
  startHour?: number;
  endHour?: number;
}): CalendarSlotCandidate[] {
  const startHour = params.startHour ?? 6;
  const endHour = params.endHour ?? 22;
  const selectedDay = luxonModule.DateTime.fromISO(params.selectedDayIso, {
    zone: params.timezone
  }).startOf("day");
  if (!selectedDay.isValid) {
    return [];
  }

  const slots: CalendarSlotCandidate[] = [];
  for (let hour = startHour; hour < endHour; hour += 1) {
    const startAt = selectedDay.set({ hour, minute: 0, second: 0, millisecond: 0 });
    const endAt = startAt.plus({ hours: 1 });
    const isBusy = params.busyIntervals.some((interval) => {
      return startAt < interval.end && interval.start < endAt;
    });
    const isPast = startAt <= params.now;
    const startAtIso = startAt.toISO();
    const endAtIso = endAt.toISO();
    if (startAtIso === null || endAtIso === null) {
      continue;
    }
    slots.push({
      slotId: `${params.requestId}_${startAt.toFormat("yyyyLLdd_HHmm")}`,
      startAt: startAtIso,
      endAt: endAtIso,
      timezone: params.timezone,
      isBusy,
      isPast,
      hour
    });
  }
  return slots;
}

export function parseBusyIntervals(
  rawIntervals: googleCalendarModel.GoogleCalendarBusyInterval[],
  timezone: string
): BusyIntervalRange[] {
  return rawIntervals
    .map((interval) => {
      const start = luxonModule.DateTime.fromISO(interval.startAt, { zone: timezone });
      const end = luxonModule.DateTime.fromISO(interval.endAt, { zone: timezone });
      if (!start.isValid || !end.isValid) {
        return null;
      }
      return { start, end };
    })
    .filter((interval): interval is BusyIntervalRange => interval !== null);
}

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
  slotDurationMinutes: number;
  startHour?: number;
  endHour?: number;
}): CalendarSlotCandidate[] {
  const startHour = params.startHour ?? 7;
  const endHour = params.endHour ?? 22;
  const selectedDay = luxonModule.DateTime.fromISO(params.selectedDayIso, {
    zone: params.timezone
  }).startOf("day");
  if (!selectedDay.isValid) {
    return [];
  }

  const slots: CalendarSlotCandidate[] = [];
  let startAt = selectedDay.set({ hour: startHour, minute: 0, second: 0, millisecond: 0 });
  const dayEnd = selectedDay.set({ hour: endHour, minute: 0, second: 0, millisecond: 0 });

  while (startAt < dayEnd) {
    const endAt = startAt.plus({ minutes: params.slotDurationMinutes });
    if (endAt > dayEnd) {
      break;
    }
    const isBusy = params.busyIntervals.some((interval) => {
      return startAt < interval.end && interval.start < endAt;
    });
    const isPast = startAt <= params.now;
    const startAtIso = startAt.toISO();
    const endAtIso = endAt.toISO();
    if (startAtIso !== null && endAtIso !== null) {
      slots.push({
        slotId: `${params.requestId}_${startAt.toFormat("yyyyLLdd_HHmm")}`,
        startAt: startAtIso,
        endAt: endAtIso,
        timezone: params.timezone,
        isBusy,
        isPast,
        hour: startAt.hour
      });
    }
    startAt = startAt.plus({ minutes: params.slotDurationMinutes });
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

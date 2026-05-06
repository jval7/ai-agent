import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as calendarUtilsModule from "@shared/utils/calendar";

import { colombiaTimezone } from "@adapters/inbound/react/hooks/useBookedAppointments";
import type { BookedAppointment } from "@adapters/inbound/react/hooks/useBookedAppointments";

export interface SelectedSlot {
  slotId: string;
  startAt: string;
  endAt: string;
  timezone: string;
}

export function useReschedule(
  isRescheduleOpen: boolean,
  selectedBookedAppointment: BookedAppointment | null
) {
  const appContainer = appContainerContextModule.useAppContainer();

  const [rescheduleSlotPickerMonth, setRescheduleSlotPickerMonth] = reactModule.useState<{
    year: number;
    month: number;
  }>(() => {
    const now = luxonModule.DateTime.now().setZone(colombiaTimezone);
    return { year: now.year, month: now.month };
  });

  const [rescheduleSelectedSlots, setRescheduleSelectedSlots] = reactModule.useState<
    SelectedSlot[]
  >([]);

  // Seed slot with the current appointment when reschedule opens
  reactModule.useEffect(() => {
    if (!isRescheduleOpen || selectedBookedAppointment === null) {
      if (!isRescheduleOpen) {
        setRescheduleSelectedSlots([]);
      }
      return;
    }
    const startAt = selectedBookedAppointment.startAt.toISO();
    const endAt = selectedBookedAppointment.endAt.toISO();
    if (startAt === null || endAt === null) {
      setRescheduleSelectedSlots([]);
      return;
    }
    const appointmentId =
      selectedBookedAppointment.source === "MANUAL"
        ? (selectedBookedAppointment.manualAppointmentId ?? "reschedule")
        : (selectedBookedAppointment.requestId ?? "reschedule");
    const startDt = selectedBookedAppointment.startAt.setZone(colombiaTimezone);
    const slotId = `${appointmentId}_${startDt.toFormat("yyyyLLdd_HHmm")}`;
    setRescheduleSelectedSlots([{ slotId, startAt, endAt, timezone: colombiaTimezone }]);
  }, [isRescheduleOpen, selectedBookedAppointment]);

  const rescheduleMonthStart = luxonModule.DateTime.fromObject(
    {
      year: rescheduleSlotPickerMonth.year,
      month: rescheduleSlotPickerMonth.month,
      day: 1
    },
    { zone: colombiaTimezone }
  );
  const rescheduleMonthEnd = rescheduleMonthStart.plus({ months: 1 });
  const rescheduleMonthFromIso = rescheduleMonthStart.toISO();
  const rescheduleMonthToIso = rescheduleMonthEnd.toISO();

  const rescheduleAvailabilityQuery = reactQueryModule.useQuery({
    queryKey: [
      "google-calendar-availability",
      "reschedule",
      rescheduleMonthFromIso,
      rescheduleMonthToIso
    ],
    enabled: isRescheduleOpen && rescheduleMonthFromIso !== null && rescheduleMonthToIso !== null,
    queryFn: () =>
      appContainer.schedulingUseCase.getAvailability(rescheduleMonthFromIso!, rescheduleMonthToIso!)
  });

  const rescheduleBusyIntervals = reactModule.useMemo<
    calendarUtilsModule.BusyIntervalRange[]
  >(() => {
    if (rescheduleAvailabilityQuery.data === undefined) {
      return [];
    }
    const allBusy = calendarUtilsModule.parseBusyIntervals(
      rescheduleAvailabilityQuery.data.busyIntervals,
      colombiaTimezone
    );
    if (selectedBookedAppointment === null) {
      return allBusy;
    }
    // Exclude the current appointment's own slot so it doesn't appear as busy
    const currentStartMs = selectedBookedAppointment.startAt.setZone(colombiaTimezone).toMillis();
    const currentEndMs = selectedBookedAppointment.endAt.setZone(colombiaTimezone).toMillis();
    return allBusy.filter((interval) => {
      return !(
        interval.start.toMillis() === currentStartMs && interval.end.toMillis() === currentEndMs
      );
    });
  }, [rescheduleAvailabilityQuery.data, selectedBookedAppointment]);

  return {
    rescheduleSlotPickerMonth,
    setRescheduleSlotPickerMonth,
    rescheduleSelectedSlots,
    setRescheduleSelectedSlots,
    rescheduleAvailabilityQuery,
    rescheduleBusyIntervals
  };
}

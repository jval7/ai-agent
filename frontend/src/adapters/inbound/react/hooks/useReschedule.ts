import * as reactModule from "react";
import * as luxonModule from "luxon";

import * as useAgendaQueryModule from "@adapters/inbound/react/hooks/useAgendaQuery";
import type { BookedAppointment } from "@adapters/inbound/react/hooks/useBookedAppointments";
import * as calendarUtilsModule from "@shared/utils/calendar";

const colombiaTimezone = "America/Bogota";

interface UseRescheduleParams {
  expandedBookedAction: "reschedule" | "cancel" | "payment" | "change-modality" | null;
  selectedBookedAppointment: BookedAppointment | null;
  tenantId: string | undefined;
}

export function useReschedule({
  expandedBookedAction,
  selectedBookedAppointment,
  tenantId
}: UseRescheduleParams) {
  const [rescheduleSlotPickerMonth, setRescheduleSlotPickerMonth] = reactModule.useState<{
    year: number;
    month: number;
  }>(() => {
    const now = luxonModule.DateTime.now().setZone(colombiaTimezone);
    return { year: now.year, month: now.month };
  });

  const [rescheduleSelectedSlots, setRescheduleSelectedSlots] = reactModule.useState<
    { slotId: string; startAt: string; endAt: string; timezone: string }[]
  >([]);

  reactModule.useEffect(() => {
    if (expandedBookedAction !== "reschedule" || selectedBookedAppointment === null) {
      if (expandedBookedAction !== "reschedule") {
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
  }, [expandedBookedAction, selectedBookedAppointment]);

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

  const rescheduleAvailabilityQuery = useAgendaQueryModule.useAgendaAvailabilityQuery(
    {
      fromIso: rescheduleMonthFromIso,
      toIso: rescheduleMonthToIso,
      enabled: expandedBookedAction === "reschedule"
    },
    tenantId
  );

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

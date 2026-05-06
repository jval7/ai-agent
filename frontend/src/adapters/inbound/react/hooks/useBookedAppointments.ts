import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as patientModel from "@domain/models/patient";
import type * as schedulingModel from "@domain/models/scheduling";

export const schedulingRequestsQueryKey = ["scheduling-requests"] as const;
export const googleCalendarConnectionQueryKey = ["google-calendar-connection"] as const;
export const patientsQueryKey = ["patients"] as const;
export const manualAppointmentsQueryKey = ["manual-appointments"] as const;

export const colombiaTimezone = "America/Bogota";

export interface BookedAppointment {
  itemKey: string;
  source: "BOT" | "MANUAL";
  requestId: string | null;
  manualAppointmentId: string | null;
  patientDisplayName: string;
  patientPhone: string;
  summary: string;
  dayIso: string;
  startAt: luxonModule.DateTime;
  endAt: luxonModule.DateTime;
  request: schedulingModel.SchedulingRequestSummary | null;
  manualAppointment: manualAppointmentModel.ManualAppointment | null;
}

export function resolvePatientDisplayName(
  request: schedulingModel.SchedulingRequestSummary,
  patientMap?: Map<string, patientModel.Patient>
): string {
  const names = [request.patientFirstName, request.patientLastName]
    .map((value) => value?.trim() ?? "")
    .filter((value) => value !== "");
  if (names.length > 0) {
    return names.join(" ");
  }
  if (patientMap !== undefined) {
    const patient = patientMap.get(request.whatsappUserId);
    if (patient !== undefined) {
      const patientName = `${patient.firstName} ${patient.lastName}`.trim();
      if (patientName !== "") {
        return patientName;
      }
    }
  }
  return request.whatsappUserId;
}

export function resolveBookedSlot(
  request: schedulingModel.SchedulingRequestSummary
): schedulingModel.SchedulingSlot | null {
  if (request.selectedSlotId !== null) {
    const selectedSlot = request.slots.find((slot) => slot.slotId === request.selectedSlotId);
    if (selectedSlot !== undefined) {
      return selectedSlot;
    }
  }

  const bookedSlot = request.slots.find((slot) => slot.status === "BOOKED");
  if (bookedSlot !== undefined) {
    return bookedSlot;
  }

  return null;
}

export interface UseBookedAppointmentsResult {
  // Queries
  requestsQuery: reactQueryModule.UseQueryResult<schedulingModel.SchedulingRequestSummary[]>;
  googleCalendarConnectionQuery: reactQueryModule.UseQueryResult<unknown>;
  patientsQuery: reactQueryModule.UseQueryResult<patientModel.Patient[]>;
  manualAppointmentsQuery: reactQueryModule.UseQueryResult<
    manualAppointmentModel.ManualAppointment[]
  >;
  // Derived data
  allRequests: schedulingModel.SchedulingRequestSummary[];
  allPatients: patientModel.Patient[];
  allManualAppointments: manualAppointmentModel.ManualAppointment[];
  patientsByWhatsappUserId: Map<string, patientModel.Patient>;
  timezone: string;
  bookedAppointments: BookedAppointment[];
  bookedAppointmentsByDay: Map<string, BookedAppointment[]>;
  selectedBookedAppointment: BookedAppointment | null;
  selectedDayAppointments: BookedAppointment[];
  // Calendar navigation state
  visibleMonth: { year: number; month: number };
  setVisibleMonth: (month: { year: number; month: luxonModule.MonthNumbers }) => void;
  visibleMonthStart: luxonModule.DateTime;
  selectedDayIso: string;
  setSelectedDayIso: (iso: string) => void;
  // Mobile navigation
  mobileBookedStep: "calendar" | "dayList" | "detail";
  setMobileBookedStep: (step: "calendar" | "dayList" | "detail") => void;
  // Appointment selection
  selectedBookedItemKey: string | null;
  setSelectedBookedItemKey: (key: string | null) => void;
}

export function useBookedAppointments(options: {
  isBookedTab: boolean;
  selectedRequestId: string | null;
  setSelectedRequestId: (id: string | null) => void;
}): UseBookedAppointmentsResult {
  const { isBookedTab, setSelectedRequestId } = options;
  const appContainer = appContainerContextModule.useAppContainer();
  const nowDate = luxonModule.DateTime.now();

  const requestsQuery = reactQueryModule.useQuery({
    queryKey: schedulingRequestsQueryKey,
    queryFn: () => appContainer.schedulingUseCase.listRequests(),
    refetchInterval: 60_000
  });
  const googleCalendarConnectionQuery = reactQueryModule.useQuery({
    queryKey: googleCalendarConnectionQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getGoogleCalendarConnectionStatus()
  });
  const patientsQuery = reactQueryModule.useQuery({
    queryKey: patientsQueryKey,
    queryFn: () => appContainer.patientUseCase.listPatients()
  });
  const manualAppointmentsQuery = reactQueryModule.useQuery({
    queryKey: manualAppointmentsQueryKey,
    queryFn: () => appContainer.manualAppointmentUseCase.listAppointments()
  });

  const [selectedBookedItemKey, setSelectedBookedItemKey] = reactModule.useState<string | null>(
    null
  );
  const [visibleMonth, setVisibleMonth] = reactModule.useState({
    year: nowDate.year,
    month: nowDate.month
  });
  const [selectedDayIso, setSelectedDayIso] = reactModule.useState<string>(() => {
    const isoDay = nowDate.toISODate();
    return isoDay ?? "";
  });
  const [mobileBookedStep, setMobileBookedStep] = reactModule.useState<
    "calendar" | "dayList" | "detail"
  >("calendar");

  const allRequests = requestsQuery.data ?? [];
  const allPatients = patientsQuery.data ?? [];
  const allManualAppointments = manualAppointmentsQuery.data ?? [];

  const timezone = googleCalendarConnectionQuery.data?.professionalTimezone ?? "UTC";

  const visibleMonthStart = luxonModule.DateTime.fromObject(
    {
      year: visibleMonth.year,
      month: visibleMonth.month,
      day: 1
    },
    { zone: timezone }
  ).startOf("day");

  reactModule.useEffect(() => {
    const firstDayIso = visibleMonthStart.toISODate();
    if (firstDayIso !== null) {
      setSelectedDayIso(firstDayIso);
    }
    // Only re-run when year/month change, not the whole DateTime
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleMonthStart.year, visibleMonthStart.month]);

  const patientsByWhatsappUserId = reactModule.useMemo(() => {
    const map = new Map<string, patientModel.Patient>();
    allPatients.forEach((patient) => {
      map.set(patient.whatsappUserId, patient);
    });
    return map;
  }, [allPatients]);

  const FINALIZED_STATUSES = reactModule.useMemo(
    () => new Set<string>(["BOOKED", "SESSION_CLOSED", "HUMAN_HANDOFF"]),
    []
  );

  const bookedAppointments = reactModule.useMemo<BookedAppointment[]>(() => {
    if (!isBookedTab) {
      return [];
    }
    const combinedAppointments: BookedAppointment[] = [];

    allRequests
      .filter((r) => FINALIZED_STATUSES.has(r.status))
      .forEach((request) => {
        const selectedSlot = resolveBookedSlot(request);
        if (selectedSlot === null) {
          return;
        }
        const appointmentTimezone =
          selectedSlot.timezone.trim() === "" ? timezone : selectedSlot.timezone;
        const startAt = luxonModule.DateTime.fromISO(selectedSlot.startAt, {
          zone: appointmentTimezone
        }).setZone(timezone);
        const endAt = luxonModule.DateTime.fromISO(selectedSlot.endAt, {
          zone: appointmentTimezone
        }).setZone(timezone);
        const dayIso = startAt.toISODate();
        if (!startAt.isValid || !endAt.isValid || dayIso === null) {
          return;
        }
        const patientDisplayName = resolvePatientDisplayName(request, patientsByWhatsappUserId);
        combinedAppointments.push({
          itemKey: `bot:${request.requestId}`,
          source: "BOT",
          requestId: request.requestId,
          manualAppointmentId: null,
          patientDisplayName,
          patientPhone: request.whatsappUserId,
          summary:
            patientDisplayName.trim() === "" ? "Cita bot" : `Cita bot - ${patientDisplayName}`,
          dayIso,
          startAt,
          endAt,
          request,
          manualAppointment: null
        });
      });

    allManualAppointments
      .filter((manualAppointment) => manualAppointment.status === "SCHEDULED")
      .forEach((manualAppointment) => {
        const appointmentTimezone =
          manualAppointment.timezone.trim() === "" ? colombiaTimezone : manualAppointment.timezone;
        const startAt = luxonModule.DateTime.fromISO(manualAppointment.startAt, {
          zone: appointmentTimezone
        }).setZone(timezone);
        const endAt = luxonModule.DateTime.fromISO(manualAppointment.endAt, {
          zone: appointmentTimezone
        }).setZone(timezone);
        const dayIso = startAt.toISODate();
        if (!startAt.isValid || !endAt.isValid || dayIso === null) {
          return;
        }
        const patient = patientsByWhatsappUserId.get(manualAppointment.patientWhatsappUserId);
        const patientDisplayName =
          patient === undefined
            ? manualAppointment.patientWhatsappUserId
            : `${patient.firstName} ${patient.lastName}`;
        combinedAppointments.push({
          itemKey: `manual:${manualAppointment.appointmentId}`,
          source: "MANUAL",
          requestId: null,
          manualAppointmentId: manualAppointment.appointmentId,
          patientDisplayName,
          patientPhone: manualAppointment.patientWhatsappUserId,
          summary: manualAppointment.summary,
          dayIso,
          startAt,
          endAt,
          request: null,
          manualAppointment
        });
      });

    return combinedAppointments.sort((left, right) => {
      return left.startAt.toMillis() - right.startAt.toMillis();
    });
  }, [
    FINALIZED_STATUSES,
    allManualAppointments,
    allRequests,
    isBookedTab,
    patientsByWhatsappUserId,
    timezone
  ]);

  const bookedAppointmentsByDay = reactModule.useMemo(() => {
    const appointmentsByDay = new Map<string, BookedAppointment[]>();
    bookedAppointments.forEach((appointment) => {
      const dayAppointments = appointmentsByDay.get(appointment.dayIso);
      if (dayAppointments === undefined) {
        appointmentsByDay.set(appointment.dayIso, [appointment]);
        return;
      }
      appointmentsByDay.set(appointment.dayIso, [...dayAppointments, appointment]);
    });
    return appointmentsByDay;
  }, [bookedAppointments]);

  const selectedBookedAppointment = reactModule.useMemo(() => {
    if (!isBookedTab || selectedBookedItemKey === null) {
      return null;
    }
    const appointment = bookedAppointments.find(
      (currentAppointment) => currentAppointment.itemKey === selectedBookedItemKey
    );
    return appointment ?? null;
  }, [bookedAppointments, isBookedTab, selectedBookedItemKey]);

  const selectedDayAppointments = reactModule.useMemo(() => {
    if (!isBookedTab || selectedDayIso === "") {
      return [];
    }
    return bookedAppointmentsByDay.get(selectedDayIso) ?? [];
  }, [bookedAppointmentsByDay, isBookedTab, selectedDayIso]);

  reactModule.useEffect(() => {
    if (!isBookedTab) {
      return;
    }
    if (bookedAppointments.length === 0) {
      setSelectedBookedItemKey(null);
      return;
    }

    if (selectedBookedAppointment !== null) {
      if (selectedBookedAppointment.dayIso !== selectedDayIso) {
        setSelectedDayIso(selectedBookedAppointment.dayIso);
      }
      if (
        selectedBookedAppointment.source === "BOT" &&
        selectedBookedAppointment.requestId !== null
      ) {
        setSelectedRequestId(selectedBookedAppointment.requestId);
      } else {
        setSelectedRequestId(null);
      }
      return;
    }

    const firstAppointment = bookedAppointments[0];
    if (firstAppointment === undefined) {
      return;
    }
    setSelectedBookedItemKey(firstAppointment.itemKey);
    if (firstAppointment.source === "BOT" && firstAppointment.requestId !== null) {
      setSelectedRequestId(firstAppointment.requestId);
    } else {
      setSelectedRequestId(null);
    }
    if (firstAppointment.dayIso !== selectedDayIso) {
      setSelectedDayIso(firstAppointment.dayIso);
    }
  }, [
    bookedAppointments,
    isBookedTab,
    selectedBookedAppointment,
    selectedDayIso,
    setSelectedRequestId
  ]);

  return {
    requestsQuery,
    googleCalendarConnectionQuery,
    patientsQuery,
    manualAppointmentsQuery,
    allRequests,
    allPatients,
    allManualAppointments,
    patientsByWhatsappUserId,
    timezone,
    bookedAppointments,
    bookedAppointmentsByDay,
    selectedBookedAppointment,
    selectedDayAppointments,
    visibleMonth,
    setVisibleMonth,
    visibleMonthStart,
    selectedDayIso,
    setSelectedDayIso,
    mobileBookedStep,
    setMobileBookedStep,
    selectedBookedItemKey,
    setSelectedBookedItemKey
  };
}

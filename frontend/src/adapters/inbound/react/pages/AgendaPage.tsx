import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as patientModel from "@domain/models/patient";
import type * as schedulingModel from "@domain/models/scheduling";
import * as uiErrorModule from "@shared/http/ui_error";
import * as dateUtilsModule from "@shared/utils/date";

const schedulingRequestsQueryKey = ["scheduling-requests"] as const;
const googleCalendarConnectionQueryKey = ["google-calendar-connection"] as const;
const patientsQueryKey = ["patients"] as const;
const manualAppointmentsQueryKey = ["manual-appointments"] as const;
const colombiaTimezone = "America/Bogota";
const manualAppointmentDurationOptionsMinutes = [30, 45, 60, 90, 120];
const halfHourMinuteOptions = ["00", "30"] as const;
const hourOptions = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"));

interface AgendaSection {
  id: string;
  label: string;
  statuses: {
    status: schedulingModel.SchedulingRequestStatus;
    label: string;
  }[];
}

const agendaSections: AgendaSection[] = [
  {
    id: "APPROVALS",
    label: "Aprobaciones",
    statuses: [
      { status: "AWAITING_CONSULTATION_REVIEW", label: "Pendiente revisión" },
      { status: "AWAITING_CONSULTATION_DETAILS", label: "Esperando detalles" },
      { status: "AWAITING_PATIENT_CHOICE", label: "Esperando paciente" },
      { status: "AWAITING_PAYMENT_CONFIRMATION", label: "Pendiente pago" },
      { status: "CONSULTATION_REJECTED", label: "Rechazado" }
    ]
  },
  {
    id: "FINALIZED",
    label: "Agenda e Historial",
    statuses: [
      { status: "BOOKED", label: "Agendadas" },
      { status: "CANCELLED", label: "Canceladas" },
      { status: "HUMAN_HANDOFF", label: "Human Handoff" }
    ]
  },
  {
    id: "MANUAL_SCHEDULING",
    label: "Agendamiento manual",
    statuses: []
  },
  {
    id: "FINANCE",
    label: "Finanzas",
    statuses: []
  }
];

const approvalStatusLabels: Record<
  string,
  { label: string; tone: "neutral" | "success" | "warning" | "danger" }
> = {
  AWAITING_CONSULTATION_REVIEW: { label: "Pendiente revisión", tone: "warning" },
  AWAITING_CONSULTATION_DETAILS: { label: "Esperando detalles", tone: "neutral" },
  AWAITING_PATIENT_CHOICE: { label: "Esperando paciente", tone: "neutral" },
  AWAITING_PAYMENT_CONFIRMATION: { label: "Pendiente pago", tone: "warning" },
  CONSULTATION_REJECTED: { label: "Rechazado", tone: "danger" }
};

const APPROVAL_STATUSES: schedulingModel.SchedulingRequestStatus[] = [
  "AWAITING_CONSULTATION_REVIEW",
  "AWAITING_CONSULTATION_DETAILS",
  "AWAITING_PATIENT_CHOICE",
  "AWAITING_PAYMENT_CONFIRMATION",
  "CONSULTATION_REJECTED"
];

const weekDayLabels = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

interface BusyIntervalRange {
  start: luxonModule.DateTime;
  end: luxonModule.DateTime;
}

interface LocalDateTimeParts {
  date: string;
  hour: string;
  minute: "00" | "30";
}

export interface CalendarSlotCandidate {
  slotId: string;
  startAt: string;
  endAt: string;
  timezone: string;
  isBusy: boolean;
  isPast: boolean;
}

interface BookedAppointment {
  itemKey: string;
  source: "BOT" | "MANUAL";
  requestId: string | null;
  manualAppointmentId: string | null;
  patientDisplayName: string;
  summary: string;
  dayIso: string;
  startAt: luxonModule.DateTime;
  endAt: luxonModule.DateTime;
  request: schedulingModel.SchedulingRequestSummary | null;
  manualAppointment: manualAppointmentModel.ManualAppointment | null;
}

interface PatientFormState {
  whatsappUserId: string;
  firstName: string;
  lastName: string;
  email: string;
  age: string;
  consultationReason: string;
  location: string;
  phone: string;
}

interface PatientUpdateFormState {
  firstName: string;
  lastName: string;
  email: string;
  age: string;
  consultationReason: string;
  location: string;
  phone: string;
}

interface ManualAppointmentFormState {
  patientWhatsappUserId: string;
  startAt: string;
  durationMinutes: string;
  summary: string;
}

type ManualAppointmentListFilter = "SCHEDULED" | "CANCELLED";

interface BookedAppointmentFormState {
  startAt: string;
  endAt: string;
  timezone: string;
  eventSummary: string;
  cancelReason: string;
}

interface PaymentFormState {
  paymentAmountCop: string;
  paymentMethod: "CASH" | "TRANSFER";
  paymentStatus: "PENDING" | "PAID";
}

type FinancePaymentStatusFilter = "ALL" | "PENDING" | "PAID";
type FinancePaymentMethodFilter = "ALL" | "CASH" | "TRANSFER";
type FinanceSourceFilter = "ALL" | "CHATBOT" | "MANUAL";

interface FinanceAppointmentItem {
  itemKey: string;
  source: "CHATBOT" | "MANUAL";
  patientDisplayName: string;
  whatsappUserId: string;
  startAt: string;
  endAt: string;
  timezone: string;
  paymentAmountCop: number | null;
  paymentMethod: "CASH" | "TRANSFER" | null;
  paymentStatus: "PENDING" | "PAID";
  paymentUpdatedAt: string | null;
}

function emptyPatientForm(): PatientFormState {
  return {
    whatsappUserId: "",
    firstName: "",
    lastName: "",
    email: "",
    age: "",
    consultationReason: "",
    location: "",
    phone: ""
  };
}

function emptyPatientUpdateForm(): PatientUpdateFormState {
  return {
    firstName: "",
    lastName: "",
    email: "",
    age: "",
    consultationReason: "",
    location: "",
    phone: ""
  };
}

function emptyManualAppointmentForm(): ManualAppointmentFormState {
  return {
    patientWhatsappUserId: "",
    startAt: "",
    durationMinutes: "60",
    summary: ""
  };
}

function emptyBookedAppointmentForm(timezone: string): BookedAppointmentFormState {
  return {
    startAt: "",
    endAt: "",
    timezone,
    eventSummary: "",
    cancelReason: ""
  };
}

function emptyPaymentForm(): PaymentFormState {
  return {
    paymentAmountCop: "",
    paymentMethod: "CASH",
    paymentStatus: "PENDING"
  };
}

function toDateTimeInputValue(isoValue: string, timezone: string): string {
  const dateValue = luxonModule.DateTime.fromISO(isoValue, { setZone: true }).setZone(timezone);
  if (!dateValue.isValid) {
    return "";
  }
  return dateValue.toFormat("yyyy-LL-dd'T'HH:mm");
}

function toApiDateTime(value: string, timezone: string): string | null {
  const parsedValue = luxonModule.DateTime.fromISO(value, { zone: timezone });
  if (!parsedValue.isValid) {
    return null;
  }
  const isoValue = parsedValue.toISO();
  if (isoValue === null) {
    return null;
  }
  return isoValue;
}

function splitLocalDateTimeInput(value: string): LocalDateTimeParts {
  const parsedValue = luxonModule.DateTime.fromISO(value);
  if (!parsedValue.isValid) {
    return {
      date: "",
      hour: "09",
      minute: "00"
    };
  }
  return {
    date: parsedValue.toFormat("yyyy-LL-dd"),
    hour: parsedValue.toFormat("HH"),
    minute: parsedValue.minute >= 30 ? "30" : "00"
  };
}

function mergeLocalDateTimeInput(
  currentValue: string,
  updates: Partial<LocalDateTimeParts>
): string {
  const currentParts = splitLocalDateTimeInput(currentValue);
  const nextDate = updates.date ?? currentParts.date;
  const nextHour = updates.hour ?? currentParts.hour;
  const nextMinute = updates.minute ?? currentParts.minute;
  if (nextDate === "") {
    return "";
  }
  return `${nextDate}T${nextHour}:${nextMinute}`;
}

function calculateEndAtFromStart(
  startAtIso: string,
  durationMinutes: number,
  timezone: string
): string | null {
  const startAtValue = luxonModule.DateTime.fromISO(startAtIso, { zone: timezone });
  if (!startAtValue.isValid) {
    return null;
  }
  const endAtValue = startAtValue.plus({ minutes: durationMinutes });
  const endAtIso = endAtValue.toISO();
  if (endAtIso === null) {
    return null;
  }
  return endAtIso;
}

function resolveDurationMinutesFromRange(
  startAtIso: string,
  endAtIso: string,
  fallbackMinutes: number
): string {
  const startAtValue = luxonModule.DateTime.fromISO(startAtIso);
  const endAtValue = luxonModule.DateTime.fromISO(endAtIso);
  if (!startAtValue.isValid || !endAtValue.isValid) {
    return String(fallbackMinutes);
  }
  const diffMinutes = Math.round(endAtValue.diff(startAtValue, "minutes").minutes);
  if (diffMinutes <= 0) {
    return String(fallbackMinutes);
  }
  return String(diffMinutes);
}

function isThirtyMinuteAligned(isoValue: string, timezone: string): boolean {
  const dateValue = luxonModule.DateTime.fromISO(isoValue, { zone: timezone });
  if (!dateValue.isValid) {
    return false;
  }
  return dateValue.minute % 30 === 0;
}

function formatCopCurrency(value: number): string {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0
  }).format(value);
}

function resolvePatientDisplayName(request: schedulingModel.SchedulingRequestSummary): string {
  const names = [request.patientFirstName, request.patientLastName]
    .map((value) => value?.trim() ?? "")
    .filter((value) => value !== "");
  if (names.length > 0) {
    return names.join(" ");
  }
  return request.whatsappUserId;
}

function resolveBookedSlot(
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

  const firstSlot = request.slots[0];
  return firstSlot ?? null;
}

export function buildCalendarSlotCandidates(params: {
  requestId: string;
  timezone: string;
  selectedDayIso: string;
  busyIntervals: BusyIntervalRange[];
  now: luxonModule.DateTime;
}): CalendarSlotCandidate[] {
  const selectedDay = luxonModule.DateTime.fromISO(params.selectedDayIso, {
    zone: params.timezone
  }).startOf("day");
  if (!selectedDay.isValid) {
    return [];
  }

  const slots: CalendarSlotCandidate[] = [];
  for (let hour = 6; hour < 22; hour += 1) {
    const startAt = selectedDay.set({
      hour,
      minute: 0,
      second: 0,
      millisecond: 0
    });
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
      isPast
    });
  }
  return slots;
}

export function AgendaPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  const nowDate = luxonModule.DateTime.now();

  const requestsQuery = reactQueryModule.useQuery({
    queryKey: schedulingRequestsQueryKey,
    queryFn: () => appContainer.schedulingUseCase.listRequests()
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

  const [activeSectionId, setActiveSectionId] = reactModule.useState<string>("APPROVALS");
  const [activeTab, setActiveTab] = reactModule.useState<schedulingModel.SchedulingRequestStatus>(
    "AWAITING_CONSULTATION_REVIEW"
  );
  const [selectedRequestId, setSelectedRequestId] = reactModule.useState<string | null>(null);
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
  const [selectedSlotsByRequestId, setSelectedSlotsByRequestId] = reactModule.useState<
    Record<string, schedulingModel.ProfessionalSlotInput[]>
  >({});
  const [professionalNotesByRequestId, setProfessionalNotesByRequestId] = reactModule.useState<
    Record<string, string>
  >({});
  const [reviewNotesByRequestId, setReviewNotesByRequestId] = reactModule.useState<
    Record<string, string>
  >({});
  const [localSubmitErrorMessage, setLocalSubmitErrorMessage] = reactModule.useState<string | null>(
    null
  );
  const [submitSuccessMessage, setSubmitSuccessMessage] = reactModule.useState<string | null>(null);
  const [patientFormState, setPatientFormState] =
    reactModule.useState<PatientFormState>(emptyPatientForm());
  const [editingPatientWhatsappUserId, setEditingPatientWhatsappUserId] = reactModule.useState<
    string | null
  >(null);
  const [patientUpdateFormState, setPatientUpdateFormState] =
    reactModule.useState<PatientUpdateFormState>(emptyPatientUpdateForm());
  const [manualAppointmentFormState, setManualAppointmentFormState] =
    reactModule.useState<ManualAppointmentFormState>(emptyManualAppointmentForm());
  const [manualAppointmentListFilter, setManualAppointmentListFilter] =
    reactModule.useState<ManualAppointmentListFilter>("SCHEDULED");
  const [editingManualAppointmentId, setEditingManualAppointmentId] = reactModule.useState<
    string | null
  >(null);
  const [manualRescheduleFormState, setManualRescheduleFormState] =
    reactModule.useState<ManualAppointmentFormState>(emptyManualAppointmentForm());
  const [bookedAppointmentFormState, setBookedAppointmentFormState] =
    reactModule.useState<BookedAppointmentFormState>(emptyBookedAppointmentForm("UTC"));
  const [manualPaymentFormState, setManualPaymentFormState] =
    reactModule.useState<PaymentFormState>(emptyPaymentForm());
  const [bookedPaymentFormState, setBookedPaymentFormState] =
    reactModule.useState<PaymentFormState>(emptyPaymentForm());
  const [financeFromDate, setFinanceFromDate] = reactModule.useState<string>("");
  const [financeToDate, setFinanceToDate] = reactModule.useState<string>("");
  const [financePaymentStatusFilter, setFinancePaymentStatusFilter] =
    reactModule.useState<FinancePaymentStatusFilter>("ALL");
  const [financePaymentMethodFilter, setFinancePaymentMethodFilter] =
    reactModule.useState<FinancePaymentMethodFilter>("ALL");
  const [financeSourceFilter, setFinanceSourceFilter] =
    reactModule.useState<FinanceSourceFilter>("ALL");
  const [financeSearchTerm, setFinanceSearchTerm] = reactModule.useState<string>("");

  const allRequests = requestsQuery.data ?? [];
  const allPatients = patientsQuery.data ?? [];
  const allManualAppointments = manualAppointmentsQuery.data ?? [];
  const requestCountByStatus = reactModule.useMemo(() => {
    const countMap = new Map<schedulingModel.SchedulingRequestStatus, number>();
    allRequests.forEach((request) => {
      const currentCount = countMap.get(request.status) ?? 0;
      countMap.set(request.status, currentCount + 1);
    });
    return countMap;
  }, [allRequests]);

  const sectionCounts = reactModule.useMemo(() => {
    const counts: Record<string, number> = {};
    agendaSections.forEach((section) => {
      if (section.id === "MANUAL_SCHEDULING") {
        counts[section.id] = allManualAppointments.filter(
          (appointment) => appointment.status === "SCHEDULED"
        ).length;
        return;
      }
      if (section.id === "FINANCE") {
        const bookedCount = allRequests.filter((request) => request.status === "BOOKED").length;
        const manualCount = allManualAppointments.filter(
          (appointment) => appointment.status === "SCHEDULED"
        ).length;
        counts[section.id] = bookedCount + manualCount;
        return;
      }
      let sectionCount = 0;
      section.statuses.forEach((statusConfig) => {
        sectionCount += requestCountByStatus.get(statusConfig.status) ?? 0;
      });
      counts[section.id] = sectionCount;
    });
    return counts;
  }, [allManualAppointments, requestCountByStatus]);

  const isApprovalSection = activeSectionId === "APPROVALS";
  const filteredRequests = reactModule.useMemo(() => {
    if (isApprovalSection) {
      const approvalStatusSet = new Set<string>(APPROVAL_STATUSES);
      return allRequests.filter((request) => approvalStatusSet.has(request.status));
    }
    return allRequests.filter((request) => request.status === activeTab);
  }, [allRequests, activeTab, isApprovalSection]);
  const isManualSchedulingSection = activeSectionId === "MANUAL_SCHEDULING";
  const isFinanceSection = activeSectionId === "FINANCE";
  const isBookedTab = activeTab === "BOOKED";
  const patientsByWhatsappUserId = reactModule.useMemo(() => {
    const map = new Map<string, patientModel.Patient>();
    allPatients.forEach((patient) => {
      map.set(patient.whatsappUserId, patient);
    });
    return map;
  }, [allPatients]);
  const sortedManualAppointments = reactModule.useMemo(() => {
    return [...allManualAppointments].sort((left, right) => {
      return left.startAt.localeCompare(right.startAt);
    });
  }, [allManualAppointments]);
  const manualAppointmentCountByStatus = reactModule.useMemo(() => {
    return {
      SCHEDULED: allManualAppointments.filter((appointment) => appointment.status === "SCHEDULED")
        .length,
      CANCELLED: allManualAppointments.filter((appointment) => appointment.status === "CANCELLED")
        .length
    };
  }, [allManualAppointments]);
  const filteredManualAppointments = reactModule.useMemo(() => {
    return sortedManualAppointments.filter(
      (appointment) => appointment.status === manualAppointmentListFilter
    );
  }, [manualAppointmentListFilter, sortedManualAppointments]);

  const handleSectionChange = (sectionId: string) => {
    setActiveSectionId(sectionId);
    setSelectedBookedItemKey(null);
    const section = agendaSections.find((s) => s.id === sectionId);
    if (section && section.statuses.length > 0) {
      const firstStatus = section.statuses[0];
      if (firstStatus) {
        setActiveTab(firstStatus.status);
      }
      setSubmitSuccessMessage(null);
      setLocalSubmitErrorMessage(null);
    }
  };

  reactModule.useEffect(() => {
    if (isBookedTab) {
      return;
    }
    if (filteredRequests.length === 0) {
      setSelectedRequestId(null);
      return;
    }
    const selectedExists = filteredRequests.some(
      (request) => request.requestId === selectedRequestId
    );
    if (!selectedExists) {
      const firstRequest = filteredRequests[0];
      if (firstRequest !== undefined) {
        setSelectedRequestId(firstRequest.requestId);
      }
    }
  }, [filteredRequests, isBookedTab, selectedRequestId]);

  const selectedRequest = allRequests.find((request) => request.requestId === selectedRequestId);
  const timezone = googleCalendarConnectionQuery.data?.professionalTimezone ?? "UTC";
  const visibleMonthStart = luxonModule.DateTime.fromObject(
    {
      year: visibleMonth.year,
      month: visibleMonth.month,
      day: 1
    },
    {
      zone: timezone
    }
  ).startOf("day");
  const visibleMonthEnd = visibleMonthStart.endOf("month");
  const monthRangeFromIso = visibleMonthStart.toISO();
  const monthRangeToIso = visibleMonthEnd.toISO();

  const availabilityQuery = reactQueryModule.useQuery({
    queryKey: ["google-calendar-availability", monthRangeFromIso, monthRangeToIso, timezone],
    enabled:
      (selectedRequest?.status === "AWAITING_CONSULTATION_REVIEW" ||
        selectedRequest?.status === "AWAITING_PATIENT_CHOICE") &&
      monthRangeFromIso !== null &&
      monthRangeToIso !== null,
    queryFn: async () => {
      if (monthRangeFromIso === null || monthRangeToIso === null) {
        throw new Error("month range is invalid");
      }
      return appContainer.schedulingUseCase.getAvailability(monthRangeFromIso, monthRangeToIso);
    }
  });

  reactModule.useEffect(() => {
    const firstDayIso = visibleMonthStart.toISODate();
    if (firstDayIso !== null) {
      setSelectedDayIso(firstDayIso);
    }
  }, [visibleMonthStart.year, visibleMonthStart.month]);

  const busyIntervals = reactModule.useMemo<BusyIntervalRange[]>(() => {
    if (availabilityQuery.data === undefined) {
      return [];
    }
    return availabilityQuery.data.busyIntervals
      .map((interval) => {
        const start = luxonModule.DateTime.fromISO(interval.startAt, { zone: timezone });
        const end = luxonModule.DateTime.fromISO(interval.endAt, { zone: timezone });
        if (!start.isValid || !end.isValid) {
          return null;
        }
        return {
          start,
          end
        };
      })
      .filter((interval): interval is BusyIntervalRange => interval !== null);
  }, [availabilityQuery.data, timezone]);

  const calendarSlots = reactModule.useMemo(() => {
    if (selectedRequest === undefined || selectedDayIso === "") {
      return [];
    }
    return buildCalendarSlotCandidates({
      requestId: selectedRequest.requestId,
      selectedDayIso,
      timezone,
      busyIntervals,
      now: luxonModule.DateTime.now().setZone(timezone)
    });
  }, [selectedRequest, selectedDayIso, timezone, busyIntervals]);

  const bookedAppointments = reactModule.useMemo<BookedAppointment[]>(() => {
    if (!isBookedTab) {
      return [];
    }
    const combinedAppointments: BookedAppointment[] = [];

    filteredRequests.forEach((request) => {
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
      const patientDisplayName = resolvePatientDisplayName(request);
      combinedAppointments.push({
        itemKey: `bot:${request.requestId}`,
        source: "BOT",
        requestId: request.requestId,
        manualAppointmentId: null,
        patientDisplayName,
        summary: patientDisplayName.trim() === "" ? "Cita bot" : `Cita bot - ${patientDisplayName}`,
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
  }, [allManualAppointments, filteredRequests, isBookedTab, patientsByWhatsappUserId, timezone]);

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

  const financeAppointments = reactModule.useMemo<FinanceAppointmentItem[]>(() => {
    const items: FinanceAppointmentItem[] = [];
    allRequests
      .filter((request) => request.status === "BOOKED")
      .forEach((request) => {
        const bookedSlot = resolveBookedSlot(request);
        if (bookedSlot === null) {
          return;
        }
        items.push({
          itemKey: `finance-bot:${request.requestId}`,
          source: "CHATBOT",
          patientDisplayName: resolvePatientDisplayName(request),
          whatsappUserId: request.whatsappUserId,
          startAt: bookedSlot.startAt,
          endAt: bookedSlot.endAt,
          timezone: bookedSlot.timezone.trim() === "" ? timezone : bookedSlot.timezone,
          paymentAmountCop: request.paymentAmountCop ?? null,
          paymentMethod: request.paymentMethod ?? null,
          paymentStatus: request.paymentStatus ?? "PENDING",
          paymentUpdatedAt: request.paymentUpdatedAt ?? null
        });
      });

    allManualAppointments
      .filter((appointment) => appointment.status === "SCHEDULED")
      .forEach((appointment) => {
        const patient = patientsByWhatsappUserId.get(appointment.patientWhatsappUserId);
        items.push({
          itemKey: `finance-manual:${appointment.appointmentId}`,
          source: "MANUAL",
          patientDisplayName:
            patient === undefined
              ? appointment.patientWhatsappUserId
              : `${patient.firstName} ${patient.lastName}`,
          whatsappUserId: appointment.patientWhatsappUserId,
          startAt: appointment.startAt,
          endAt: appointment.endAt,
          timezone: appointment.timezone.trim() === "" ? colombiaTimezone : appointment.timezone,
          paymentAmountCop: appointment.paymentAmountCop ?? null,
          paymentMethod: appointment.paymentMethod ?? null,
          paymentStatus: appointment.paymentStatus ?? "PENDING",
          paymentUpdatedAt: appointment.paymentUpdatedAt ?? null
        });
      });

    return items.sort((left, right) => left.startAt.localeCompare(right.startAt));
  }, [allManualAppointments, allRequests, patientsByWhatsappUserId, timezone]);

  const filteredFinanceAppointments = reactModule.useMemo(() => {
    const normalizedSearchTerm = financeSearchTerm.trim().toLowerCase();
    return financeAppointments.filter((appointment) => {
      const startDate = luxonModule.DateTime.fromISO(appointment.startAt, {
        zone: appointment.timezone
      }).toISODate();
      if (startDate === null) {
        return false;
      }
      if (financeFromDate !== "" && startDate < financeFromDate) {
        return false;
      }
      if (financeToDate !== "" && startDate > financeToDate) {
        return false;
      }
      if (
        financePaymentStatusFilter !== "ALL" &&
        appointment.paymentStatus !== financePaymentStatusFilter
      ) {
        return false;
      }
      if (
        financePaymentMethodFilter !== "ALL" &&
        appointment.paymentMethod !== financePaymentMethodFilter
      ) {
        return false;
      }
      if (financeSourceFilter !== "ALL" && appointment.source !== financeSourceFilter) {
        return false;
      }
      if (normalizedSearchTerm === "") {
        return true;
      }
      const patientName = appointment.patientDisplayName.toLowerCase();
      const whatsappUserId = appointment.whatsappUserId.toLowerCase();
      return (
        patientName.includes(normalizedSearchTerm) || whatsappUserId.includes(normalizedSearchTerm)
      );
    });
  }, [
    financeAppointments,
    financeFromDate,
    financePaymentMethodFilter,
    financePaymentStatusFilter,
    financeSearchTerm,
    financeSourceFilter,
    financeToDate
  ]);

  const financeMetrics = reactModule.useMemo(() => {
    const totalAppointments = filteredFinanceAppointments.length;
    const pendingAppointments = filteredFinanceAppointments.filter(
      (appointment) => appointment.paymentStatus === "PENDING"
    ).length;
    const paidAppointments = filteredFinanceAppointments.filter(
      (appointment) => appointment.paymentStatus === "PAID"
    ).length;
    const totalPaidCop = filteredFinanceAppointments.reduce((accumulator, appointment) => {
      if (appointment.paymentStatus !== "PAID" || appointment.paymentAmountCop === null) {
        return accumulator;
      }
      return accumulator + appointment.paymentAmountCop;
    }, 0);
    return {
      totalAppointments,
      pendingAppointments,
      paidAppointments,
      totalPaidCop
    };
  }, [filteredFinanceAppointments]);

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
  }, [bookedAppointments, isBookedTab, selectedBookedAppointment, selectedDayIso]);
  const selectedBookedBotRequest =
    selectedBookedAppointment?.source === "BOT" ? selectedBookedAppointment.request : null;
  reactModule.useEffect(() => {
    if (selectedBookedAppointment?.source !== "BOT" || selectedBookedBotRequest === null) {
      setBookedAppointmentFormState(emptyBookedAppointmentForm(timezone));
      return;
    }
    setBookedAppointmentFormState({
      startAt: toDateTimeInputValue(selectedBookedAppointment.startAt.toISO() ?? "", timezone),
      endAt: toDateTimeInputValue(selectedBookedAppointment.endAt.toISO() ?? "", timezone),
      timezone,
      eventSummary:
        selectedBookedAppointment.patientDisplayName.trim() === ""
          ? "Cita"
          : `Cita - ${selectedBookedAppointment.patientDisplayName}`,
      cancelReason: ""
    });
  }, [selectedBookedAppointment, selectedBookedBotRequest, timezone]);
  reactModule.useEffect(() => {
    if (
      selectedBookedAppointment?.source !== "MANUAL" ||
      selectedBookedAppointment.manualAppointment === null
    ) {
      setManualPaymentFormState(emptyPaymentForm());
      return;
    }
    setManualPaymentFormState({
      paymentAmountCop:
        selectedBookedAppointment.manualAppointment.paymentAmountCop == null
          ? ""
          : String(selectedBookedAppointment.manualAppointment.paymentAmountCop),
      paymentMethod: selectedBookedAppointment.manualAppointment.paymentMethod ?? "CASH",
      paymentStatus: selectedBookedAppointment.manualAppointment.paymentStatus ?? "PENDING"
    });
  }, [selectedBookedAppointment]);
  reactModule.useEffect(() => {
    if (selectedBookedBotRequest === null) {
      setBookedPaymentFormState(emptyPaymentForm());
      return;
    }
    setBookedPaymentFormState({
      paymentAmountCop:
        selectedBookedBotRequest.paymentAmountCop == null
          ? ""
          : String(selectedBookedBotRequest.paymentAmountCop),
      paymentMethod: selectedBookedBotRequest.paymentMethod ?? "CASH",
      paymentStatus: selectedBookedBotRequest.paymentStatus ?? "PENDING"
    });
  }, [selectedBookedBotRequest]);

  const selectedSlots =
    selectedRequest !== undefined
      ? (selectedSlotsByRequestId[selectedRequest.requestId] ?? [])
      : [];
  const selectedSlotIdSet = new Set(selectedSlots.map((slot) => slot.slotId));
  const currentProfessionalNote =
    selectedRequest !== undefined
      ? (professionalNotesByRequestId[selectedRequest.requestId] ?? "")
      : "";
  const currentReviewNote =
    selectedRequest !== undefined ? (reviewNotesByRequestId[selectedRequest.requestId] ?? "") : "";
  const manualCreateStartParts = splitLocalDateTimeInput(manualAppointmentFormState.startAt);
  const manualRescheduleStartParts = splitLocalDateTimeInput(manualRescheduleFormState.startAt);

  const submitSlotsMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      slots: schedulingModel.ProfessionalSlotInput[];
      professionalNote: string | null;
    }) => {
      return appContainer.schedulingUseCase.submitProfessionalSlots(
        payload.request.conversationId,
        payload.request.requestId,
        {
          slots: payload.slots,
          professionalNote: payload.professionalNote
        }
      );
    },
    onSuccess: (result, payload) => {
      setSubmitSuccessMessage(result.assistantText);
      setLocalSubmitErrorMessage(null);
      setSelectedSlotsByRequestId((currentValue) => ({
        ...currentValue,
        [payload.request.requestId]: []
      }));
      queryClient.setQueryData<schedulingModel.SchedulingRequestSummary[]>(
        schedulingRequestsQueryKey,
        (currentValue) => {
          if (currentValue === undefined) {
            return currentValue;
          }
          return currentValue.map((request) => {
            if (request.requestId !== payload.request.requestId) {
              return request;
            }
            return {
              ...request,
              status: "AWAITING_PATIENT_CHOICE",
              updatedAt: luxonModule.DateTime.now().toISO() ?? request.updatedAt,
              professionalNote: payload.professionalNote,
              slots: payload.slots.map((slot) => ({
                slotId: slot.slotId,
                startAt: slot.startAt,
                endAt: slot.endAt,
                timezone: slot.timezone,
                status: "PROPOSED"
              }))
            };
          });
        }
      );
      setActiveTab("AWAITING_PATIENT_CHOICE");
    }
  });

  const resolveConsultationReviewMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      decision: "REQUEST_MORE_INFO" | "REJECT";
      professionalNote: string | null;
    }) => {
      return appContainer.schedulingUseCase.resolveConsultationReview(
        payload.request.conversationId,
        payload.request.requestId,
        {
          decision: payload.decision,
          professionalNote: payload.professionalNote
        }
      );
    },
    onSuccess: (result, payload) => {
      setSubmitSuccessMessage(result.assistantText);
      setLocalSubmitErrorMessage(null);
      queryClient.setQueryData<schedulingModel.SchedulingRequestSummary[]>(
        schedulingRequestsQueryKey,
        (currentValue) => {
          if (currentValue === undefined) {
            return currentValue;
          }
          return currentValue.map((request) => {
            if (request.requestId !== payload.request.requestId) {
              return request;
            }
            return {
              ...request,
              status: result.status,
              updatedAt: luxonModule.DateTime.now().toISO() ?? request.updatedAt,
              professionalNote: payload.professionalNote
            };
          });
        }
      );
      setActiveTab(result.status);
    }
  });

  const resolvePaymentReviewMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      decision: "APPROVE" | "SEND_REMINDER";
      professionalNote: string | null;
    }) => {
      return appContainer.schedulingUseCase.resolvePaymentReview(
        payload.request.conversationId,
        payload.request.requestId,
        {
          decision: payload.decision,
          professionalNote: payload.professionalNote
        }
      );
    },
    onSuccess: (result, payload) => {
      setSubmitSuccessMessage(result.assistantText);
      setLocalSubmitErrorMessage(null);
      queryClient.setQueryData<schedulingModel.SchedulingRequestSummary[]>(
        schedulingRequestsQueryKey,
        (currentValue) => {
          if (currentValue === undefined) {
            return currentValue;
          }
          return currentValue.map((request) => {
            if (request.requestId !== payload.request.requestId) {
              return request;
            }
            return {
              ...request,
              status: result.status,
              updatedAt: luxonModule.DateTime.now().toISO() ?? request.updatedAt,
              professionalNote: payload.professionalNote
            };
          });
        }
      );
      setActiveTab(result.status);
    }
  });

  const createPatientMutation = reactQueryModule.useMutation({
    mutationFn: (payload: patientModel.CreatePatientInput) => {
      return appContainer.patientUseCase.createPatient(payload);
    },
    onSuccess: async () => {
      setSubmitSuccessMessage("Paciente creado correctamente.");
      setLocalSubmitErrorMessage(null);
      setPatientFormState(emptyPatientForm());
      await queryClient.invalidateQueries({ queryKey: patientsQueryKey });
    }
  });

  const updatePatientMutation = reactQueryModule.useMutation({
    mutationFn: (payload: { whatsappUserId: string; input: patientModel.UpdatePatientInput }) => {
      return appContainer.patientUseCase.updatePatient(payload.whatsappUserId, payload.input);
    },
    onSuccess: async () => {
      setSubmitSuccessMessage("Paciente actualizado correctamente.");
      setLocalSubmitErrorMessage(null);
      setEditingPatientWhatsappUserId(null);
      setPatientUpdateFormState(emptyPatientUpdateForm());
      await queryClient.invalidateQueries({ queryKey: patientsQueryKey });
    }
  });

  const removePatientMutation = reactQueryModule.useMutation({
    mutationFn: (whatsappUserId: string) =>
      appContainer.patientUseCase.removePatient(whatsappUserId),
    onSuccess: async () => {
      setSubmitSuccessMessage("Paciente eliminado correctamente.");
      setLocalSubmitErrorMessage(null);
      setEditingPatientWhatsappUserId(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: patientsQueryKey }),
        queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey }),
        queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey })
      ]);
    }
  });

  const createManualAppointmentMutation = reactQueryModule.useMutation({
    mutationFn: (payload: manualAppointmentModel.CreateManualAppointmentInput) => {
      return appContainer.manualAppointmentUseCase.createAppointment(payload);
    },
    onSuccess: async () => {
      setSubmitSuccessMessage("Cita manual creada correctamente.");
      setLocalSubmitErrorMessage(null);
      setManualAppointmentFormState(emptyManualAppointmentForm());
      await queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey });
    }
  });

  const rescheduleManualAppointmentMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      appointmentId: string;
      input: manualAppointmentModel.RescheduleManualAppointmentInput;
    }) => {
      return appContainer.manualAppointmentUseCase.rescheduleAppointment(
        payload.appointmentId,
        payload.input
      );
    },
    onSuccess: async () => {
      setSubmitSuccessMessage("Cita manual reprogramada correctamente.");
      setLocalSubmitErrorMessage(null);
      setEditingManualAppointmentId(null);
      await queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey });
    }
  });

  const cancelManualAppointmentMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      appointmentId: string;
      input: manualAppointmentModel.CancelManualAppointmentInput;
    }) => {
      return appContainer.manualAppointmentUseCase.cancelAppointment(
        payload.appointmentId,
        payload.input
      );
    },
    onSuccess: async () => {
      setSubmitSuccessMessage("Cita manual cancelada correctamente.");
      setLocalSubmitErrorMessage(null);
      setEditingManualAppointmentId(null);
      await queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey });
    }
  });

  const updateManualPaymentMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      appointmentId: string;
      input: manualAppointmentModel.UpdateManualAppointmentPaymentInput;
    }) => {
      return appContainer.manualAppointmentUseCase.updatePayment(
        payload.appointmentId,
        payload.input
      );
    },
    onSuccess: async () => {
      setSubmitSuccessMessage("Pago de cita manual actualizado.");
      setLocalSubmitErrorMessage(null);
      await queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey });
    }
  });

  const rescheduleBookedSlotMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      requestId: string;
      input: schedulingModel.RescheduleBookedSlotInput;
    }) => {
      return appContainer.schedulingUseCase.rescheduleBookedSlot(payload.requestId, payload.input);
    },
    onSuccess: async () => {
      setSubmitSuccessMessage("Cita del chatbot reprogramada correctamente.");
      setLocalSubmitErrorMessage(null);
      await queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey });
    }
  });

  const cancelBookedSlotMutation = reactQueryModule.useMutation({
    mutationFn: (payload: { requestId: string; input: schedulingModel.CancelBookedSlotInput }) => {
      return appContainer.schedulingUseCase.cancelBookedSlot(payload.requestId, payload.input);
    },
    onSuccess: async () => {
      setSubmitSuccessMessage("Cita del chatbot cancelada correctamente.");
      setLocalSubmitErrorMessage(null);
      await queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey });
    }
  });

  const updateBookedPaymentMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      requestId: string;
      input: schedulingModel.UpdateBookedSlotPaymentInput;
    }) => {
      return appContainer.schedulingUseCase.updateBookedPayment(payload.requestId, payload.input);
    },
    onSuccess: async () => {
      setSubmitSuccessMessage("Pago de cita chatbot actualizado.");
      setLocalSubmitErrorMessage(null);
      await queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey });
    }
  });

  const submitErrorMessage = uiErrorModule.resolveUiErrorMessage([
    submitSlotsMutation.error,
    resolveConsultationReviewMutation.error,
    resolvePaymentReviewMutation.error,
    createPatientMutation.error,
    updatePatientMutation.error,
    removePatientMutation.error,
    createManualAppointmentMutation.error,
    rescheduleManualAppointmentMutation.error,
    cancelManualAppointmentMutation.error,
    updateManualPaymentMutation.error,
    rescheduleBookedSlotMutation.error,
    cancelBookedSlotMutation.error,
    updateBookedPaymentMutation.error
  ]);
  const loadingErrorMessage = uiErrorModule.resolveUiErrorMessage([
    requestsQuery.error,
    googleCalendarConnectionQuery.error,
    availabilityQuery.error,
    patientsQuery.error,
    manualAppointmentsQuery.error
  ]);

  const firstWeekdayOffset = visibleMonthStart.weekday % 7;
  const monthDays = visibleMonthStart.daysInMonth ?? 0;
  const dayGrid: (luxonModule.DateTime | null)[] = [];
  for (let index = 0; index < firstWeekdayOffset; index += 1) {
    dayGrid.push(null);
  }
  for (let day = 1; day <= monthDays; day += 1) {
    dayGrid.push(visibleMonthStart.set({ day }));
  }

  return (
    <appShellModule.AppShell>
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-brand-ink">Agenda profesional</h2>
            <p className="text-sm text-slate-600">
              Gestiona solicitudes y envía múltiples slots de 60 minutos.
            </p>
          </div>
          <button
            className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
            onClick={() => {
              void queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey });
              void queryClient.invalidateQueries({ queryKey: googleCalendarConnectionQueryKey });
              void queryClient.invalidateQueries({ queryKey: patientsQueryKey });
              void queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey });
              void queryClient.invalidateQueries({
                queryKey: ["google-calendar-availability"]
              });
            }}
            type="button"
          >
            Refrescar
          </button>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex gap-1 overflow-x-auto border-b border-border-subtle pb-1">
            {agendaSections.map((section) => {
              const isActive = activeSectionId === section.id;
              const count = sectionCounts[section.id] ?? 0;
              return (
                <button
                  className={[
                    "relative -mb-px shrink-0 whitespace-nowrap px-3 py-3 text-sm font-semibold transition-colors sm:px-6",
                    isActive
                      ? "border-b-2 border-brand-teal text-brand-teal"
                      : "text-slate-500 hover:border-b-2 hover:border-slate-300 hover:text-slate-700"
                  ].join(" ")}
                  key={section.id}
                  onClick={() => handleSectionChange(section.id)}
                  type="button"
                >
                  {section.label}
                  {count > 0 ? (
                    <span
                      className={[
                        "ml-2 rounded-full px-2 py-0.5 text-xs",
                        isActive
                          ? "bg-brand-accent-light text-brand-teal"
                          : "bg-slate-100 text-slate-600"
                      ].join(" ")}
                    >
                      {count}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>

          {!isApprovalSection &&
          (agendaSections.find((s) => s.id === activeSectionId)?.statuses.length ?? 0) > 0 ? (
            <div className="flex flex-wrap gap-2">
              {agendaSections
                .find((s) => s.id === activeSectionId)
                ?.statuses.map((tab) => (
                  <button
                    className={[
                      "rounded-md border px-3 py-2 text-sm font-semibold",
                      activeTab === tab.status
                        ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                        : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                    ].join(" ")}
                    key={tab.status}
                    onClick={() => {
                      setActiveTab(tab.status);
                      setSelectedBookedItemKey(null);
                      setSubmitSuccessMessage(null);
                      setLocalSubmitErrorMessage(null);
                    }}
                    type="button"
                  >
                    {tab.label} ({requestCountByStatus.get(tab.status) ?? 0})
                  </button>
                ))}
            </div>
          ) : null}
        </div>
      </section>

      {!isManualSchedulingSection && !isFinanceSection ? (
        <section
          className={[
            "mt-4 grid gap-4",
            isBookedTab
              ? "lg:grid-cols-[520px_minmax(0,1fr)]"
              : "lg:grid-cols-[320px_minmax(0,1fr)]"
          ].join(" ")}
        >
          {isBookedTab ? (
            <article className="rounded-xl border border-border-subtle bg-white shadow-card">
              <header className="border-b border-border-subtle p-4">
                <h3 className="text-base font-semibold">Calendario de citas agendadas</h3>
                <p className="text-xs text-slate-500">
                  Integra citas del chatbot y manuales. Haz click para ver el detalle completo.
                </p>
              </header>
              <div className="space-y-3 p-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm font-semibold text-brand-ink">
                    {visibleMonthStart.toFormat("LLLL yyyy")}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="rounded-lg border border-border-subtle px-3 py-1 text-sm text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                      onClick={() => {
                        const previous = visibleMonthStart.minus({ months: 1 });
                        setVisibleMonth({
                          year: previous.year,
                          month: previous.month as luxonModule.MonthNumbers
                        });
                      }}
                      type="button"
                    >
                      Anterior
                    </button>
                    <button
                      className="rounded-lg border border-border-subtle px-3 py-1 text-sm text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                      onClick={() => {
                        const next = visibleMonthStart.plus({ months: 1 });
                        setVisibleMonth({
                          year: next.year,
                          month: next.month as luxonModule.MonthNumbers
                        });
                      }}
                      type="button"
                    >
                      Siguiente
                    </button>
                  </div>
                </div>

                <div className="overflow-x-auto pb-1">
                  <div className="min-w-[42rem]">
                    <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-600">
                      {weekDayLabels.map((label) => (
                        <span key={label}>{label}</span>
                      ))}
                    </div>
                    <div className="grid grid-cols-7 gap-1">
                      {dayGrid.map((dateCell, index) => {
                        if (dateCell === null) {
                          return (
                            <div
                              className="min-h-32 rounded-md bg-slate-50"
                              key={`empty-${index}`}
                            />
                          );
                        }
                        const isoDate = dateCell.toISODate();
                        const dayAppointments =
                          isoDate === null ? [] : (bookedAppointmentsByDay.get(isoDate) ?? []);
                        const isSelectedDay = isoDate === selectedDayIso;
                        return (
                          <div
                            className={[
                              "min-h-32 rounded-md border p-1.5",
                              isSelectedDay
                                ? "border-brand-teal bg-brand-accent-light/40"
                                : "border-slate-200 bg-white"
                            ].join(" ")}
                            key={dateCell.toISODate() ?? `day-${dateCell.day}-${index}`}
                          >
                            <button
                              className={[
                                "w-full rounded px-1 text-left text-xs font-semibold",
                                isSelectedDay
                                  ? "bg-brand-accent-light text-brand-teal"
                                  : "text-slate-700 hover:bg-slate-100"
                              ].join(" ")}
                              onClick={() => {
                                if (isoDate === null) {
                                  return;
                                }
                                setSelectedDayIso(isoDate);
                                const firstAppointment = dayAppointments[0];
                                if (firstAppointment !== undefined) {
                                  setSelectedBookedItemKey(firstAppointment.itemKey);
                                  setSelectedRequestId(firstAppointment.requestId);
                                }
                              }}
                              type="button"
                            >
                              {dateCell.day}
                            </button>

                            <div className="mt-1 space-y-1">
                              {dayAppointments.slice(0, 2).map((appointment) => {
                                const isSelectedAppointment =
                                  appointment.itemKey === selectedBookedItemKey;
                                return (
                                  <button
                                    className={[
                                      "w-full rounded border px-1.5 py-1.5 text-left text-[11px]",
                                      isSelectedAppointment
                                        ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                                    ].join(" ")}
                                    key={appointment.itemKey}
                                    onClick={() => {
                                      setSelectedDayIso(appointment.dayIso);
                                      setSelectedBookedItemKey(appointment.itemKey);
                                      setSelectedRequestId(appointment.requestId);
                                      setSubmitSuccessMessage(null);
                                      setLocalSubmitErrorMessage(null);
                                    }}
                                    title={`${appointment.startAt.toFormat(
                                      "HH:mm"
                                    )} - ${appointment.endAt.toFormat("HH:mm")} | ${
                                      appointment.patientDisplayName
                                    } | ${appointment.source === "MANUAL" ? "Manual" : "Chatbot"}`}
                                    type="button"
                                  >
                                    <span className="block font-semibold leading-tight">
                                      {appointment.startAt.toFormat("HH:mm")} -{" "}
                                      {appointment.endAt.toFormat("HH:mm")}
                                    </span>
                                  </button>
                                );
                              })}
                              {dayAppointments.length > 2 ? (
                                <p className="px-1 text-[11px] font-semibold text-slate-500">
                                  +{dayAppointments.length - 2} más
                                </p>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                <section className="rounded-lg border border-border-subtle p-3">
                  <h4 className="text-sm font-semibold text-brand-ink">
                    {selectedDayIso !== ""
                      ? `Citas del ${luxonModule.DateTime.fromISO(selectedDayIso, {
                          zone: timezone
                        }).toFormat("dd LLL yyyy")}`
                      : "Citas del día seleccionado"}
                  </h4>
                  {selectedDayAppointments.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-500">No hay citas para este día.</p>
                  ) : (
                    <div className="mt-2 space-y-2">
                      {selectedDayAppointments.map((appointment) => {
                        const isSelectedAppointment = appointment.itemKey === selectedBookedItemKey;
                        return (
                          <button
                            className={[
                              "w-full rounded-md border px-3 py-2 text-left",
                              isSelectedAppointment
                                ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                                : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                            ].join(" ")}
                            key={`day-${appointment.itemKey}`}
                            onClick={() => {
                              setSelectedDayIso(appointment.dayIso);
                              setSelectedBookedItemKey(appointment.itemKey);
                              setSelectedRequestId(appointment.requestId);
                              setSubmitSuccessMessage(null);
                              setLocalSubmitErrorMessage(null);
                            }}
                            type="button"
                          >
                            <p className="text-sm font-semibold">
                              {appointment.startAt.toFormat("HH:mm")} -{" "}
                              {appointment.endAt.toFormat("HH:mm")}
                            </p>
                            <p className="text-xs">{appointment.patientDisplayName}</p>
                            <p className="text-[11px] uppercase text-slate-500">
                              {appointment.source === "MANUAL" ? "Manual" : "Chatbot"}
                            </p>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </section>

                <p className="text-xs text-slate-500">Zona horaria de visualización: {timezone}</p>
              </div>
            </article>
          ) : (
            <article className="rounded-xl border border-border-subtle bg-white shadow-card">
              <header className="border-b border-border-subtle p-4">
                <h3 className="text-base font-semibold">Solicitudes</h3>
                <p className="text-xs text-slate-500">
                  {isApprovalSection
                    ? `${filteredRequests.length} solicitudes pendientes`
                    : `Estado actual: ${activeTab}`}
                </p>
              </header>
              <div className="max-h-[calc(100vh-12rem)] space-y-2 overflow-auto p-3">
                {requestsQuery.isLoading ? (
                  <p className="text-sm text-slate-500">Cargando...</p>
                ) : null}
                {filteredRequests.length === 0 ? (
                  <p className="text-sm text-slate-500">No hay solicitudes en este estado.</p>
                ) : null}
                {filteredRequests.map((request) => {
                  const isSelected = request.requestId === selectedRequestId;
                  const statusConfig = approvalStatusLabels[request.status];
                  return (
                    <button
                      className={[
                        "w-full rounded-lg border p-3 text-left",
                        isSelected
                          ? "border-brand-teal bg-brand-accent-light"
                          : "border-slate-200 bg-white hover:border-slate-300"
                      ].join(" ")}
                      key={request.requestId}
                      onClick={() => {
                        setSelectedRequestId(request.requestId);
                        setSubmitSuccessMessage(null);
                        setLocalSubmitErrorMessage(null);
                      }}
                      type="button"
                    >
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <p className="truncate text-sm font-semibold text-brand-ink">
                          {resolvePatientDisplayName(request)}
                        </p>
                        <statusBadgeModule.StatusBadge
                          label={statusConfig?.label ?? request.status}
                          tone={statusConfig?.tone ?? "neutral"}
                        />
                      </div>
                      {request.consultationReason !== null ? (
                        <p className="truncate text-xs text-slate-600">
                          {request.consultationReason}
                        </p>
                      ) : null}
                      <p className="mt-1 text-xs text-slate-500">
                        {dateUtilsModule.formatDateTime(request.updatedAt)}
                      </p>
                    </button>
                  );
                })}
              </div>
            </article>
          )}

          <article className="space-y-4 rounded-xl border border-border-subtle bg-white shadow-card p-4">
            {isBookedTab &&
            selectedBookedAppointment !== null &&
            selectedBookedAppointment.source === "MANUAL" ? (
              <section className="space-y-3">
                <h4 className="text-sm font-semibold text-brand-ink">Detalle cita manual</h4>
                <div className="rounded-lg border border-border-subtle p-3 text-xs text-slate-700">
                  <p>
                    <strong>ID:</strong> {selectedBookedAppointment.manualAppointmentId}
                  </p>
                  <p>
                    <strong>Paciente:</strong> {selectedBookedAppointment.patientDisplayName}
                  </p>
                  <p>
                    <strong>Resumen:</strong> {selectedBookedAppointment.summary}
                  </p>
                  <p>
                    <strong>Horario:</strong>{" "}
                    {selectedBookedAppointment.startAt.toFormat("dd LLL yyyy HH:mm")} -{" "}
                    {selectedBookedAppointment.endAt.toFormat("HH:mm")}
                  </p>
                  <p>
                    <strong>Origen:</strong> Agendamiento manual
                  </p>
                </div>
                <div className="rounded-lg border border-border-subtle p-3">
                  <h5 className="text-sm font-semibold text-brand-ink">Pago de cita</h5>
                  <div className="mt-3 grid gap-3 md:grid-cols-3">
                    <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Valor (COP)
                      <input
                        className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                        min={1}
                        onChange={(event) => {
                          setManualPaymentFormState((currentValue) => ({
                            ...currentValue,
                            paymentAmountCop: event.target.value
                          }));
                        }}
                        type="number"
                        value={manualPaymentFormState.paymentAmountCop}
                      />
                    </label>
                    <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Categoría
                      <select
                        className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                        onChange={(event) => {
                          setManualPaymentFormState((currentValue) => ({
                            ...currentValue,
                            paymentMethod: event.target.value as "CASH" | "TRANSFER"
                          }));
                        }}
                        value={manualPaymentFormState.paymentMethod}
                      >
                        <option value="CASH">Efectivo</option>
                        <option value="TRANSFER">Transferencia</option>
                      </select>
                    </label>
                    <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Estado
                      <select
                        className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                        onChange={(event) => {
                          setManualPaymentFormState((currentValue) => ({
                            ...currentValue,
                            paymentStatus: event.target.value as "PENDING" | "PAID"
                          }));
                        }}
                        value={manualPaymentFormState.paymentStatus}
                      >
                        <option value="PENDING">Pendiente por pago</option>
                        <option value="PAID">Pagada</option>
                      </select>
                    </label>
                  </div>
                  <div className="mt-3">
                    <button
                      className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={updateManualPaymentMutation.isPending}
                      onClick={() => {
                        if (selectedBookedAppointment.manualAppointmentId === null) {
                          return;
                        }
                        const paymentAmountCop = Number.parseInt(
                          manualPaymentFormState.paymentAmountCop,
                          10
                        );
                        if (Number.isNaN(paymentAmountCop) || paymentAmountCop <= 0) {
                          setLocalSubmitErrorMessage("El valor del pago debe ser mayor a cero.");
                          return;
                        }
                        setLocalSubmitErrorMessage(null);
                        setSubmitSuccessMessage(null);
                        updateManualPaymentMutation.mutate({
                          appointmentId: selectedBookedAppointment.manualAppointmentId,
                          input: {
                            paymentAmountCop,
                            paymentMethod: manualPaymentFormState.paymentMethod,
                            paymentStatus: manualPaymentFormState.paymentStatus
                          }
                        });
                      }}
                      type="button"
                    >
                      {updateManualPaymentMutation.isPending
                        ? "Guardando pago..."
                        : "Guardar pago manual"}
                    </button>
                  </div>
                </div>
              </section>
            ) : selectedRequest === undefined ? (
              <p className="text-sm text-slate-500">
                {isBookedTab
                  ? "Selecciona una cita en el calendario para ver todos los detalles."
                  : "Selecciona una solicitud para ver detalle y gestionar slots."}
              </p>
            ) : (
              <>
                <section className="rounded-lg border border-border-subtle p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-brand-ink">
                      Información del paciente
                    </h4>
                    <statusBadgeModule.StatusBadge
                      label={
                        approvalStatusLabels[selectedRequest.status]?.label ??
                        selectedRequest.status
                      }
                      tone={approvalStatusLabels[selectedRequest.status]?.tone ?? "neutral"}
                    />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2 text-sm text-slate-700">
                      <p>
                        <span className="font-semibold text-slate-500">Nombre</span>
                        <br />
                        {resolvePatientDisplayName(selectedRequest)}
                      </p>
                      <p>
                        <span className="font-semibold text-slate-500">Motivo</span>
                        <br />
                        {selectedRequest.consultationReason ?? "-"}
                      </p>
                      {selectedRequest.consultationDetails !== null ? (
                        <p>
                          <span className="font-semibold text-slate-500">Detalles</span>
                          <br />
                          {selectedRequest.consultationDetails}
                        </p>
                      ) : null}
                    </div>
                    <div className="space-y-2 text-sm text-slate-700">
                      <p>
                        <span className="font-semibold text-slate-500">Teléfono</span>
                        <br />
                        {selectedRequest.whatsappUserId}
                      </p>
                      {selectedRequest.patientLocation !== null ? (
                        <p>
                          <span className="font-semibold text-slate-500">Ubicación</span>
                          <br />
                          {selectedRequest.patientLocation}
                        </p>
                      ) : null}
                      {selectedRequest.appointmentModality !== null ? (
                        <p>
                          <span className="font-semibold text-slate-500">Modalidad</span>
                          <br />
                          {selectedRequest.appointmentModality}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  {selectedRequest.patientPreferenceNote !== null ? (
                    <div className="mt-3 rounded-md bg-slate-50 p-3">
                      <p className="text-xs font-semibold text-slate-500">
                        Preferencias del paciente
                      </p>
                      <p className="mt-1 text-sm text-slate-700">
                        {selectedRequest.patientPreferenceNote}
                      </p>
                    </div>
                  ) : null}
                  {selectedRequest.rejectionSummary !== null ? (
                    <div className="mt-2 rounded-md bg-red-50 p-3">
                      <p className="text-xs font-semibold text-red-600">Resumen rechazo</p>
                      <p className="mt-1 text-sm text-red-700">
                        {selectedRequest.rejectionSummary}
                      </p>
                    </div>
                  ) : null}
                  {isBookedTab && selectedBookedAppointment !== null ? (
                    <div className="mt-3 rounded-md bg-brand-accent-light p-3">
                      <p className="text-xs font-semibold text-brand-teal">Cita agendada</p>
                      <p className="mt-1 text-sm text-brand-ink">
                        {selectedBookedAppointment.startAt.toFormat("dd LLL yyyy HH:mm")} -{" "}
                        {selectedBookedAppointment.endAt.toFormat("HH:mm")}
                      </p>
                    </div>
                  ) : null}
                </section>

                {selectedRequest.status === "AWAITING_CONSULTATION_REVIEW" ||
                selectedRequest.status === "AWAITING_PATIENT_CHOICE" ? (
                  <>
                    <section className="rounded-lg border border-border-subtle p-3">
                      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <h4 className="text-sm font-semibold text-brand-ink">
                          Calendario ({timezone}) - {visibleMonthStart.toFormat("LLLL yyyy")}
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          <button
                            className="rounded-lg border border-border-subtle px-3 py-1 text-sm text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                            onClick={() => {
                              const previous = visibleMonthStart.minus({ months: 1 });
                              setVisibleMonth({
                                year: previous.year,
                                month: previous.month as luxonModule.MonthNumbers
                              });
                            }}
                            type="button"
                          >
                            Anterior
                          </button>
                          <button
                            className="rounded-lg border border-border-subtle px-3 py-1 text-sm text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                            onClick={() => {
                              const next = visibleMonthStart.plus({ months: 1 });
                              setVisibleMonth({
                                year: next.year,
                                month: next.month as luxonModule.MonthNumbers
                              });
                            }}
                            type="button"
                          >
                            Siguiente
                          </button>
                        </div>
                      </div>

                      <div className="overflow-x-auto pb-1">
                        <div className="min-w-[22rem]">
                          <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-600">
                            {weekDayLabels.map((label) => (
                              <span key={label}>{label}</span>
                            ))}
                          </div>
                          <div className="mt-2 grid grid-cols-7 gap-1">
                            {dayGrid.map((dateCell, index) => {
                              if (dateCell === null) {
                                return (
                                  <div
                                    className="h-10 rounded-md bg-slate-50"
                                    key={`empty-${index}`}
                                  />
                                );
                              }
                              const isoDate = dateCell.toISODate();
                              const isSelected = isoDate === selectedDayIso;
                              return (
                                <button
                                  className={[
                                    "h-10 rounded-md border text-sm",
                                    isSelected
                                      ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                                  ].join(" ")}
                                  key={dateCell.toISODate() ?? `day-${dateCell.day}-${index}`}
                                  onClick={() => {
                                    if (isoDate !== null) {
                                      setSelectedDayIso(isoDate);
                                    }
                                  }}
                                  type="button"
                                >
                                  {dateCell.day}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                      {availabilityQuery.isLoading ? (
                        <p className="mt-3 text-xs text-slate-500">
                          Cargando disponibilidad del mes...
                        </p>
                      ) : null}
                    </section>

                    <section className="rounded-lg border border-border-subtle p-3">
                      <h4 className="text-sm font-semibold text-brand-ink">
                        Slots de 60 min (06:00 a 22:00)
                      </h4>
                      <p className="mt-1 text-xs text-slate-500">
                        Día seleccionado: {selectedDayIso !== "" ? selectedDayIso : "-"}
                      </p>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                        {calendarSlots.map((slot) => {
                          const isSelected = selectedSlotIdSet.has(slot.slotId);
                          const isDisabled = slot.isBusy || slot.isPast;
                          const slotStartText = luxonModule.DateTime.fromISO(slot.startAt, {
                            zone: timezone
                          }).toFormat("HH:mm");
                          const slotEndText = luxonModule.DateTime.fromISO(slot.endAt, {
                            zone: timezone
                          }).toFormat("HH:mm");
                          return (
                            <button
                              className={[
                                "rounded-md border px-3 py-2 text-left text-sm",
                                isDisabled
                                  ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                                  : isSelected
                                    ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                                    : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                              ].join(" ")}
                              disabled={isDisabled}
                              key={slot.slotId}
                              onClick={() => {
                                if (selectedRequest === undefined) {
                                  return;
                                }
                                setSelectedSlotsByRequestId((currentValue) => {
                                  const currentRequestSlots =
                                    currentValue[selectedRequest.requestId] ?? [];
                                  const slotExists = currentRequestSlots.some(
                                    (currentSlot) => currentSlot.slotId === slot.slotId
                                  );
                                  const nextRequestSlots = slotExists
                                    ? currentRequestSlots.filter(
                                        (currentSlot) => currentSlot.slotId !== slot.slotId
                                      )
                                    : [
                                        ...currentRequestSlots,
                                        {
                                          slotId: slot.slotId,
                                          startAt: slot.startAt,
                                          endAt: slot.endAt,
                                          timezone: slot.timezone
                                        }
                                      ].sort((left, right) =>
                                        left.startAt.localeCompare(right.startAt)
                                      );
                                  return {
                                    ...currentValue,
                                    [selectedRequest.requestId]: nextRequestSlots
                                  };
                                });
                              }}
                              type="button"
                            >
                              <p className="font-semibold">
                                {slotStartText} - {slotEndText}
                              </p>
                              {slot.isBusy ? <p className="text-xs">No disponible</p> : null}
                              {slot.isPast ? <p className="text-xs">Horario pasado</p> : null}
                            </button>
                          );
                        })}
                      </div>
                      <p className="mt-3 text-xs text-slate-600">
                        Slots seleccionados: {selectedSlots.length}
                      </p>
                      <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Nota para paciente (opcional)
                        <textarea
                          className="mt-1 min-h-24 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 text-slate-700 focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                          onChange={(event) => {
                            if (selectedRequest === undefined) {
                              return;
                            }
                            const nextValue = event.target.value;
                            setProfessionalNotesByRequestId((currentValue) => ({
                              ...currentValue,
                              [selectedRequest.requestId]: nextValue
                            }));
                          }}
                          value={currentProfessionalNote}
                        />
                      </label>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          className="w-full rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                          disabled={submitSlotsMutation.isPending}
                          onClick={() => {
                            if (selectedRequest === undefined) {
                              return;
                            }
                            if (selectedSlots.length === 0) {
                              setLocalSubmitErrorMessage("Debes seleccionar al menos un slot.");
                              return;
                            }
                            setLocalSubmitErrorMessage(null);
                            setSubmitSuccessMessage(null);
                            submitSlotsMutation.mutate({
                              request: selectedRequest,
                              slots: selectedSlots,
                              professionalNote:
                                currentProfessionalNote.trim() === ""
                                  ? null
                                  : currentProfessionalNote.trim()
                            });
                          }}
                          type="button"
                        >
                          {submitSlotsMutation.isPending ? "Enviando..." : "Enviar espacios"}
                        </button>
                      </div>
                    </section>
                  </>
                ) : null}

                {selectedRequest.status === "AWAITING_CONSULTATION_REVIEW" ? (
                  <section className="rounded-lg border border-border-subtle p-3">
                    <h4 className="text-sm font-semibold text-brand-ink">
                      Resolver motivo de consulta
                    </h4>
                    <p className="mt-2 text-xs text-slate-600">
                      Propón horarios arriba para aprobar, o pide más información / rechaza.
                    </p>
                    <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Nota para el bot
                      <textarea
                        className="mt-1 min-h-24 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 text-slate-700"
                        onChange={(event) => {
                          if (selectedRequest === undefined) {
                            return;
                          }
                          const nextValue = event.target.value;
                          setReviewNotesByRequestId((currentValue) => ({
                            ...currentValue,
                            [selectedRequest.requestId]: nextValue
                          }));
                        }}
                        value={currentReviewNote}
                      />
                    </label>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        className="rounded-md bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={resolveConsultationReviewMutation.isPending}
                        onClick={() => {
                          if (selectedRequest === undefined) {
                            return;
                          }
                          if (currentReviewNote.trim() === "") {
                            setLocalSubmitErrorMessage(
                              "Debes agregar una nota para pedir más información."
                            );
                            return;
                          }
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          resolveConsultationReviewMutation.mutate({
                            request: selectedRequest,
                            decision: "REQUEST_MORE_INFO",
                            professionalNote: currentReviewNote.trim()
                          });
                        }}
                        type="button"
                      >
                        Pedir más info
                      </button>
                      <button
                        className="rounded-md bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={resolveConsultationReviewMutation.isPending}
                        onClick={() => {
                          if (selectedRequest === undefined) {
                            return;
                          }
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          resolveConsultationReviewMutation.mutate({
                            request: selectedRequest,
                            decision: "REJECT",
                            professionalNote:
                              currentReviewNote.trim() === "" ? null : currentReviewNote.trim()
                          });
                        }}
                        type="button"
                      >
                        Rechazar
                      </button>
                    </div>
                  </section>
                ) : null}

                {selectedRequest.status === "AWAITING_PAYMENT_CONFIRMATION" ? (
                  <section className="rounded-lg border border-border-subtle p-3">
                    <h4 className="text-sm font-semibold text-brand-ink">
                      Confirmar pago del paciente
                    </h4>
                    <p className="mt-2 text-xs text-slate-600">
                      El paciente seleccionó un horario y se le enviaron los datos de pago. Verifica
                      el comprobante y aprueba, o envía un recordatorio de pago.
                    </p>
                    <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Nota para el bot
                      <textarea
                        className="mt-1 min-h-24 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 text-slate-700"
                        onChange={(event) => {
                          if (selectedRequest === undefined) {
                            return;
                          }
                          const nextValue = event.target.value;
                          setReviewNotesByRequestId((currentValue) => ({
                            ...currentValue,
                            [selectedRequest.requestId]: nextValue
                          }));
                        }}
                        value={currentReviewNote}
                      />
                    </label>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={resolvePaymentReviewMutation.isPending}
                        onClick={() => {
                          if (selectedRequest === undefined) {
                            return;
                          }
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          resolvePaymentReviewMutation.mutate({
                            request: selectedRequest,
                            decision: "APPROVE",
                            professionalNote:
                              currentReviewNote.trim() === "" ? null : currentReviewNote.trim()
                          });
                        }}
                        type="button"
                      >
                        Aprobar pago
                      </button>
                      <button
                        className="rounded-md bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={resolvePaymentReviewMutation.isPending}
                        onClick={() => {
                          if (selectedRequest === undefined) {
                            return;
                          }
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          resolvePaymentReviewMutation.mutate({
                            request: selectedRequest,
                            decision: "SEND_REMINDER",
                            professionalNote:
                              currentReviewNote.trim() === "" ? null : currentReviewNote.trim()
                          });
                        }}
                        type="button"
                      >
                        Enviar recordatorio
                      </button>
                    </div>
                  </section>
                ) : null}

                {selectedRequest.status === "BOOKED" ? (
                  <section className="rounded-lg border border-border-subtle p-3">
                    <h4 className="text-sm font-semibold text-brand-ink">
                      Gestionar cita del chatbot
                    </h4>
                    <p className="mt-1 text-xs text-slate-500">
                      Reprograma o cancela esta cita y sincroniza el cambio en Google Calendar.
                    </p>
                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Inicio
                        <input
                          className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                          onChange={(event) => {
                            const nextValue = event.target.value;
                            setBookedAppointmentFormState((currentValue) => ({
                              ...currentValue,
                              startAt: nextValue
                            }));
                          }}
                          type="datetime-local"
                          value={bookedAppointmentFormState.startAt}
                        />
                      </label>
                      <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Fin
                        <input
                          className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                          onChange={(event) => {
                            const nextValue = event.target.value;
                            setBookedAppointmentFormState((currentValue) => ({
                              ...currentValue,
                              endAt: nextValue
                            }));
                          }}
                          type="datetime-local"
                          value={bookedAppointmentFormState.endAt}
                        />
                      </label>
                      <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Timezone
                        <input
                          className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                          onChange={(event) => {
                            const nextValue = event.target.value;
                            setBookedAppointmentFormState((currentValue) => ({
                              ...currentValue,
                              timezone: nextValue
                            }));
                          }}
                          type="text"
                          value={bookedAppointmentFormState.timezone}
                        />
                      </label>
                      <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Resumen evento
                        <input
                          className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                          onChange={(event) => {
                            const nextValue = event.target.value;
                            setBookedAppointmentFormState((currentValue) => ({
                              ...currentValue,
                              eventSummary: nextValue
                            }));
                          }}
                          type="text"
                          value={bookedAppointmentFormState.eventSummary}
                        />
                      </label>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={rescheduleBookedSlotMutation.isPending}
                        onClick={() => {
                          if (selectedBookedBotRequest === null) {
                            return;
                          }
                          const normalizedTimezone = bookedAppointmentFormState.timezone.trim();
                          if (normalizedTimezone === "") {
                            setLocalSubmitErrorMessage("La zona horaria es obligatoria.");
                            return;
                          }
                          const startAtIso = toApiDateTime(
                            bookedAppointmentFormState.startAt,
                            normalizedTimezone
                          );
                          const endAtIso = toApiDateTime(
                            bookedAppointmentFormState.endAt,
                            normalizedTimezone
                          );
                          if (startAtIso === null || endAtIso === null) {
                            setLocalSubmitErrorMessage(
                              "Debes ingresar fecha y hora válidas para reprogramar."
                            );
                            return;
                          }
                          const startAtValue = luxonModule.DateTime.fromISO(startAtIso);
                          const endAtValue = luxonModule.DateTime.fromISO(endAtIso);
                          if (
                            !startAtValue.isValid ||
                            !endAtValue.isValid ||
                            endAtValue <= startAtValue
                          ) {
                            setLocalSubmitErrorMessage("El fin debe ser posterior al inicio.");
                            return;
                          }
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          rescheduleBookedSlotMutation.mutate({
                            requestId: selectedBookedBotRequest.requestId,
                            input: {
                              startAt: startAtIso,
                              endAt: endAtIso,
                              timezone: normalizedTimezone,
                              eventSummary:
                                bookedAppointmentFormState.eventSummary.trim() === ""
                                  ? null
                                  : bookedAppointmentFormState.eventSummary.trim()
                            }
                          });
                        }}
                        type="button"
                      >
                        {rescheduleBookedSlotMutation.isPending
                          ? "Reprogramando..."
                          : "Reprogramar cita bot"}
                      </button>
                    </div>
                    <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Motivo de cancelación (opcional)
                      <textarea
                        className="mt-1 min-h-20 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 text-slate-700"
                        onChange={(event) => {
                          const nextValue = event.target.value;
                          setBookedAppointmentFormState((currentValue) => ({
                            ...currentValue,
                            cancelReason: nextValue
                          }));
                        }}
                        value={bookedAppointmentFormState.cancelReason}
                      />
                    </label>
                    <div className="mt-3">
                      <button
                        className="rounded-md bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={cancelBookedSlotMutation.isPending}
                        onClick={() => {
                          if (selectedBookedBotRequest === null) {
                            return;
                          }
                          const isConfirmed = window.confirm(
                            "¿Seguro que quieres cancelar esta cita del chatbot?"
                          );
                          if (!isConfirmed) {
                            return;
                          }
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          cancelBookedSlotMutation.mutate({
                            requestId: selectedBookedBotRequest.requestId,
                            input: {
                              reason:
                                bookedAppointmentFormState.cancelReason.trim() === ""
                                  ? null
                                  : bookedAppointmentFormState.cancelReason.trim()
                            }
                          });
                        }}
                        type="button"
                      >
                        {cancelBookedSlotMutation.isPending ? "Cancelando..." : "Cancelar cita bot"}
                      </button>
                    </div>

                    <div className="mt-5 rounded-lg border border-border-subtle p-3">
                      <h5 className="text-sm font-semibold text-brand-ink">Pago de cita</h5>
                      <div className="mt-3 grid gap-3 md:grid-cols-3">
                        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Valor (COP)
                          <input
                            className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                            min={1}
                            onChange={(event) => {
                              setBookedPaymentFormState((currentValue) => ({
                                ...currentValue,
                                paymentAmountCop: event.target.value
                              }));
                            }}
                            type="number"
                            value={bookedPaymentFormState.paymentAmountCop}
                          />
                        </label>
                        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Categoría
                          <select
                            className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                            onChange={(event) => {
                              setBookedPaymentFormState((currentValue) => ({
                                ...currentValue,
                                paymentMethod: event.target.value as "CASH" | "TRANSFER"
                              }));
                            }}
                            value={bookedPaymentFormState.paymentMethod}
                          >
                            <option value="CASH">Efectivo</option>
                            <option value="TRANSFER">Transferencia</option>
                          </select>
                        </label>
                        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Estado
                          <select
                            className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                            onChange={(event) => {
                              setBookedPaymentFormState((currentValue) => ({
                                ...currentValue,
                                paymentStatus: event.target.value as "PENDING" | "PAID"
                              }));
                            }}
                            value={bookedPaymentFormState.paymentStatus}
                          >
                            <option value="PENDING">Pendiente por pago</option>
                            <option value="PAID">Pagada</option>
                          </select>
                        </label>
                      </div>
                      <div className="mt-3">
                        <button
                          className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={updateBookedPaymentMutation.isPending}
                          onClick={() => {
                            if (selectedBookedBotRequest === null) {
                              return;
                            }
                            const paymentAmountCop = Number.parseInt(
                              bookedPaymentFormState.paymentAmountCop,
                              10
                            );
                            if (Number.isNaN(paymentAmountCop) || paymentAmountCop <= 0) {
                              setLocalSubmitErrorMessage(
                                "El valor del pago debe ser mayor a cero."
                              );
                              return;
                            }
                            setLocalSubmitErrorMessage(null);
                            setSubmitSuccessMessage(null);
                            updateBookedPaymentMutation.mutate({
                              requestId: selectedBookedBotRequest.requestId,
                              input: {
                                paymentAmountCop,
                                paymentMethod: bookedPaymentFormState.paymentMethod,
                                paymentStatus: bookedPaymentFormState.paymentStatus
                              }
                            });
                          }}
                          type="button"
                        >
                          {updateBookedPaymentMutation.isPending
                            ? "Guardando pago..."
                            : "Guardar pago chatbot"}
                        </button>
                      </div>
                    </div>
                  </section>
                ) : null}
              </>
            )}

            {loadingErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner message={loadingErrorMessage} />
            ) : null}
            {submitErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner message={submitErrorMessage} />
            ) : null}
            {localSubmitErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner message={localSubmitErrorMessage} />
            ) : null}
            {submitSuccessMessage !== null ? (
              <div className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                {submitSuccessMessage}
              </div>
            ) : null}
          </article>
        </section>
      ) : null}

      {isManualSchedulingSection ? (
        <section className="mt-6 grid gap-4 xl:grid-cols-2">
          <article className="rounded-xl border border-border-subtle bg-white shadow-card p-4">
            <header className="mb-3">
              <h3 className="text-base font-semibold text-brand-ink">Pacientes</h3>
              <p className="text-xs text-slate-500">
                Crea, actualiza y elimina pacientes sin salir de Agenda.
              </p>
            </header>

            <section className="rounded-lg border border-border-subtle p-3">
              <h4 className="text-sm font-semibold text-brand-ink">Crear paciente</h4>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  WhatsApp ID
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setPatientFormState((currentValue) => ({
                        ...currentValue,
                        whatsappUserId: nextValue
                      }));
                    }}
                    type="text"
                    value={patientFormState.whatsappUserId}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Nombre
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setPatientFormState((currentValue) => ({
                        ...currentValue,
                        firstName: nextValue
                      }));
                    }}
                    type="text"
                    value={patientFormState.firstName}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Apellido
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setPatientFormState((currentValue) => ({
                        ...currentValue,
                        lastName: nextValue
                      }));
                    }}
                    type="text"
                    value={patientFormState.lastName}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Email
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setPatientFormState((currentValue) => ({
                        ...currentValue,
                        email: nextValue
                      }));
                    }}
                    type="email"
                    value={patientFormState.email}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Edad
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    min={1}
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setPatientFormState((currentValue) => ({
                        ...currentValue,
                        age: nextValue
                      }));
                    }}
                    type="number"
                    value={patientFormState.age}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Teléfono
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setPatientFormState((currentValue) => ({
                        ...currentValue,
                        phone: nextValue
                      }));
                    }}
                    type="text"
                    value={patientFormState.phone}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500 md:col-span-2">
                  Motivo de consulta
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setPatientFormState((currentValue) => ({
                        ...currentValue,
                        consultationReason: nextValue
                      }));
                    }}
                    type="text"
                    value={patientFormState.consultationReason}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500 md:col-span-2">
                  Ubicación
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setPatientFormState((currentValue) => ({
                        ...currentValue,
                        location: nextValue
                      }));
                    }}
                    type="text"
                    value={patientFormState.location}
                  />
                </label>
              </div>
              <div className="mt-3">
                <button
                  className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={createPatientMutation.isPending}
                  onClick={() => {
                    const trimmedWhatsappUserId = patientFormState.whatsappUserId.trim();
                    const trimmedFirstName = patientFormState.firstName.trim();
                    const trimmedLastName = patientFormState.lastName.trim();
                    const trimmedEmail = patientFormState.email.trim();
                    const trimmedConsultationReason = patientFormState.consultationReason.trim();
                    const trimmedLocation = patientFormState.location.trim();
                    const trimmedPhone = patientFormState.phone.trim();
                    const ageValue = Number.parseInt(patientFormState.age, 10);
                    if (
                      trimmedWhatsappUserId === "" ||
                      trimmedFirstName === "" ||
                      trimmedLastName === "" ||
                      trimmedEmail === "" ||
                      trimmedConsultationReason === "" ||
                      trimmedLocation === "" ||
                      trimmedPhone === "" ||
                      Number.isNaN(ageValue) ||
                      ageValue <= 0
                    ) {
                      setLocalSubmitErrorMessage(
                        "Completa todos los campos del paciente antes de guardar."
                      );
                      return;
                    }
                    setLocalSubmitErrorMessage(null);
                    setSubmitSuccessMessage(null);
                    createPatientMutation.mutate({
                      whatsappUserId: trimmedWhatsappUserId,
                      firstName: trimmedFirstName,
                      lastName: trimmedLastName,
                      email: trimmedEmail,
                      age: ageValue,
                      consultationReason: trimmedConsultationReason,
                      location: trimmedLocation,
                      phone: trimmedPhone
                    });
                  }}
                  type="button"
                >
                  {createPatientMutation.isPending ? "Creando..." : "Crear paciente"}
                </button>
              </div>
            </section>

            <section className="mt-4 rounded-lg border border-border-subtle p-3">
              <h4 className="text-sm font-semibold text-brand-ink">Listado de pacientes</h4>
              <div className="mt-3 space-y-2">
                {patientsQuery.isLoading ? (
                  <p className="text-sm text-slate-500">Cargando pacientes...</p>
                ) : null}
                {allPatients.length === 0 ? (
                  <p className="text-sm text-slate-500">Aún no hay pacientes registrados.</p>
                ) : null}
                {allPatients.map((patient) => (
                  <div
                    className="rounded-lg border border-border-subtle bg-white p-3"
                    key={patient.whatsappUserId}
                  >
                    <p className="text-sm font-semibold text-brand-ink">
                      {patient.firstName} {patient.lastName}
                    </p>
                    <p className="text-xs text-slate-600">WhatsApp: {patient.whatsappUserId}</p>
                    <p className="text-xs text-slate-600">Email: {patient.email}</p>
                    <p className="text-xs text-slate-600">Teléfono: {patient.phone}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <button
                        className="rounded-md border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                        onClick={() => {
                          setEditingPatientWhatsappUserId(patient.whatsappUserId);
                          setPatientUpdateFormState({
                            firstName: patient.firstName,
                            lastName: patient.lastName,
                            email: patient.email,
                            age: String(patient.age),
                            consultationReason: patient.consultationReason,
                            location: patient.location,
                            phone: patient.phone
                          });
                        }}
                        type="button"
                      >
                        Editar
                      </button>
                      <button
                        className="rounded-md border border-rose-300 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={removePatientMutation.isPending}
                        onClick={() => {
                          const isConfirmed = window.confirm(
                            "¿Seguro que quieres eliminar este paciente? Esto cancelará sus citas."
                          );
                          if (!isConfirmed) {
                            return;
                          }
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          removePatientMutation.mutate(patient.whatsappUserId);
                        }}
                        type="button"
                      >
                        {removePatientMutation.isPending ? "Eliminando..." : "Eliminar"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {editingPatientWhatsappUserId !== null ? (
              <section className="mt-4 rounded-lg border border-border-subtle p-3">
                <h4 className="text-sm font-semibold text-brand-ink">Editar paciente</h4>
                <p className="mt-1 text-xs text-slate-500">
                  WhatsApp ID fijo: {editingPatientWhatsappUserId}
                </p>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Nombre
                    <input
                      className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                      onChange={(event) => {
                        const nextValue = event.target.value;
                        setPatientUpdateFormState((currentValue) => ({
                          ...currentValue,
                          firstName: nextValue
                        }));
                      }}
                      type="text"
                      value={patientUpdateFormState.firstName}
                    />
                  </label>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Apellido
                    <input
                      className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                      onChange={(event) => {
                        const nextValue = event.target.value;
                        setPatientUpdateFormState((currentValue) => ({
                          ...currentValue,
                          lastName: nextValue
                        }));
                      }}
                      type="text"
                      value={patientUpdateFormState.lastName}
                    />
                  </label>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Email
                    <input
                      className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                      onChange={(event) => {
                        const nextValue = event.target.value;
                        setPatientUpdateFormState((currentValue) => ({
                          ...currentValue,
                          email: nextValue
                        }));
                      }}
                      type="email"
                      value={patientUpdateFormState.email}
                    />
                  </label>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Edad
                    <input
                      className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                      min={1}
                      onChange={(event) => {
                        const nextValue = event.target.value;
                        setPatientUpdateFormState((currentValue) => ({
                          ...currentValue,
                          age: nextValue
                        }));
                      }}
                      type="number"
                      value={patientUpdateFormState.age}
                    />
                  </label>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Teléfono
                    <input
                      className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                      onChange={(event) => {
                        const nextValue = event.target.value;
                        setPatientUpdateFormState((currentValue) => ({
                          ...currentValue,
                          phone: nextValue
                        }));
                      }}
                      type="text"
                      value={patientUpdateFormState.phone}
                    />
                  </label>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500 md:col-span-2">
                    Motivo de consulta
                    <input
                      className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                      onChange={(event) => {
                        const nextValue = event.target.value;
                        setPatientUpdateFormState((currentValue) => ({
                          ...currentValue,
                          consultationReason: nextValue
                        }));
                      }}
                      type="text"
                      value={patientUpdateFormState.consultationReason}
                    />
                  </label>
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500 md:col-span-2">
                    Ubicación
                    <input
                      className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                      onChange={(event) => {
                        const nextValue = event.target.value;
                        setPatientUpdateFormState((currentValue) => ({
                          ...currentValue,
                          location: nextValue
                        }));
                      }}
                      type="text"
                      value={patientUpdateFormState.location}
                    />
                  </label>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={updatePatientMutation.isPending}
                    onClick={() => {
                      if (editingPatientWhatsappUserId === null) {
                        return;
                      }
                      const trimmedFirstName = patientUpdateFormState.firstName.trim();
                      const trimmedLastName = patientUpdateFormState.lastName.trim();
                      const trimmedEmail = patientUpdateFormState.email.trim();
                      const trimmedConsultationReason =
                        patientUpdateFormState.consultationReason.trim();
                      const trimmedLocation = patientUpdateFormState.location.trim();
                      const trimmedPhone = patientUpdateFormState.phone.trim();
                      const ageValue = Number.parseInt(patientUpdateFormState.age, 10);
                      if (
                        trimmedFirstName === "" ||
                        trimmedLastName === "" ||
                        trimmedEmail === "" ||
                        trimmedConsultationReason === "" ||
                        trimmedLocation === "" ||
                        trimmedPhone === "" ||
                        Number.isNaN(ageValue) ||
                        ageValue <= 0
                      ) {
                        setLocalSubmitErrorMessage(
                          "Completa todos los campos del paciente antes de actualizar."
                        );
                        return;
                      }
                      setLocalSubmitErrorMessage(null);
                      setSubmitSuccessMessage(null);
                      updatePatientMutation.mutate({
                        whatsappUserId: editingPatientWhatsappUserId,
                        input: {
                          firstName: trimmedFirstName,
                          lastName: trimmedLastName,
                          email: trimmedEmail,
                          age: ageValue,
                          consultationReason: trimmedConsultationReason,
                          location: trimmedLocation,
                          phone: trimmedPhone
                        }
                      });
                    }}
                    type="button"
                  >
                    {updatePatientMutation.isPending ? "Guardando..." : "Guardar cambios"}
                  </button>
                  <button
                    className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                    onClick={() => {
                      setEditingPatientWhatsappUserId(null);
                      setPatientUpdateFormState(emptyPatientUpdateForm());
                    }}
                    type="button"
                  >
                    Cancelar edición
                  </button>
                </div>
              </section>
            ) : null}
          </article>

          <article className="rounded-xl border border-border-subtle bg-white shadow-card p-4">
            <header className="mb-3">
              <h3 className="text-base font-semibold text-brand-ink">Citas manuales</h3>
              <p className="text-xs text-slate-500">
                Crea, reprograma y elimina citas manuales sincronizadas con Calendar.
              </p>
            </header>

            <section className="rounded-lg border border-border-subtle p-3">
              <h4 className="text-sm font-semibold text-brand-ink">Nueva cita manual</h4>
              {allPatients.length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">
                  Necesitas al menos un paciente para crear una cita manual.
                </p>
              ) : null}
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500 md:col-span-2">
                  Paciente
                  <select
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setManualAppointmentFormState((currentValue) => ({
                        ...currentValue,
                        patientWhatsappUserId: nextValue
                      }));
                    }}
                    value={manualAppointmentFormState.patientWhatsappUserId}
                  >
                    <option value="">Selecciona un paciente</option>
                    {allPatients.map((patient) => (
                      <option key={patient.whatsappUserId} value={patient.whatsappUserId}>
                        {patient.firstName} {patient.lastName} ({patient.whatsappUserId})
                      </option>
                    ))}
                  </select>
                </label>
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <p className="block">Inicio</p>
                  <div className="mt-1 grid grid-cols-3 gap-2">
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Fecha
                      <input
                        className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                        onChange={(event) => {
                          const nextDate = event.target.value;
                          setManualAppointmentFormState((currentValue) => ({
                            ...currentValue,
                            startAt: mergeLocalDateTimeInput(currentValue.startAt, {
                              date: nextDate
                            })
                          }));
                        }}
                        type="date"
                        value={manualCreateStartParts.date}
                      />
                    </label>
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Hora
                      <select
                        className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                        onChange={(event) => {
                          const nextHour = event.target.value;
                          setManualAppointmentFormState((currentValue) => ({
                            ...currentValue,
                            startAt: mergeLocalDateTimeInput(currentValue.startAt, {
                              hour: nextHour
                            })
                          }));
                        }}
                        value={manualCreateStartParts.hour}
                      >
                        {hourOptions.map((hourOption) => (
                          <option key={hourOption} value={hourOption}>
                            {hourOption}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Minuto
                      <select
                        className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                        onChange={(event) => {
                          const nextMinute = event.target.value as LocalDateTimeParts["minute"];
                          setManualAppointmentFormState((currentValue) => ({
                            ...currentValue,
                            startAt: mergeLocalDateTimeInput(currentValue.startAt, {
                              minute: nextMinute
                            })
                          }));
                        }}
                        value={manualCreateStartParts.minute}
                      >
                        {halfHourMinuteOptions.map((minuteOption) => (
                          <option key={minuteOption} value={minuteOption}>
                            {minuteOption}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                </div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Duración
                  <select
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setManualAppointmentFormState((currentValue) => ({
                        ...currentValue,
                        durationMinutes: nextValue
                      }));
                    }}
                    value={manualAppointmentFormState.durationMinutes}
                  >
                    {manualAppointmentDurationOptionsMinutes.map((minutesOption) => (
                      <option key={minutesOption} value={String(minutesOption)}>
                        {minutesOption} minutos
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Timezone
                  <input
                    className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-700"
                    disabled
                    readOnly
                    type="text"
                    value={colombiaTimezone}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Resumen
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setManualAppointmentFormState((currentValue) => ({
                        ...currentValue,
                        summary: nextValue
                      }));
                    }}
                    type="text"
                    value={manualAppointmentFormState.summary}
                  />
                </label>
              </div>
              <div className="mt-3">
                <button
                  className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={createManualAppointmentMutation.isPending || allPatients.length === 0}
                  onClick={() => {
                    if (manualAppointmentFormState.patientWhatsappUserId.trim() === "") {
                      setLocalSubmitErrorMessage("Debes seleccionar un paciente.");
                      return;
                    }
                    const startAtIso = toApiDateTime(
                      manualAppointmentFormState.startAt,
                      colombiaTimezone
                    );
                    const durationMinutes = Number.parseInt(
                      manualAppointmentFormState.durationMinutes,
                      10
                    );
                    if (Number.isNaN(durationMinutes) || durationMinutes <= 0) {
                      setLocalSubmitErrorMessage("Debes seleccionar una duración válida.");
                      return;
                    }
                    if (startAtIso === null) {
                      setLocalSubmitErrorMessage("Debes ingresar fecha y hora de inicio válidas.");
                      return;
                    }
                    if (!isThirtyMinuteAligned(startAtIso, colombiaTimezone)) {
                      setLocalSubmitErrorMessage(
                        "El inicio de la cita debe estar en bloques de 30 minutos."
                      );
                      return;
                    }
                    const endAtIso = calculateEndAtFromStart(
                      startAtIso,
                      durationMinutes,
                      colombiaTimezone
                    );
                    if (startAtIso === null || endAtIso === null) {
                      setLocalSubmitErrorMessage("No se pudo calcular la hora final de la cita.");
                      return;
                    }
                    const startAtValue = luxonModule.DateTime.fromISO(startAtIso);
                    const endAtValue = luxonModule.DateTime.fromISO(endAtIso);
                    if (
                      !startAtValue.isValid ||
                      !endAtValue.isValid ||
                      endAtValue <= startAtValue
                    ) {
                      setLocalSubmitErrorMessage("El fin debe ser posterior al inicio.");
                      return;
                    }
                    setLocalSubmitErrorMessage(null);
                    setSubmitSuccessMessage(null);
                    createManualAppointmentMutation.mutate({
                      patientWhatsappUserId: manualAppointmentFormState.patientWhatsappUserId,
                      startAt: startAtIso,
                      endAt: endAtIso,
                      timezone: colombiaTimezone,
                      summary:
                        manualAppointmentFormState.summary.trim() === ""
                          ? null
                          : manualAppointmentFormState.summary.trim()
                    });
                  }}
                  type="button"
                >
                  {createManualAppointmentMutation.isPending ? "Creando..." : "Crear cita manual"}
                </button>
              </div>
            </section>

            <section className="mt-4 rounded-lg border border-border-subtle p-3">
              <h4 className="text-sm font-semibold text-brand-ink">Listado de citas manuales</h4>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  className={[
                    "rounded-md border px-3 py-1.5 text-xs font-semibold",
                    manualAppointmentListFilter === "SCHEDULED"
                      ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                      : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                  ].join(" ")}
                  onClick={() => {
                    setManualAppointmentListFilter("SCHEDULED");
                    setEditingManualAppointmentId(null);
                  }}
                  type="button"
                >
                  Agendadas ({manualAppointmentCountByStatus.SCHEDULED})
                </button>
                <button
                  className={[
                    "rounded-md border px-3 py-1.5 text-xs font-semibold",
                    manualAppointmentListFilter === "CANCELLED"
                      ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                      : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                  ].join(" ")}
                  onClick={() => {
                    setManualAppointmentListFilter("CANCELLED");
                    setEditingManualAppointmentId(null);
                  }}
                  type="button"
                >
                  Canceladas ({manualAppointmentCountByStatus.CANCELLED})
                </button>
              </div>
              <div className="mt-3 space-y-2">
                {manualAppointmentsQuery.isLoading ? (
                  <p className="text-sm text-slate-500">Cargando citas manuales...</p>
                ) : null}
                {filteredManualAppointments.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    {manualAppointmentListFilter === "SCHEDULED"
                      ? "No hay citas manuales agendadas."
                      : "No hay citas manuales canceladas."}
                  </p>
                ) : null}
                {filteredManualAppointments.map((appointment) => {
                  const patient = patientsByWhatsappUserId.get(appointment.patientWhatsappUserId);
                  const patientName =
                    patient === undefined
                      ? appointment.patientWhatsappUserId
                      : `${patient.firstName} ${patient.lastName}`;
                  const startText = dateUtilsModule.formatDateTime(appointment.startAt);
                  const endText = dateUtilsModule.formatDateTime(appointment.endAt);
                  const isEditing = editingManualAppointmentId === appointment.appointmentId;
                  const isScheduled = appointment.status === "SCHEDULED";
                  return (
                    <div
                      className="rounded-lg border border-border-subtle bg-white p-3"
                      key={appointment.appointmentId}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-brand-ink">{patientName}</p>
                        <statusBadgeModule.StatusBadge label={appointment.status} tone="neutral" />
                      </div>
                      <p className="text-xs text-slate-600">ID: {appointment.appointmentId}</p>
                      <p className="text-xs text-slate-600">
                        {startText} - {endText}
                      </p>
                      <p className="text-xs text-slate-600">Resumen: {appointment.summary}</p>
                      <p className="text-xs text-slate-600">Timezone: {appointment.timezone}</p>
                      {isScheduled ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          <button
                            className="rounded-md border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                            onClick={() => {
                              setEditingManualAppointmentId(appointment.appointmentId);
                              setManualRescheduleFormState({
                                patientWhatsappUserId: appointment.patientWhatsappUserId,
                                startAt: toDateTimeInputValue(
                                  appointment.startAt,
                                  colombiaTimezone
                                ),
                                durationMinutes: resolveDurationMinutesFromRange(
                                  appointment.startAt,
                                  appointment.endAt,
                                  60
                                ),
                                summary: appointment.summary
                              });
                            }}
                            type="button"
                          >
                            Reprogramar
                          </button>
                          <button
                            className="rounded-md border border-rose-300 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={cancelManualAppointmentMutation.isPending}
                            onClick={() => {
                              const isConfirmed = window.confirm(
                                "¿Seguro que quieres eliminar esta cita manual?"
                              );
                              if (!isConfirmed) {
                                return;
                              }
                              setLocalSubmitErrorMessage(null);
                              setSubmitSuccessMessage(null);
                              cancelManualAppointmentMutation.mutate({
                                appointmentId: appointment.appointmentId,
                                input: {
                                  reason: null
                                }
                              });
                            }}
                            type="button"
                          >
                            {cancelManualAppointmentMutation.isPending
                              ? "Eliminando..."
                              : "Eliminar"}
                          </button>
                        </div>
                      ) : null}
                      {isEditing ? (
                        <div className="mt-3 grid gap-3 rounded-lg border border-border-subtle bg-slate-50 p-3 md:grid-cols-2">
                          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            <p className="block">Inicio</p>
                            <div className="mt-1 grid grid-cols-3 gap-2">
                              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                Fecha
                                <input
                                  className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                                  onChange={(event) => {
                                    const nextDate = event.target.value;
                                    setManualRescheduleFormState((currentValue) => ({
                                      ...currentValue,
                                      startAt: mergeLocalDateTimeInput(currentValue.startAt, {
                                        date: nextDate
                                      })
                                    }));
                                  }}
                                  type="date"
                                  value={manualRescheduleStartParts.date}
                                />
                              </label>
                              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                Hora
                                <select
                                  className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                                  onChange={(event) => {
                                    const nextHour = event.target.value;
                                    setManualRescheduleFormState((currentValue) => ({
                                      ...currentValue,
                                      startAt: mergeLocalDateTimeInput(currentValue.startAt, {
                                        hour: nextHour
                                      })
                                    }));
                                  }}
                                  value={manualRescheduleStartParts.hour}
                                >
                                  {hourOptions.map((hourOption) => (
                                    <option key={hourOption} value={hourOption}>
                                      {hourOption}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                Minuto
                                <select
                                  className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                                  onChange={(event) => {
                                    const nextMinute = event.target
                                      .value as LocalDateTimeParts["minute"];
                                    setManualRescheduleFormState((currentValue) => ({
                                      ...currentValue,
                                      startAt: mergeLocalDateTimeInput(currentValue.startAt, {
                                        minute: nextMinute
                                      })
                                    }));
                                  }}
                                  value={manualRescheduleStartParts.minute}
                                >
                                  {halfHourMinuteOptions.map((minuteOption) => (
                                    <option key={minuteOption} value={minuteOption}>
                                      {minuteOption}
                                    </option>
                                  ))}
                                </select>
                              </label>
                            </div>
                          </div>
                          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Duración
                            <select
                              className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                              onChange={(event) => {
                                const nextValue = event.target.value;
                                setManualRescheduleFormState((currentValue) => ({
                                  ...currentValue,
                                  durationMinutes: nextValue
                                }));
                              }}
                              value={manualRescheduleFormState.durationMinutes}
                            >
                              {manualAppointmentDurationOptionsMinutes.map((minutesOption) => (
                                <option key={minutesOption} value={String(minutesOption)}>
                                  {minutesOption} minutos
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Timezone
                            <input
                              className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-700"
                              disabled
                              readOnly
                              type="text"
                              value={colombiaTimezone}
                            />
                          </label>
                          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Resumen
                            <input
                              className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                              onChange={(event) => {
                                const nextValue = event.target.value;
                                setManualRescheduleFormState((currentValue) => ({
                                  ...currentValue,
                                  summary: nextValue
                                }));
                              }}
                              type="text"
                              value={manualRescheduleFormState.summary}
                            />
                          </label>
                          <div className="md:col-span-2 flex flex-wrap gap-2">
                            <button
                              className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                              disabled={rescheduleManualAppointmentMutation.isPending}
                              onClick={() => {
                                const startAtIso = toApiDateTime(
                                  manualRescheduleFormState.startAt,
                                  colombiaTimezone
                                );
                                const durationMinutes = Number.parseInt(
                                  manualRescheduleFormState.durationMinutes,
                                  10
                                );
                                if (Number.isNaN(durationMinutes) || durationMinutes <= 0) {
                                  setLocalSubmitErrorMessage(
                                    "Debes seleccionar una duración válida."
                                  );
                                  return;
                                }
                                if (startAtIso === null) {
                                  setLocalSubmitErrorMessage(
                                    "Debes ingresar fecha y hora de inicio válidas."
                                  );
                                  return;
                                }
                                if (!isThirtyMinuteAligned(startAtIso, colombiaTimezone)) {
                                  setLocalSubmitErrorMessage(
                                    "El inicio de la cita debe estar en bloques de 30 minutos."
                                  );
                                  return;
                                }
                                const endAtIso = calculateEndAtFromStart(
                                  startAtIso,
                                  durationMinutes,
                                  colombiaTimezone
                                );
                                if (endAtIso === null) {
                                  setLocalSubmitErrorMessage(
                                    "No se pudo calcular la hora final de la cita."
                                  );
                                  return;
                                }
                                const startAtValue = luxonModule.DateTime.fromISO(startAtIso);
                                const endAtValue = luxonModule.DateTime.fromISO(endAtIso);
                                if (
                                  !startAtValue.isValid ||
                                  !endAtValue.isValid ||
                                  endAtValue <= startAtValue
                                ) {
                                  setLocalSubmitErrorMessage(
                                    "El fin debe ser posterior al inicio."
                                  );
                                  return;
                                }
                                setLocalSubmitErrorMessage(null);
                                setSubmitSuccessMessage(null);
                                rescheduleManualAppointmentMutation.mutate({
                                  appointmentId: appointment.appointmentId,
                                  input: {
                                    startAt: startAtIso,
                                    endAt: endAtIso,
                                    timezone: colombiaTimezone,
                                    summary:
                                      manualRescheduleFormState.summary.trim() === ""
                                        ? null
                                        : manualRescheduleFormState.summary.trim()
                                  }
                                });
                              }}
                              type="button"
                            >
                              {rescheduleManualAppointmentMutation.isPending
                                ? "Guardando..."
                                : "Guardar reprogramación"}
                            </button>
                            <button
                              className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                              onClick={() => {
                                setEditingManualAppointmentId(null);
                              }}
                              type="button"
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </section>
          </article>
        </section>
      ) : null}

      {isFinanceSection ? (
        <section className="mt-6 space-y-4">
          <article className="rounded-xl border border-border-subtle bg-white shadow-card p-4">
            <header className="mb-4">
              <h3 className="text-base font-semibold text-brand-ink">Finanzas</h3>
              <p className="text-xs text-slate-500">
                Seguimiento de pagos para citas agendadas (chatbot y manuales).
              </p>
            </header>

            <section className="rounded-lg border border-border-subtle p-3">
              <h4 className="text-sm font-semibold text-brand-ink">Filtros</h4>
              <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Desde (fecha cita)
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => setFinanceFromDate(event.target.value)}
                    type="date"
                    value={financeFromDate}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Hasta (fecha cita)
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => setFinanceToDate(event.target.value)}
                    type="date"
                    value={financeToDate}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Estado de pago
                  <select
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) =>
                      setFinancePaymentStatusFilter(
                        event.target.value as FinancePaymentStatusFilter
                      )
                    }
                    value={financePaymentStatusFilter}
                  >
                    <option value="ALL">Todos</option>
                    <option value="PENDING">Pendiente por pago</option>
                    <option value="PAID">Pagada</option>
                  </select>
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Método de pago
                  <select
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) =>
                      setFinancePaymentMethodFilter(
                        event.target.value as FinancePaymentMethodFilter
                      )
                    }
                    value={financePaymentMethodFilter}
                  >
                    <option value="ALL">Todos</option>
                    <option value="CASH">Efectivo</option>
                    <option value="TRANSFER">Transferencia</option>
                  </select>
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Origen
                  <select
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) =>
                      setFinanceSourceFilter(event.target.value as FinanceSourceFilter)
                    }
                    value={financeSourceFilter}
                  >
                    <option value="ALL">Todos</option>
                    <option value="CHATBOT">Chatbot</option>
                    <option value="MANUAL">Manual</option>
                  </select>
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Buscar paciente
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => setFinanceSearchTerm(event.target.value)}
                    placeholder="Nombre o WhatsApp"
                    type="text"
                    value={financeSearchTerm}
                  />
                </label>
              </div>
              <div className="mt-3">
                <button
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  onClick={() => {
                    setFinanceFromDate("");
                    setFinanceToDate("");
                    setFinancePaymentStatusFilter("ALL");
                    setFinancePaymentMethodFilter("ALL");
                    setFinanceSourceFilter("ALL");
                    setFinanceSearchTerm("");
                  }}
                  type="button"
                >
                  Limpiar filtros
                </button>
              </div>
            </section>

            <section className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <article className="rounded-lg border border-border-subtle bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Total citas
                </p>
                <p className="mt-1 text-xl font-semibold text-brand-ink">
                  {financeMetrics.totalAppointments}
                </p>
              </article>
              <article className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                  Pendientes
                </p>
                <p className="mt-1 text-xl font-semibold text-amber-700">
                  {financeMetrics.pendingAppointments}
                </p>
              </article>
              <article className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                  Pagadas
                </p>
                <p className="mt-1 text-xl font-semibold text-emerald-700">
                  {financeMetrics.paidAppointments}
                </p>
              </article>
              <article className="rounded-lg border border-palette-sage bg-brand-accent-light p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-brand-teal">
                  Total pagado
                </p>
                <p className="mt-1 text-xl font-semibold text-brand-teal">
                  {formatCopCurrency(financeMetrics.totalPaidCop)}
                </p>
              </article>
            </section>

            <section className="mt-4 rounded-lg border border-border-subtle p-3">
              <h4 className="text-sm font-semibold text-brand-ink">Detalle de citas</h4>
              {filteredFinanceAppointments.length === 0 ? (
                <p className="mt-3 text-sm text-slate-500">
                  No hay citas que coincidan con los filtros seleccionados.
                </p>
              ) : (
                <div className="mt-3 space-y-2">
                  {filteredFinanceAppointments.map((appointment) => {
                    const startAt = luxonModule.DateTime.fromISO(appointment.startAt, {
                      zone: appointment.timezone
                    });
                    const endAt = luxonModule.DateTime.fromISO(appointment.endAt, {
                      zone: appointment.timezone
                    });
                    const dateText =
                      !startAt.isValid || !endAt.isValid
                        ? "-"
                        : `${startAt.toFormat("dd LLL yyyy HH:mm")} - ${endAt.toFormat("HH:mm")}`;
                    const paymentMethodLabel =
                      appointment.paymentMethod === "CASH"
                        ? "Efectivo"
                        : appointment.paymentMethod === "TRANSFER"
                          ? "Transferencia"
                          : "-";
                    const paymentStatusLabel =
                      appointment.paymentStatus === "PAID" ? "Pagada" : "Pendiente por pago";
                    const paymentAmountLabel =
                      appointment.paymentAmountCop === null
                        ? "-"
                        : formatCopCurrency(appointment.paymentAmountCop);
                    return (
                      <article
                        className="rounded-md border border-slate-200 bg-white px-3 py-2"
                        key={appointment.itemKey}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-brand-ink">
                            {appointment.patientDisplayName}
                          </p>
                          <statusBadgeModule.StatusBadge
                            label={paymentStatusLabel}
                            tone={appointment.paymentStatus === "PAID" ? "success" : "warning"}
                          />
                        </div>
                        <p className="text-xs text-slate-600">
                          WhatsApp: {appointment.whatsappUserId}
                        </p>
                        <p className="text-xs text-slate-600">Cita: {dateText}</p>
                        <p className="text-xs text-slate-600">Origen: {appointment.source}</p>
                        <p className="text-xs text-slate-600">Valor: {paymentAmountLabel}</p>
                        <p className="text-xs text-slate-600">Método: {paymentMethodLabel}</p>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </article>
        </section>
      ) : null}
    </appShellModule.AppShell>
  );
}

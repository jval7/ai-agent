import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import { NewPatientModal } from "@adapters/inbound/react/components/NewPatientModal";
import * as slotPickerModule from "@adapters/inbound/react/components/SlotPicker";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as patientModel from "@domain/models/patient";
import type * as schedulingModel from "@domain/models/scheduling";
import * as uiErrorModule from "@shared/http/ui_error";
import * as calendarUtilsModule from "@shared/utils/calendar";
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
    id: "FINALIZED",
    label: "Agenda e Historial",
    statuses: [
      { status: "BOOKED", label: "Agendadas" },
      { status: "SESSION_CLOSED", label: "Cerradas" },
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

interface LocalDateTimeParts {
  date: string;
  hour: string;
  minute: "00" | "30";
}

interface BookedAppointment {
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

interface ManualAppointmentFormState {
  patientWhatsappUserId: string;
  selectedSlots: { slotId: string; startAt: string; endAt: string; timezone: string }[];
  summary: string;
  isVirtual: boolean;
}

interface RescheduleManualFormState {
  patientWhatsappUserId: string;
  startAt: string;
  durationMinutes: string;
  summary: string;
  isVirtual: boolean;
}

type ManualAppointmentListFilter = "SCHEDULED" | "CANCELLED";

interface BookedAppointmentFormState {
  startDate: string;
  startTime: string;
  durationMinutes: string;
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

function emptyManualAppointmentForm(): ManualAppointmentFormState {
  return {
    patientWhatsappUserId: "",
    selectedSlots: [],
    summary: "",
    isVirtual: true
  };
}

function emptyRescheduleManualForm(): RescheduleManualFormState {
  return {
    patientWhatsappUserId: "",
    startAt: "",
    durationMinutes: "60",
    summary: "",
    isVirtual: true
  };
}

function emptyBookedAppointmentForm(): BookedAppointmentFormState {
  return {
    startDate: "",
    startTime: "08:00",
    durationMinutes: "60",
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

function deriveWhatsappUserId(phone: string): string {
  return phone.replace(/\D/g, "");
}

function resolvePatientDisplayName(
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

  return null;
}

export function AgendaPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  const nowDate = luxonModule.DateTime.now();

  const requestsQuery = reactQueryModule.useQuery({
    queryKey: schedulingRequestsQueryKey,
    queryFn: () => appContainer.schedulingUseCase.listRequests(),
    refetchInterval: 5_000
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

  const [activeSectionId, setActiveSectionId] = reactModule.useState<string>("FINALIZED");
  const [activeTab, setActiveTab] =
    reactModule.useState<schedulingModel.SchedulingRequestStatus>("BOOKED");
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
  const [mobileBookedStep, setMobileBookedStep] = reactModule.useState<
    "calendar" | "dayList" | "detail"
  >("calendar");
  const [localSubmitErrorMessage, setLocalSubmitErrorMessage] = reactModule.useState<string | null>(
    null
  );
  const [submitSuccessMessage, setSubmitSuccessMessage] = reactModule.useState<string | null>(null);
  const [patientFormState, setPatientFormState] =
    reactModule.useState<PatientFormState>(emptyPatientForm());
  const [manualAppointmentFormState, setManualAppointmentFormState] =
    reactModule.useState<ManualAppointmentFormState>(emptyManualAppointmentForm());
  const [manualMobileStep, setManualMobileStep] = reactModule.useState<
    "SELECT_PATIENT" | "CREATE_PATIENT" | "APPOINTMENT_FORM"
  >("SELECT_PATIENT");
  const [manualMobileSelectedPatientId, setManualMobileSelectedPatientId] = reactModule.useState<
    string | null
  >(null);
  const [isNewPatientModalOpen, setIsNewPatientModalOpen] = reactModule.useState(false);
  const [manualSlotPickerMonth, setManualSlotPickerMonth] = reactModule.useState<{
    year: number;
    month: number;
  }>(() => {
    const now = luxonModule.DateTime.now().setZone(colombiaTimezone);
    return { year: now.year, month: now.month };
  });
  const [manualAppointmentListFilter, setManualAppointmentListFilter] =
    reactModule.useState<ManualAppointmentListFilter>("SCHEDULED");
  const [editingManualAppointmentId, setEditingManualAppointmentId] = reactModule.useState<
    string | null
  >(null);
  const [manualRescheduleFormState, setManualRescheduleFormState] =
    reactModule.useState<RescheduleManualFormState>(emptyRescheduleManualForm());
  const [bookedAppointmentFormState, setBookedAppointmentFormState] =
    reactModule.useState<BookedAppointmentFormState>(emptyBookedAppointmentForm());
  const [manualPaymentFormState, setManualPaymentFormState] =
    reactModule.useState<PaymentFormState>(emptyPaymentForm());
  const [bookedPaymentFormState, setBookedPaymentFormState] =
    reactModule.useState<PaymentFormState>(emptyPaymentForm());
  const [expandedBookedAction, setExpandedBookedAction] = reactModule.useState<
    "reschedule" | "cancel" | "payment" | null
  >(null);
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
        const bookedCount = allRequests.filter(
          (request) => request.status === "BOOKED" || request.status === "SESSION_CLOSED"
        ).length;
        const manualCount = allManualAppointments.filter(
          (appointment) => appointment.status === "SCHEDULED"
        ).length;
        counts[section.id] = bookedCount + manualCount;
        return;
      }
      if (section.id === "FINALIZED") {
        counts[section.id] =
          (requestCountByStatus.get("BOOKED") ?? 0) +
          (requestCountByStatus.get("SESSION_CLOSED") ?? 0);
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

  const filteredRequests = reactModule.useMemo(() => {
    return allRequests.filter((request) => request.status === activeTab);
  }, [allRequests, activeTab]);
  const isManualSchedulingSection = activeSectionId === "MANUAL_SCHEDULING";
  const isFinanceSection = activeSectionId === "FINANCE";
  const isFinalizedSection = activeSectionId === "FINALIZED";
  const isBookedTab = activeTab === "BOOKED";

  const manualSlotPickerMonthStart = luxonModule.DateTime.fromObject(
    { year: manualSlotPickerMonth.year, month: manualSlotPickerMonth.month, day: 1 },
    { zone: colombiaTimezone }
  );
  const manualSlotPickerMonthEnd = manualSlotPickerMonthStart.plus({ months: 1 });
  const manualSlotPickerMonthFromIso = manualSlotPickerMonthStart.toISO();
  const manualSlotPickerMonthToIso = manualSlotPickerMonthEnd.toISO();

  const manualAvailabilityQuery = reactQueryModule.useQuery({
    queryKey: [
      "google-calendar-availability",
      "manual",
      manualSlotPickerMonthFromIso,
      manualSlotPickerMonthToIso
    ],
    enabled:
      isManualSchedulingSection &&
      manualSlotPickerMonthFromIso !== null &&
      manualSlotPickerMonthToIso !== null,
    queryFn: () =>
      appContainer.schedulingUseCase.getAvailability(
        manualSlotPickerMonthFromIso!,
        manualSlotPickerMonthToIso!
      )
  });

  const manualBusyIntervals = reactModule.useMemo<calendarUtilsModule.BusyIntervalRange[]>(() => {
    if (manualAvailabilityQuery.data === undefined) {
      return [];
    }
    return calendarUtilsModule.parseBusyIntervals(
      manualAvailabilityQuery.data.busyIntervals,
      colombiaTimezone
    );
  }, [manualAvailabilityQuery.data]);
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
    setSelectedRequestId(null);
    setSubmitSuccessMessage(null);
    setLocalSubmitErrorMessage(null);
    setMobileBookedStep("calendar");
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
  reactModule.useEffect(() => {
    const firstDayIso = visibleMonthStart.toISODate();
    if (firstDayIso !== null) {
      setSelectedDayIso(firstDayIso);
    }
  }, [visibleMonthStart.year, visibleMonthStart.month]);

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

  const financeAppointments = reactModule.useMemo<FinanceAppointmentItem[]>(() => {
    const items: FinanceAppointmentItem[] = [];
    allRequests
      .filter((request) => request.status === "BOOKED" || request.status === "SESSION_CLOSED")
      .forEach((request) => {
        const bookedSlot = resolveBookedSlot(request);
        if (bookedSlot === null) {
          return;
        }
        items.push({
          itemKey: `finance-bot:${request.requestId}`,
          source: "CHATBOT",
          patientDisplayName: resolvePatientDisplayName(request, patientsByWhatsappUserId),
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
    setExpandedBookedAction(null);
    if (selectedBookedAppointment?.source !== "BOT" || selectedBookedBotRequest === null) {
      setBookedAppointmentFormState(emptyBookedAppointmentForm());
      return;
    }
    const startInTz = selectedBookedAppointment.startAt.setZone(timezone);
    const endInTz = selectedBookedAppointment.endAt.setZone(timezone);
    const durationMins = endInTz.diff(startInTz, "minutes").minutes;
    setBookedAppointmentFormState({
      startDate: startInTz.toFormat("yyyy-LL-dd"),
      startTime: startInTz.toFormat("HH:mm"),
      durationMinutes: String(Math.max(Math.round(durationMins), 30)),
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

  const manualRescheduleStartParts = splitLocalDateTimeInput(manualRescheduleFormState.startAt);

  const resolvePaymentReviewMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      decision: "APPROVE" | "SEND_REMINDER";
      professionalNote: string | null;
      paymentAmountCop: number | null;
    }) => {
      return appContainer.schedulingUseCase.resolvePaymentReview(
        payload.request.conversationId,
        payload.request.requestId,
        {
          decision: payload.decision,
          professionalNote: payload.professionalNote,
          paymentAmountCop: payload.paymentAmountCop
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
              paymentAmountCop: payload.paymentAmountCop ?? request.paymentAmountCop,
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
    resolvePaymentReviewMutation.error,
    createPatientMutation.error,
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
        <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
          <div>
            <h2 className="text-lg font-semibold text-brand-ink sm:text-xl">Agenda profesional</h2>
            <p className="text-xs text-slate-600 sm:text-sm">
              Gestiona solicitudes y envía múltiples slots de 60 minutos.
            </p>
          </div>
          <button
            className="rounded-lg border border-border-subtle px-3 py-2 text-xs font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 sm:px-4 sm:py-2.5 sm:text-sm"
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
          {/* Mobile: bottom-tab-bar style grid */}
          <div className="grid grid-cols-4 gap-1 rounded-xl bg-slate-100 p-1 sm:hidden">
            {agendaSections.map((section) => {
              const isActive = activeSectionId === section.id;
              const count = sectionCounts[section.id] ?? 0;
              const iconBySection: Record<string, React.ReactNode> = {
                FINALIZED: (
                  <svg
                    className="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
                    />
                  </svg>
                ),
                MANUAL_SCHEDULING: (
                  <svg
                    className="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z"
                    />
                  </svg>
                ),
                FINANCE: (
                  <svg
                    className="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z"
                    />
                  </svg>
                )
              };
              const shortLabels: Record<string, string> = {
                FINALIZED: "Agenda",
                MANUAL_SCHEDULING: "Manual",
                FINANCE: "Finanzas"
              };
              return (
                <button
                  className={[
                    "relative flex flex-col items-center gap-0.5 rounded-lg px-1 py-2 text-[10px] font-semibold transition-colors",
                    isActive ? "bg-white text-brand-teal shadow-sm" : "text-slate-500"
                  ].join(" ")}
                  key={section.id}
                  onClick={() => handleSectionChange(section.id)}
                  type="button"
                >
                  {iconBySection[section.id]}
                  <span>{shortLabels[section.id]}</span>
                  {count > 0 ? (
                    <span
                      className={[
                        "absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[9px] font-bold",
                        isActive ? "bg-brand-teal text-white" : "bg-slate-300 text-slate-700"
                      ].join(" ")}
                    >
                      {count}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
          {/* Desktop: horizontal tab bar */}
          <div className="hidden border-b border-border-subtle sm:flex sm:gap-1 sm:pb-1">
            {agendaSections.map((section) => {
              const isActive = activeSectionId === section.id;
              const count = sectionCounts[section.id] ?? 0;
              return (
                <button
                  className={[
                    "relative -mb-px shrink-0 whitespace-nowrap px-6 py-3 text-sm font-semibold transition-colors",
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
                        "ml-2 rounded-full px-2 text-xs",
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

          {!isFinalizedSection &&
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
                      setMobileBookedStep("calendar");
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
        <section className="mt-4">
          <div
            className={[
              "grid gap-4",
              isBookedTab
                ? "lg:grid-cols-[520px_minmax(0,1fr)]"
                : "lg:grid-cols-[320px_minmax(0,1fr)]"
            ].join(" ")}
          >
            {isBookedTab ? (
              <article
                className={[
                  "rounded-xl border border-border-subtle bg-white shadow-card",
                  mobileBookedStep === "detail" ? "hidden sm:block" : ""
                ].join(" ")}
              >
                <header
                  className={[
                    "border-b border-border-subtle px-3 py-3 sm:p-4",
                    mobileBookedStep !== "calendar" ? "hidden sm:block" : ""
                  ].join(" ")}
                >
                  <h3 className="text-sm font-semibold sm:text-base">
                    Calendario de citas agendadas
                  </h3>
                  <p className="text-[11px] text-slate-500 sm:text-xs">
                    Integra citas del chatbot y manuales. Toca un día para ver detalle.
                  </p>
                </header>
                <div className="space-y-3 p-2 sm:p-3">
                  <div
                    className={[
                      "flex items-center justify-between gap-2",
                      mobileBookedStep !== "calendar" ? "hidden sm:flex" : ""
                    ].join(" ")}
                  >
                    <p className="text-sm font-semibold capitalize text-brand-ink">
                      {visibleMonthStart.toFormat("LLLL yyyy")}
                    </p>
                    <div className="flex gap-1.5 sm:gap-2">
                      <button
                        className="rounded-lg border border-border-subtle px-2.5 py-1 text-xs text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 sm:px-3 sm:text-sm"
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
                        className="rounded-lg border border-border-subtle px-2.5 py-1 text-xs text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 sm:px-3 sm:text-sm"
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

                  {/* Mobile compact calendar - only visible in calendar step */}
                  <div className={mobileBookedStep === "calendar" ? "sm:hidden" : "hidden"}>
                    <div className="grid grid-cols-7 gap-0.5 text-center text-[10px] font-semibold text-slate-500">
                      {calendarUtilsModule.weekDayLabels.map((label) => (
                        <span key={`mobile-${label}`}>{label}</span>
                      ))}
                    </div>
                    <div className="mt-1 grid grid-cols-7 gap-0.5">
                      {dayGrid.map((dateCell, index) => {
                        if (dateCell === null) {
                          return (
                            <div
                              className="aspect-square rounded-md"
                              key={`mobile-empty-${index}`}
                            />
                          );
                        }
                        const isoDate = dateCell.toISODate();
                        const dayAppointments =
                          isoDate === null ? [] : (bookedAppointmentsByDay.get(isoDate) ?? []);
                        const isSelectedDay = isoDate === selectedDayIso;
                        const hasAppointments = dayAppointments.length > 0;
                        return (
                          <button
                            className={[
                              "relative flex aspect-square flex-col items-center justify-center rounded-md text-xs font-medium transition-colors",
                              isSelectedDay
                                ? "bg-brand-teal font-bold text-white"
                                : hasAppointments
                                  ? "bg-brand-accent-light font-semibold text-brand-teal"
                                  : "text-slate-700 hover:bg-slate-100"
                            ].join(" ")}
                            key={dateCell.toISODate() ?? `mobile-day-${dateCell.day}-${index}`}
                            onClick={() => {
                              if (isoDate === null) {
                                return;
                              }
                              setSelectedDayIso(isoDate);
                              const firstAppointment = dayAppointments[0];
                              if (firstAppointment !== undefined) {
                                setSelectedBookedItemKey(firstAppointment.itemKey);
                                setSelectedRequestId(firstAppointment.requestId);
                                setMobileBookedStep("dayList");
                              }
                            }}
                            type="button"
                          >
                            {dateCell.day}
                            {hasAppointments ? (
                              <span
                                className={[
                                  "absolute bottom-0.5 h-1 w-1 rounded-full",
                                  isSelectedDay ? "bg-white" : "bg-brand-teal"
                                ].join(" ")}
                              />
                            ) : null}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Mobile day list - visible when a day with appointments is selected */}
                  <div className={mobileBookedStep === "dayList" ? "sm:hidden" : "hidden"}>
                    <button
                      className="mb-2 flex items-center gap-1 text-xs font-semibold text-brand-teal"
                      onClick={() => setMobileBookedStep("calendar")}
                      type="button"
                    >
                      <svg
                        className="h-4 w-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          d="M15 19l-7-7 7-7"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                        />
                      </svg>
                      Volver al calendario
                    </button>
                    <h4 className="text-sm font-semibold text-brand-ink">
                      {selectedDayIso !== ""
                        ? `Citas del ${luxonModule.DateTime.fromISO(selectedDayIso, {
                            zone: timezone
                          }).toFormat("dd LLL yyyy")}`
                        : "Citas del día"}
                    </h4>
                    {selectedDayAppointments.length === 0 ? (
                      <p className="mt-2 text-xs text-slate-500">No hay citas para este día.</p>
                    ) : (
                      <div className="mt-2 space-y-1.5">
                        {selectedDayAppointments.map((appointment) => {
                          const isSelectedAppointment =
                            appointment.itemKey === selectedBookedItemKey;
                          return (
                            <button
                              className={[
                                "w-full rounded-md border px-2.5 py-2 text-left",
                                isSelectedAppointment
                                  ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                              ].join(" ")}
                              key={`mobile-day-${appointment.itemKey}`}
                              onClick={() => {
                                setSelectedDayIso(appointment.dayIso);
                                setSelectedBookedItemKey(appointment.itemKey);
                                setSelectedRequestId(appointment.requestId);
                                setSubmitSuccessMessage(null);
                                setLocalSubmitErrorMessage(null);
                                setMobileBookedStep("detail");
                              }}
                              type="button"
                            >
                              <p className="text-xs font-semibold">
                                {appointment.startAt.toFormat("HH:mm")} -{" "}
                                {appointment.endAt.toFormat("HH:mm")}
                              </p>
                              {appointment.patientDisplayName !== appointment.patientPhone ? (
                                <p className="text-xs">{appointment.patientDisplayName}</p>
                              ) : null}
                              <p className="text-xs text-slate-500">{appointment.patientPhone}</p>
                              <p className="text-[11px] uppercase text-slate-500">
                                {appointment.source === "MANUAL" ? "Manual" : "Chatbot"}
                              </p>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Desktop full calendar */}
                  <div className="hidden sm:block">
                    <div className="overflow-x-auto pb-1">
                      <div className="min-w-[42rem]">
                        <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-600">
                          {calendarUtilsModule.weekDayLabels.map((label) => (
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
                  </div>

                  <section className="hidden rounded-lg border border-border-subtle p-2.5 sm:block sm:p-3">
                    <h4 className="text-xs font-semibold text-brand-ink sm:text-sm">
                      {selectedDayIso !== ""
                        ? `Citas del ${luxonModule.DateTime.fromISO(selectedDayIso, {
                            zone: timezone
                          }).toFormat("dd LLL yyyy")}`
                        : "Citas del día seleccionado"}
                    </h4>
                    {selectedDayAppointments.length === 0 ? (
                      <p className="mt-2 text-xs text-slate-500">No hay citas para este día.</p>
                    ) : (
                      <div className="mt-2 space-y-1.5 sm:space-y-2">
                        {selectedDayAppointments.map((appointment) => {
                          const isSelectedAppointment =
                            appointment.itemKey === selectedBookedItemKey;
                          return (
                            <button
                              className={[
                                "w-full rounded-md border px-2.5 py-2 text-left sm:px-3",
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
                              <p className="text-xs font-semibold sm:text-sm">
                                {appointment.startAt.toFormat("HH:mm")} -{" "}
                                {appointment.endAt.toFormat("HH:mm")}
                              </p>
                              {appointment.patientDisplayName !== appointment.patientPhone ? (
                                <p className="text-xs">{appointment.patientDisplayName}</p>
                              ) : null}
                              <p className="text-xs text-slate-500">{appointment.patientPhone}</p>
                              <p className="text-[11px] uppercase text-slate-500">
                                {appointment.source === "MANUAL" ? "Manual" : "Chatbot"}
                              </p>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </section>

                  <p className="text-[11px] text-slate-500 sm:text-xs">
                    Zona horaria de visualización: {timezone}
                  </p>
                </div>
              </article>
            ) : (
              <article className="rounded-xl border border-border-subtle bg-white shadow-card">
                <header className="border-b border-border-subtle px-3 py-3 sm:p-4">
                  <h3 className="text-sm font-semibold sm:text-base">Solicitudes</h3>
                  <p className="text-[11px] text-slate-500 sm:text-xs">
                    {`Estado actual: ${activeTab}`}
                  </p>
                </header>
                <div className="max-h-[calc(100vh-12rem)] space-y-2 overflow-auto p-2 sm:p-3">
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
                            {resolvePatientDisplayName(request, patientsByWhatsappUserId)}
                          </p>
                          <statusBadgeModule.StatusBadge
                            label={statusConfig?.label ?? request.status}
                            tone={statusConfig?.tone ?? "neutral"}
                          />
                        </div>
                        {request.audienceType !== null ? (
                          <span className="text-xs font-medium text-violet-600">
                            {request.audienceType === "CHILDREN" ? "Infantil" : "Adulto"}
                          </span>
                        ) : null}
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

            <article
              className={[
                "space-y-4 rounded-xl border border-border-subtle bg-white p-3 shadow-card sm:p-4",
                isBookedTab && mobileBookedStep !== "detail" ? "hidden sm:block" : ""
              ].join(" ")}
            >
              {isBookedTab && mobileBookedStep === "detail" ? (
                <button
                  className="flex items-center gap-1 text-xs font-semibold text-brand-teal sm:hidden"
                  onClick={() => setMobileBookedStep("dayList")}
                  type="button"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      d="M15 19l-7-7 7-7"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                    />
                  </svg>
                  Volver a citas del día
                </button>
              ) : null}
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
                          {resolvePatientDisplayName(selectedRequest, patientsByWhatsappUserId)}
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

                  {selectedRequest.status === "BOOKED" ||
                  selectedRequest.status === "SESSION_CLOSED" ? (
                    <section className="rounded-lg border border-border-subtle p-3">
                      <h4 className="text-sm font-semibold text-brand-ink">
                        Gestionar cita del chatbot
                      </h4>
                      <div className="mt-2 flex items-center gap-2">
                        <span
                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ${selectedRequest.paymentStatus === "PAID" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}
                        >
                          {selectedRequest.paymentStatus === "PAID"
                            ? "Pago confirmado"
                            : "Pago pendiente"}
                        </span>
                        {selectedRequest.paymentAmountCop != null ? (
                          <span className="text-xs text-slate-500">
                            ${selectedRequest.paymentAmountCop.toLocaleString("es-CO")} COP
                          </span>
                        ) : null}
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${expandedBookedAction === "reschedule" ? "bg-brand-teal text-white" : "border border-brand-teal text-brand-teal hover:bg-brand-accent-light"}`}
                          onClick={() =>
                            setExpandedBookedAction(
                              expandedBookedAction === "reschedule" ? null : "reschedule"
                            )
                          }
                          type="button"
                        >
                          Reprogramar
                        </button>
                        <button
                          className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${expandedBookedAction === "cancel" ? "bg-rose-600 text-white" : "border border-rose-600 text-rose-600 hover:bg-rose-50"}`}
                          onClick={() =>
                            setExpandedBookedAction(
                              expandedBookedAction === "cancel" ? null : "cancel"
                            )
                          }
                          type="button"
                        >
                          Cancelar
                        </button>
                        {selectedRequest.paymentStatus !== "PAID" ? (
                          <button
                            className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${expandedBookedAction === "payment" ? "bg-brand-teal text-white" : "border border-brand-teal text-brand-teal hover:bg-brand-accent-light"}`}
                            onClick={() =>
                              setExpandedBookedAction(
                                expandedBookedAction === "payment" ? null : "payment"
                              )
                            }
                            type="button"
                          >
                            Agregar pago
                          </button>
                        ) : null}
                        {selectedRequest.paymentStatus !== "PAID" ? (
                          <button
                            className="rounded-md border border-amber-500 px-4 py-2 text-sm font-semibold text-amber-600 transition-colors hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={resolvePaymentReviewMutation.isPending}
                            onClick={() => {
                              if (selectedBookedBotRequest === null) {
                                return;
                              }
                              setLocalSubmitErrorMessage(null);
                              setSubmitSuccessMessage(null);
                              resolvePaymentReviewMutation.mutate({
                                request: selectedRequest,
                                decision: "SEND_REMINDER",
                                professionalNote: null,
                                paymentAmountCop: null
                              });
                            }}
                            type="button"
                          >
                            {resolvePaymentReviewMutation.isPending
                              ? "Enviando..."
                              : "Recordatorio de pago"}
                          </button>
                        ) : null}
                      </div>

                      {expandedBookedAction === "reschedule" ? (
                        <div className="mt-3 rounded-lg border border-border-subtle p-3">
                          <p className="text-xs text-slate-500">
                            Reprograma esta cita y sincroniza el cambio en Google Calendar.
                          </p>
                          <div className="mt-3 grid gap-3 sm:grid-cols-3">
                            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Fecha
                              <input
                                className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                                onChange={(event) => {
                                  const nextValue = event.target.value;
                                  setBookedAppointmentFormState((currentValue) => ({
                                    ...currentValue,
                                    startDate: nextValue
                                  }));
                                }}
                                type="date"
                                value={bookedAppointmentFormState.startDate}
                              />
                            </label>
                            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Hora
                              <select
                                className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                                onChange={(event) => {
                                  const nextValue = event.target.value;
                                  setBookedAppointmentFormState((currentValue) => ({
                                    ...currentValue,
                                    startTime: nextValue
                                  }));
                                }}
                                value={bookedAppointmentFormState.startTime}
                              >
                                {Array.from({ length: 48 }, (_, idx) => {
                                  const hours = String(Math.floor(idx / 2)).padStart(2, "0");
                                  const mins = idx % 2 === 0 ? "00" : "30";
                                  const timeValue = `${hours}:${mins}`;
                                  return (
                                    <option key={timeValue} value={timeValue}>
                                      {timeValue}
                                    </option>
                                  );
                                })}
                              </select>
                            </label>
                            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Duración (min)
                              <select
                                className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                                onChange={(event) => {
                                  const nextValue = event.target.value;
                                  setBookedAppointmentFormState((currentValue) => ({
                                    ...currentValue,
                                    durationMinutes: nextValue
                                  }));
                                }}
                                value={bookedAppointmentFormState.durationMinutes}
                              >
                                <option value="30">30 min</option>
                                <option value="60">60 min</option>
                                <option value="90">90 min</option>
                                <option value="120">120 min</option>
                              </select>
                            </label>
                          </div>
                          <div className="mt-3">
                            <button
                              className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                              disabled={rescheduleBookedSlotMutation.isPending}
                              onClick={() => {
                                if (selectedBookedBotRequest === null) {
                                  return;
                                }
                                const { startDate, startTime, durationMinutes } =
                                  bookedAppointmentFormState;
                                if (startDate === "" || startTime === "") {
                                  setLocalSubmitErrorMessage(
                                    "Debes seleccionar fecha y hora para reprogramar."
                                  );
                                  return;
                                }
                                const colombiaTimezone = "America/Bogota";
                                const startAtDt = luxonModule.DateTime.fromISO(
                                  `${startDate}T${startTime}`,
                                  { zone: colombiaTimezone }
                                );
                                if (!startAtDt.isValid) {
                                  setLocalSubmitErrorMessage("Fecha u hora no válida.");
                                  return;
                                }
                                const endAtDt = startAtDt.plus({
                                  minutes: Number(durationMinutes)
                                });
                                const startAtIso = startAtDt.toISO();
                                const endAtIso = endAtDt.toISO();
                                if (startAtIso === null || endAtIso === null) {
                                  setLocalSubmitErrorMessage("Error al calcular las fechas.");
                                  return;
                                }
                                const originalSummary =
                                  selectedBookedAppointment?.patientDisplayName.trim() === ""
                                    ? "Cita"
                                    : `Cita - ${selectedBookedAppointment?.patientDisplayName ?? ""}`;
                                setLocalSubmitErrorMessage(null);
                                setSubmitSuccessMessage(null);
                                rescheduleBookedSlotMutation.mutate({
                                  requestId: selectedBookedBotRequest.requestId,
                                  input: {
                                    startAt: startAtIso,
                                    endAt: endAtIso,
                                    timezone: colombiaTimezone,
                                    eventSummary: originalSummary
                                  }
                                });
                              }}
                              type="button"
                            >
                              {rescheduleBookedSlotMutation.isPending
                                ? "Reprogramando..."
                                : "Reprogramar cita"}
                            </button>
                          </div>
                        </div>
                      ) : null}

                      {expandedBookedAction === "cancel" ? (
                        <div className="mt-3 rounded-lg border border-border-subtle p-3">
                          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
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
                              {cancelBookedSlotMutation.isPending
                                ? "Cancelando..."
                                : "Cancelar cita"}
                            </button>
                          </div>
                        </div>
                      ) : null}

                      {expandedBookedAction === "payment" ? (
                        <div className="mt-3 rounded-lg border border-border-subtle p-3">
                          <div className="grid gap-3 md:grid-cols-3">
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
                                : "Guardar pago"}
                            </button>
                          </div>
                        </div>
                      ) : null}
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
          </div>
        </section>
      ) : null}

      {isManualSchedulingSection ? (
        <section className="mt-4 sm:mt-6">
          {/* ===== MOBILE STEP-BY-STEP FLOW ===== */}
          <div className="sm:hidden">
            {manualMobileStep === "SELECT_PATIENT" ? (
              <article className="rounded-xl border border-border-subtle bg-white p-3 shadow-card">
                <header className="mb-3">
                  <h3 className="text-sm font-semibold text-brand-ink">Seleccionar paciente</h3>
                  <p className="text-[11px] text-slate-500">
                    Elige un paciente existente o crea uno nuevo.
                  </p>
                </header>
                <div className="mb-3">
                  <button
                    className="w-full rounded-lg border-2 border-dashed border-brand-teal/40 px-4 py-3 text-sm font-semibold text-brand-teal transition-colors hover:border-brand-teal hover:bg-brand-accent-light"
                    onClick={() => setManualMobileStep("CREATE_PATIENT")}
                    type="button"
                  >
                    + Crear nuevo paciente
                  </button>
                </div>
                <div className="space-y-2">
                  {patientsQuery.isLoading ? (
                    <p className="text-sm text-slate-500">Cargando pacientes...</p>
                  ) : null}
                  {allPatients.length === 0 && !patientsQuery.isLoading ? (
                    <p className="text-sm text-slate-500">Aún no hay pacientes registrados.</p>
                  ) : null}
                  {allPatients.map((patient) => (
                    <button
                      className="w-full rounded-lg border border-border-subtle bg-white p-3 text-left transition-colors hover:border-brand-teal hover:bg-brand-accent-light"
                      key={patient.whatsappUserId}
                      onClick={() => {
                        setManualMobileSelectedPatientId(patient.whatsappUserId);
                        setManualAppointmentFormState((currentValue) => ({
                          ...currentValue,
                          patientWhatsappUserId: patient.whatsappUserId
                        }));
                        setManualMobileStep("APPOINTMENT_FORM");
                      }}
                      type="button"
                    >
                      <p className="text-sm font-semibold text-brand-ink">
                        {patient.firstName} {patient.lastName}
                      </p>
                      <p className="text-xs text-slate-600">WhatsApp: {patient.whatsappUserId}</p>
                      <p className="text-xs text-slate-600">Tel: {patient.phone}</p>
                    </button>
                  ))}
                </div>
              </article>
            ) : null}

            {manualMobileStep === "CREATE_PATIENT" ? (
              <article className="rounded-xl border border-border-subtle bg-white p-3 shadow-card">
                <header className="mb-3 flex items-center gap-2">
                  <button
                    className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
                    onClick={() => setManualMobileStep("SELECT_PATIENT")}
                    type="button"
                  >
                    <svg
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M15.75 19.5L8.25 12l7.5-7.5"
                      />
                    </svg>
                  </button>
                  <div>
                    <h3 className="text-sm font-semibold text-brand-ink">Crear paciente</h3>
                    <p className="text-[11px] text-slate-500">
                      Completa los datos del nuevo paciente.
                    </p>
                  </div>
                </header>
                <div className="grid gap-3">
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
                      placeholder="+57 300 123 4567"
                      type="text"
                      value={patientFormState.phone}
                    />
                    {(() => {
                      const derived = deriveWhatsappUserId(patientFormState.phone);
                      const showError = patientFormState.phone.trim() !== "" && derived.length < 8;
                      return showError ? (
                        <p className="mt-1 text-[11px] text-rose-600">
                          Incluye el código de país, ej. +57 300 123 4567
                        </p>
                      ) : null;
                    })()}
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
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
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
                    className="w-full rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={createPatientMutation.isPending}
                    onClick={() => {
                      const trimmedFirstName = patientFormState.firstName.trim();
                      const trimmedLastName = patientFormState.lastName.trim();
                      const trimmedEmail = patientFormState.email.trim();
                      const trimmedConsultationReason = patientFormState.consultationReason.trim();
                      const trimmedLocation = patientFormState.location.trim();
                      const trimmedPhone = patientFormState.phone.trim();
                      const ageValue = Number.parseInt(patientFormState.age, 10);
                      const derivedWhatsappUserId = deriveWhatsappUserId(trimmedPhone);
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
                          "Completa todos los campos del paciente antes de guardar."
                        );
                        return;
                      }
                      if (derivedWhatsappUserId.length < 8) {
                        setLocalSubmitErrorMessage(
                          "Incluye el código de país en el teléfono, ej. +57 300 123 4567"
                        );
                        return;
                      }
                      setLocalSubmitErrorMessage(null);
                      setSubmitSuccessMessage(null);
                      createPatientMutation.mutate(
                        {
                          whatsappUserId: derivedWhatsappUserId,
                          firstName: trimmedFirstName,
                          lastName: trimmedLastName,
                          email: trimmedEmail,
                          age: ageValue,
                          consultationReason: trimmedConsultationReason,
                          location: trimmedLocation,
                          phone: trimmedPhone
                        },
                        {
                          onSuccess: () => {
                            setManualMobileStep("SELECT_PATIENT");
                          }
                        }
                      );
                    }}
                    type="button"
                  >
                    {createPatientMutation.isPending ? "Creando..." : "Crear paciente"}
                  </button>
                </div>
              </article>
            ) : null}

            {manualMobileStep === "APPOINTMENT_FORM" ? (
              <article className="rounded-xl border border-border-subtle bg-white p-3 shadow-card">
                <header className="mb-3 flex items-center gap-2">
                  <button
                    className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
                    onClick={() => {
                      setManualMobileStep("SELECT_PATIENT");
                      setManualMobileSelectedPatientId(null);
                    }}
                    type="button"
                  >
                    <svg
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M15.75 19.5L8.25 12l7.5-7.5"
                      />
                    </svg>
                  </button>
                  <div>
                    <h3 className="text-sm font-semibold text-brand-ink">Nueva cita manual</h3>
                    {(() => {
                      const selectedPatient = allPatients.find(
                        (p) => p.whatsappUserId === manualMobileSelectedPatientId
                      );
                      return selectedPatient !== undefined ? (
                        <p className="text-[11px] text-slate-500">
                          Paciente: {selectedPatient.firstName} {selectedPatient.lastName}
                        </p>
                      ) : null;
                    })()}
                  </div>
                </header>
                <div className="space-y-5">
                  {/* Fecha y hora section */}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-brand-teal">
                      Fecha y hora
                    </p>
                    <div className="mt-2">
                      <slotPickerModule.SlotPicker
                        busyIntervals={manualBusyIntervals}
                        isLoadingAvailability={manualAvailabilityQuery.isLoading}
                        onMonthChange={setManualSlotPickerMonth}
                        onSelectedSlotsChange={(slots) => {
                          setManualAppointmentFormState((currentValue) => ({
                            ...currentValue,
                            selectedSlots: slots.slice(-1)
                          }));
                        }}
                        requestId="manual"
                        selectedSlots={manualAppointmentFormState.selectedSlots}
                        timezone={colombiaTimezone}
                      />
                    </div>
                  </div>

                  <div className="border-t border-border-subtle" />

                  {/* Detalles section */}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-brand-teal">
                      Detalles
                    </p>
                    <div className="mt-2 space-y-3">
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
                          placeholder="Ej. Control mensual"
                          type="text"
                          value={manualAppointmentFormState.summary}
                        />
                      </label>

                      {/* Meet toggle */}
                      <div className="flex items-start gap-3">
                        <button
                          className={[
                            "relative mt-0.5 inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-teal/30",
                            manualAppointmentFormState.isVirtual ? "bg-brand-teal" : "bg-slate-200"
                          ].join(" ")}
                          onClick={() => {
                            setManualAppointmentFormState((currentValue) => ({
                              ...currentValue,
                              isVirtual: !currentValue.isVirtual
                            }));
                          }}
                          role="switch"
                          aria-checked={manualAppointmentFormState.isVirtual}
                          type="button"
                        >
                          <span
                            className={[
                              "inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200",
                              manualAppointmentFormState.isVirtual
                                ? "translate-x-4"
                                : "translate-x-0"
                            ].join(" ")}
                          />
                        </button>
                        <div>
                          <p className="text-sm font-medium text-slate-700">
                            Cita virtual (Google Meet)
                          </p>
                          <p className="text-xs text-slate-500">
                            Se generará un enlace automáticamente.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="mt-5">
                  <button
                    className="w-full rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={createManualAppointmentMutation.isPending}
                    onClick={() => {
                      if (manualAppointmentFormState.patientWhatsappUserId.trim() === "") {
                        setLocalSubmitErrorMessage("Debes seleccionar un paciente.");
                        return;
                      }
                      const [selectedSlot] = manualAppointmentFormState.selectedSlots;
                      if (selectedSlot === undefined) {
                        setLocalSubmitErrorMessage("Debes seleccionar un horario.");
                        return;
                      }
                      setLocalSubmitErrorMessage(null);
                      setSubmitSuccessMessage(null);
                      createManualAppointmentMutation.mutate(
                        {
                          patientWhatsappUserId: manualAppointmentFormState.patientWhatsappUserId,
                          startAt: selectedSlot.startAt,
                          endAt: selectedSlot.endAt,
                          timezone: selectedSlot.timezone,
                          summary:
                            manualAppointmentFormState.summary.trim() === ""
                              ? null
                              : manualAppointmentFormState.summary.trim(),
                          isVirtual: manualAppointmentFormState.isVirtual
                        },
                        {
                          onSuccess: () => {
                            setManualMobileStep("SELECT_PATIENT");
                            setManualMobileSelectedPatientId(null);
                          }
                        }
                      );
                    }}
                    type="button"
                  >
                    {createManualAppointmentMutation.isPending ? "Creando..." : "Agendar cita"}
                  </button>
                </div>
              </article>
            ) : null}
          </div>

          {/* ===== DESKTOP HERO LAYOUT ===== */}
          <div className="hidden sm:block">
            {/* Hero card: centered, max-w-2xl */}
            <div className="mx-auto max-w-2xl">
              <article className="rounded-xl border border-border-subtle bg-white shadow-card">
                {/* Card header */}
                <header className="border-b border-border-subtle px-6 py-5">
                  <h2 className="text-lg font-semibold text-brand-ink">Nueva cita manual</h2>
                  <p className="mt-0.5 text-sm text-slate-500">
                    Selecciona un paciente y define el horario.
                  </p>
                </header>

                <div className="px-6 py-5 space-y-5">
                  {/* Paciente section */}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-brand-teal">
                      Paciente
                    </p>
                    <div className="mt-2 flex items-center gap-3">
                      <div className="relative flex-1">
                        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
                          <svg
                            className="h-4 w-4"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={1.5}
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
                            />
                          </svg>
                        </span>
                        <select
                          aria-label="Paciente"
                          className="w-full rounded-lg border border-border-subtle py-2 pl-9 pr-3 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
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
                              {patient.firstName} {patient.lastName} · {patient.phone}
                            </option>
                          ))}
                        </select>
                      </div>
                      <button
                        className="shrink-0 text-sm font-semibold text-brand-teal transition-colors hover:text-brand-teal-hover"
                        onClick={() => setIsNewPatientModalOpen(true)}
                        type="button"
                      >
                        + Nuevo paciente
                      </button>
                    </div>
                  </div>

                  <div className="border-t border-border-subtle" />

                  {/* Fecha y hora section */}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-brand-teal">
                      Fecha y hora
                    </p>
                    <div className="mt-2">
                      <slotPickerModule.SlotPicker
                        busyIntervals={manualBusyIntervals}
                        isLoadingAvailability={manualAvailabilityQuery.isLoading}
                        onMonthChange={setManualSlotPickerMonth}
                        onSelectedSlotsChange={(slots) => {
                          setManualAppointmentFormState((currentValue) => ({
                            ...currentValue,
                            selectedSlots: slots.slice(-1)
                          }));
                        }}
                        requestId="manual"
                        selectedSlots={manualAppointmentFormState.selectedSlots}
                        timezone={colombiaTimezone}
                      />
                    </div>
                  </div>

                  <div className="border-t border-border-subtle" />

                  {/* Detalles section */}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-brand-teal">
                      Detalles
                    </p>
                    <div className="mt-2 space-y-3">
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
                          placeholder="Ej. Control mensual"
                          type="text"
                          value={manualAppointmentFormState.summary}
                        />
                      </label>

                      {/* Meet toggle */}
                      <div className="flex items-start gap-3">
                        <button
                          className={[
                            "relative mt-0.5 inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-teal/30",
                            manualAppointmentFormState.isVirtual ? "bg-brand-teal" : "bg-slate-200"
                          ].join(" ")}
                          onClick={() => {
                            setManualAppointmentFormState((currentValue) => ({
                              ...currentValue,
                              isVirtual: !currentValue.isVirtual
                            }));
                          }}
                          role="switch"
                          aria-checked={manualAppointmentFormState.isVirtual}
                          type="button"
                        >
                          <span
                            className={[
                              "inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200",
                              manualAppointmentFormState.isVirtual
                                ? "translate-x-4"
                                : "translate-x-0"
                            ].join(" ")}
                          />
                        </button>
                        <div>
                          <p className="text-sm font-medium text-slate-700">
                            Cita virtual (Google Meet)
                          </p>
                          <p className="text-xs text-slate-500">
                            Se generará un enlace automáticamente.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Card footer */}
                <div className="flex items-center justify-between border-t border-border-subtle px-6 py-4">
                  <button
                    className="rounded-lg border border-border-subtle px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                    onClick={() => {
                      setManualAppointmentFormState(emptyManualAppointmentForm());
                      setLocalSubmitErrorMessage(null);
                      setSubmitSuccessMessage(null);
                    }}
                    type="button"
                  >
                    Cancelar
                  </button>
                  <button
                    className="rounded-lg bg-brand-teal px-5 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={
                      createManualAppointmentMutation.isPending ||
                      manualAppointmentFormState.patientWhatsappUserId === "" ||
                      manualAppointmentFormState.selectedSlots.length !== 1
                    }
                    onClick={() => {
                      if (manualAppointmentFormState.patientWhatsappUserId.trim() === "") {
                        setLocalSubmitErrorMessage("Debes seleccionar un paciente.");
                        return;
                      }
                      const [selectedSlot] = manualAppointmentFormState.selectedSlots;
                      if (selectedSlot === undefined) {
                        setLocalSubmitErrorMessage("Debes seleccionar un horario.");
                        return;
                      }
                      setLocalSubmitErrorMessage(null);
                      setSubmitSuccessMessage(null);
                      createManualAppointmentMutation.mutate({
                        patientWhatsappUserId: manualAppointmentFormState.patientWhatsappUserId,
                        startAt: selectedSlot.startAt,
                        endAt: selectedSlot.endAt,
                        timezone: selectedSlot.timezone,
                        summary:
                          manualAppointmentFormState.summary.trim() === ""
                            ? null
                            : manualAppointmentFormState.summary.trim(),
                        isVirtual: manualAppointmentFormState.isVirtual
                      });
                    }}
                    type="button"
                  >
                    {createManualAppointmentMutation.isPending ? "Agendando..." : "Agendar cita"}
                  </button>
                </div>
              </article>

              {/* Error / success feedback */}
              {submitErrorMessage !== null ? (
                <div className="mt-3">
                  <errorBannerModule.ErrorBanner message={submitErrorMessage} />
                </div>
              ) : null}
              {localSubmitErrorMessage !== null ? (
                <div className="mt-3">
                  <errorBannerModule.ErrorBanner message={localSubmitErrorMessage} />
                </div>
              ) : null}
              {submitSuccessMessage !== null ? (
                <div className="mt-3 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                  {submitSuccessMessage}
                </div>
              ) : null}
            </div>

            {/* Manual appointments list — visually lighter, below hero */}
            <div className="mx-auto mt-8 max-w-2xl">
              <h3 className="text-sm font-medium text-brand-ink">Citas manuales agendadas</h3>
              <div className="mt-3 flex flex-wrap gap-2">
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
                      className="rounded-lg border border-slate-200 bg-white p-3"
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
                      {appointment.meetUrl !== null ? (
                        <a
                          className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-brand-teal underline hover:text-brand-teal-hover"
                          href={appointment.meetUrl}
                          rel="noopener noreferrer"
                          target="_blank"
                        >
                          Unirse a Meet
                        </a>
                      ) : null}
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
                                summary: appointment.summary,
                                isVirtual: appointment.isVirtual
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
            </div>
          </div>

          {/* NewPatientModal — rendered for both mobile and desktop */}
          <NewPatientModal
            isOpen={isNewPatientModalOpen}
            isSubmitting={createPatientMutation.isPending}
            onClose={() => setIsNewPatientModalOpen(false)}
            onCreated={(whatsappUserId) => {
              setManualAppointmentFormState((currentValue) => ({
                ...currentValue,
                patientWhatsappUserId: whatsappUserId
              }));
            }}
            onSubmit={async (input) => {
              await createPatientMutation.mutateAsync(input);
            }}
          />

          {/* Mobile error/success feedback */}
          <div className="mt-3 space-y-2 sm:hidden">
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
          </div>
        </section>
      ) : null}

      {isFinanceSection ? (
        <section className="mt-4 space-y-4 sm:mt-6">
          <article className="rounded-xl border border-border-subtle bg-white p-3 shadow-card sm:p-4">
            <header className="mb-4">
              <h3 className="text-sm font-semibold text-brand-ink sm:text-base">Finanzas</h3>
              <p className="text-[11px] text-slate-500 sm:text-xs">
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

import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as appointmentDetailCardModule from "@adapters/inbound/react/components/AppointmentDetailCard";
import * as appointmentDrawerModule from "@adapters/inbound/react/components/AppointmentDrawer";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import { NewManualAppointmentModal } from "@adapters/inbound/react/components/NewManualAppointmentModal";
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

const agendaStatuses: {
  status: schedulingModel.SchedulingRequestStatus;
  label: string;
}[] = [
  { status: "BOOKED", label: "Agendadas" },
  { status: "SESSION_CLOSED", label: "Cerradas" },
  { status: "CANCELLED", label: "Canceladas" },
  { status: "HUMAN_HANDOFF", label: "Human Handoff" }
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

interface BookedAppointmentFormState {
  cancelReason: string;
}

interface PaymentFormState {
  paymentAmountCop: string;
  paymentMethod: "CASH" | "TRANSFER";
  paymentStatus: "PENDING" | "PAID";
}

function emptyBookedAppointmentForm(): BookedAppointmentFormState {
  return {
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
  const [bookedAppointmentFormState, setBookedAppointmentFormState] =
    reactModule.useState<BookedAppointmentFormState>(emptyBookedAppointmentForm());
  const [bookedPaymentFormState, setBookedPaymentFormState] =
    reactModule.useState<PaymentFormState>(emptyPaymentForm());
  const [expandedBookedAction, setExpandedBookedAction] = reactModule.useState<
    "reschedule" | "cancel" | "payment" | "change-modality" | null
  >(null);
  const [desktopDrawerOpen, setDesktopDrawerOpen] = reactModule.useState(false);
  const [drawerPaymentDraft, setDrawerPaymentDraft] = reactModule.useState<{
    amountCop: string;
    category: string;
  }>({ amountCop: "", category: "CASH" });
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

  const filteredRequests = reactModule.useMemo(() => {
    return allRequests.filter((request) => request.status === activeTab);
  }, [allRequests, activeTab]);
  const isBookedTab = activeTab === "BOOKED";
  // Legacy: manual scheduling is now handled by NewManualAppointmentModal
  const [isNewManualModalOpen, setIsNewManualModalOpen] = reactModule.useState(false);

  const patientsByWhatsappUserId = reactModule.useMemo(() => {
    const map = new Map<string, patientModel.Patient>();
    allPatients.forEach((patient) => {
      map.set(patient.whatsappUserId, patient);
    });
    return map;
  }, [allPatients]);

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
    setBookedAppointmentFormState(emptyBookedAppointmentForm());
  }, [selectedBookedAppointment, selectedBookedBotRequest, timezone]);
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

  // Sync drawer payment draft when selected appointment changes
  reactModule.useEffect(() => {
    if (selectedBookedAppointment === null) {
      setDrawerPaymentDraft({ amountCop: "", category: "CASH" });
      return;
    }
    if (
      selectedBookedAppointment.source === "MANUAL" &&
      selectedBookedAppointment.manualAppointment !== null
    ) {
      const ma = selectedBookedAppointment.manualAppointment;
      setDrawerPaymentDraft({
        amountCop: ma.paymentAmountCop == null ? "" : String(ma.paymentAmountCop),
        category: ma.paymentMethod ?? "CASH"
      });
    } else if (
      selectedBookedAppointment.source === "BOT" &&
      selectedBookedAppointment.request !== null
    ) {
      const req = selectedBookedAppointment.request;
      setDrawerPaymentDraft({
        amountCop: req.paymentAmountCop == null ? "" : String(req.paymentAmountCop),
        category: req.paymentMethod ?? "CASH"
      });
    }
  }, [selectedBookedAppointment]);

  // Seed rescheduleSelectedSlots with the current appointment's slot when reschedule opens
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

  // Availability query for the reschedule SlotPicker
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
    enabled:
      expandedBookedAction === "reschedule" &&
      rescheduleMonthFromIso !== null &&
      rescheduleMonthToIso !== null,
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

  const resolvePaymentReviewMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      decision: "APPROVE" | "SEND_REMINDER";
      professionalNote: string | null;
      paymentAmountCop: number | null;
      paymentCurrency: "COP" | "USD";
    }) => {
      return appContainer.schedulingUseCase.resolvePaymentReview(
        payload.request.conversationId,
        payload.request.requestId,
        {
          decision: payload.decision,
          professionalNote: payload.professionalNote,
          paymentAmountCop: payload.paymentAmountCop,
          paymentCurrency: payload.paymentCurrency
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

  const changeModalityMutation = reactQueryModule.useMutation<
    void,
    Error,
    { source: "BOT" | "MANUAL"; id: string; newModality: "PRESENCIAL" | "VIRTUAL" }
  >({
    mutationFn: async (payload) => {
      if (payload.source === "BOT") {
        await appContainer.schedulingUseCase.changeBookedSlotModality(payload.id, {
          newModality: payload.newModality
        });
      } else {
        await appContainer.manualAppointmentUseCase.changeModality(payload.id, {
          newModality: payload.newModality
        });
      }
    },
    onSuccess: async (_data, payload) => {
      const modalityLabel = payload.newModality === "VIRTUAL" ? "virtual" : "presencial";
      setSubmitSuccessMessage(`Modalidad cambiada a ${modalityLabel} correctamente.`);
      setLocalSubmitErrorMessage(null);
      setExpandedBookedAction(null);
      if (payload.source === "BOT") {
        await queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey });
      } else {
        await queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey });
      }
    }
  });

  const submitErrorMessage = uiErrorModule.resolveUiErrorMessage([
    resolvePaymentReviewMutation.error,
    rescheduleManualAppointmentMutation.error,
    cancelManualAppointmentMutation.error,
    updateManualPaymentMutation.error,
    rescheduleBookedSlotMutation.error,
    cancelBookedSlotMutation.error,
    updateBookedPaymentMutation.error,
    changeModalityMutation.error
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

        <div className="flex flex-wrap gap-2">
          {agendaStatuses.map((tab) => (
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
      </section>

      <section className="mt-4">
        <div
          className={["grid gap-4", isBookedTab ? "" : "lg:grid-cols-[320px_minmax(0,1fr)]"].join(
            " "
          )}
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
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold sm:text-base">
                      Calendario de citas agendadas
                    </h3>
                    <p className="text-[11px] text-slate-500 sm:text-xs">
                      Integra citas del chatbot y manuales. Toca un día para ver detalle.
                    </p>
                  </div>
                  <button
                    className="hidden shrink-0 rounded-lg bg-brand-teal px-3 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover sm:block"
                    onClick={() => setIsNewManualModalOpen(true)}
                    type="button"
                  >
                    + Nueva cita manual
                  </button>
                </div>
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
                          <div className="aspect-square rounded-md" key={`mobile-empty-${index}`} />
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
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
                        const isSelectedAppointment = appointment.itemKey === selectedBookedItemKey;
                        const isVirtualAppointment =
                          appointment.source === "MANUAL"
                            ? (appointment.manualAppointment?.isVirtual ?? false)
                            : appointment.request?.appointmentModality === "VIRTUAL";
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
                            <div className="mt-1 flex flex-wrap items-center gap-1.5">
                              <span className="text-[11px] uppercase text-slate-500">
                                {appointment.source === "MANUAL" ? "Manual" : "Chatbot"}
                              </span>
                              <span
                                className={[
                                  "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                                  isVirtualAppointment
                                    ? "bg-brand-accent-light text-brand-teal"
                                    : "bg-slate-100 text-slate-600"
                                ].join(" ")}
                              >
                                {isVirtualAppointment ? "Google Meet" : "Presencial"}
                              </span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Mobile FAB — only in calendar step */}
                {mobileBookedStep === "calendar" ? (
                  <button
                    aria-label="Nueva cita manual"
                    className="fixed bottom-4 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-brand-teal text-white shadow-lg transition-colors hover:bg-brand-teal-hover sm:hidden"
                    onClick={() => setIsNewManualModalOpen(true)}
                    type="button"
                  >
                    <svg
                      className="h-7 w-7"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 4.5v15m7.5-7.5h-15"
                      />
                    </svg>
                  </button>
                ) : null}

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
                          const isPastDay =
                            isoDate !== null && isoDate < (nowDate.toISODate() ?? "");
                          return (
                            <div
                              className={[
                                "min-h-32 rounded-md border p-1.5",
                                isSelectedDay
                                  ? "border-brand-teal bg-brand-accent-light/40"
                                  : isPastDay
                                    ? "border-slate-200 bg-slate-50 opacity-70"
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
                                  const isChatbot = appointment.source === "BOT";
                                  return (
                                    <button
                                      className={[
                                        "w-full rounded border px-1.5 py-1.5 text-left text-[11px] font-semibold transition-colors",
                                        isChatbot
                                          ? "border-brand-teal/40 bg-brand-accent-light text-brand-teal hover:bg-brand-accent-light/70"
                                          : "border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200"
                                      ].join(" ")}
                                      key={appointment.itemKey}
                                      onClick={() => {
                                        setSelectedDayIso(appointment.dayIso);
                                        setSelectedBookedItemKey(appointment.itemKey);
                                        setSelectedRequestId(appointment.requestId);
                                        setSubmitSuccessMessage(null);
                                        setLocalSubmitErrorMessage(null);
                                        setExpandedBookedAction(null);
                                        setDesktopDrawerOpen(true);
                                      }}
                                      title={`${appointment.startAt.toFormat(
                                        "HH:mm"
                                      )} - ${appointment.endAt.toFormat("HH:mm")} | ${
                                        appointment.patientDisplayName
                                      } | ${appointment.source === "MANUAL" ? "Manual" : "Chatbot"}`}
                                      type="button"
                                    >
                                      <span className="block leading-tight">
                                        {appointment.startAt.toFormat("HH:mm")} -{" "}
                                        {appointment.endAt.toFormat("HH:mm")}
                                      </span>
                                      <span className="block truncate leading-tight opacity-80">
                                        {appointment.patientDisplayName}
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
                  {/* Legend */}
                  <div className="mt-2 hidden items-center gap-4 sm:flex">
                    <div className="flex items-center gap-1.5">
                      <span className="inline-block h-2.5 w-2.5 rounded-full bg-brand-teal" />
                      <span className="text-[11px] text-slate-500">Chatbot</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="inline-block h-2.5 w-2.5 rounded-full bg-slate-400" />
                      <span className="text-[11px] text-slate-500">Manual</span>
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
                        const isSelectedAppointment = appointment.itemKey === selectedBookedItemKey;
                        const isChatbot = appointment.source === "BOT";
                        const isVirtualAppointment =
                          appointment.source === "MANUAL"
                            ? (appointment.manualAppointment?.isVirtual ?? false)
                            : appointment.request?.appointmentModality === "VIRTUAL";
                        return (
                          <button
                            className={[
                              "w-full rounded-md border px-2.5 py-2 text-left sm:px-3",
                              isSelectedAppointment && desktopDrawerOpen
                                ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                                : isChatbot
                                  ? "border-brand-teal/30 bg-brand-accent-light/50 text-brand-teal hover:border-brand-teal"
                                  : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                            ].join(" ")}
                            key={`day-${appointment.itemKey}`}
                            onClick={() => {
                              setSelectedDayIso(appointment.dayIso);
                              setSelectedBookedItemKey(appointment.itemKey);
                              setSelectedRequestId(appointment.requestId);
                              setSubmitSuccessMessage(null);
                              setLocalSubmitErrorMessage(null);
                              setExpandedBookedAction(null);
                              setDesktopDrawerOpen(true);
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
                            <div className="mt-1 flex flex-wrap items-center gap-1.5">
                              <span className="text-[11px] uppercase text-slate-500">
                                {appointment.source === "MANUAL" ? "Manual" : "Chatbot"}
                              </span>
                              <span
                                className={[
                                  "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                                  isVirtualAppointment
                                    ? "bg-brand-accent-light text-brand-teal"
                                    : "bg-slate-100 text-slate-600"
                                ].join(" ")}
                              >
                                {isVirtualAppointment ? "Google Meet" : "Presencial"}
                              </span>
                            </div>
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
              isBookedTab && mobileBookedStep !== "detail" ? "hidden" : "",
              isBookedTab && mobileBookedStep === "detail" ? "sm:hidden" : ""
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
            {isBookedTab && selectedBookedAppointment !== null ? (
              <appointmentDetailCardModule.AppointmentDetailCard
                origin={selectedBookedAppointment.source === "MANUAL" ? "MANUAL" : "CHATBOT"}
                modality={
                  selectedBookedAppointment.source === "MANUAL" &&
                  selectedBookedAppointment.manualAppointment !== null
                    ? selectedBookedAppointment.manualAppointment.isVirtual
                      ? "VIRTUAL"
                      : "PRESENCIAL"
                    : selectedBookedAppointment.request?.appointmentModality === "PRESENCIAL"
                      ? "PRESENCIAL"
                      : "VIRTUAL"
                }
                patientFullName={selectedBookedAppointment.patientDisplayName}
                summary={
                  selectedBookedAppointment.source === "MANUAL"
                    ? selectedBookedAppointment.summary
                    : (selectedBookedAppointment.request?.consultationReason ?? null)
                }
                startAt={selectedBookedAppointment.startAt.toISO() ?? ""}
                endAt={selectedBookedAppointment.endAt.toISO() ?? ""}
                timezone={timezone}
                durationMinutes={Math.round(
                  selectedBookedAppointment.endAt.diff(selectedBookedAppointment.startAt, "minutes")
                    .minutes
                )}
                payment={
                  selectedBookedAppointment.source === "MANUAL" &&
                  selectedBookedAppointment.manualAppointment !== null
                    ? {
                        status: selectedBookedAppointment.manualAppointment.paymentStatus ?? null,
                        amountCop: selectedBookedAppointment.manualAppointment.paymentAmountCop,
                        currency: selectedBookedAppointment.manualAppointment.paymentCurrency,
                        category: selectedBookedAppointment.manualAppointment.paymentMethod
                      }
                    : {
                        status: selectedBookedAppointment.request?.paymentStatus ?? null,
                        amountCop: selectedBookedAppointment.request?.paymentAmountCop ?? null,
                        currency: selectedBookedAppointment.request?.paymentCurrency ?? "COP",
                        category: selectedBookedAppointment.request?.paymentMethod ?? null
                      }
                }
                paymentDraft={drawerPaymentDraft}
                onPaymentDraftChange={setDrawerPaymentDraft}
                isSavingPayment={
                  updateManualPaymentMutation.isPending || updateBookedPaymentMutation.isPending
                }
                onSavePayment={() => {
                  const amountCop = Number.parseInt(drawerPaymentDraft.amountCop, 10);
                  if (Number.isNaN(amountCop) || amountCop <= 0) {
                    setLocalSubmitErrorMessage("El valor del pago debe ser mayor a cero.");
                    return;
                  }
                  setLocalSubmitErrorMessage(null);
                  setSubmitSuccessMessage(null);
                  if (
                    selectedBookedAppointment.source === "MANUAL" &&
                    selectedBookedAppointment.manualAppointmentId !== null
                  ) {
                    updateManualPaymentMutation.mutate({
                      appointmentId: selectedBookedAppointment.manualAppointmentId,
                      input: {
                        paymentAmountCop: amountCop,
                        paymentCurrency:
                          selectedBookedAppointment.manualAppointment?.paymentCurrency ?? "COP",
                        paymentMethod: drawerPaymentDraft.category as "CASH" | "TRANSFER",
                        paymentStatus: "PAID"
                      }
                    });
                  } else if (
                    selectedBookedAppointment.source === "BOT" &&
                    selectedBookedAppointment.requestId !== null
                  ) {
                    updateBookedPaymentMutation.mutate({
                      requestId: selectedBookedAppointment.requestId,
                      input: {
                        paymentAmountCop: amountCop,
                        paymentCurrency:
                          selectedBookedAppointment.request?.paymentCurrency ?? "COP",
                        paymentMethod: drawerPaymentDraft.category as "CASH" | "TRANSFER",
                        paymentStatus: "PAID"
                      }
                    });
                  }
                }}
                onReschedule={() => {
                  setExpandedBookedAction(
                    expandedBookedAction === "reschedule" ? null : "reschedule"
                  );
                }}
                {...(selectedBookedAppointment.startAt > nowDate
                  ? {
                      onChangeModality: () => {
                        setLocalSubmitErrorMessage(null);
                        setSubmitSuccessMessage(null);
                        setExpandedBookedAction("change-modality");
                      }
                    }
                  : {})}
                onCancel={() => {
                  if (selectedBookedAppointment === null) {
                    return;
                  }
                  const isConfirmed = window.confirm("¿Seguro que quieres cancelar esta cita?");
                  if (!isConfirmed) {
                    return;
                  }
                  setLocalSubmitErrorMessage(null);
                  setSubmitSuccessMessage(null);
                  if (
                    selectedBookedAppointment.source === "BOT" &&
                    selectedBookedBotRequest !== null
                  ) {
                    cancelBookedSlotMutation.mutate({
                      requestId: selectedBookedBotRequest.requestId,
                      input: { reason: null }
                    });
                  } else if (
                    selectedBookedAppointment.source === "MANUAL" &&
                    selectedBookedAppointment.manualAppointmentId !== null
                  ) {
                    cancelManualAppointmentMutation.mutate({
                      appointmentId: selectedBookedAppointment.manualAppointmentId,
                      input: { reason: null }
                    });
                  }
                }}
                errorMessage={localSubmitErrorMessage ?? submitErrorMessage}
                successMessage={submitSuccessMessage}
              />
            ) : null}

            {/* Expanded action forms for booked tab — shared mobile/desktop */}
            {isBookedTab &&
            selectedBookedAppointment !== null &&
            expandedBookedAction === "reschedule" ? (
              <div
                className="rounded-lg border border-border-subtle p-4 space-y-4"
                data-testid="reschedule-slotpicker-panel"
              >
                <div>
                  <p className="text-sm font-semibold text-brand-ink">Reprogramar cita</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Selecciona un nuevo horario disponible.
                  </p>
                </div>
                <slotPickerModule.SlotPicker
                  timezone={colombiaTimezone}
                  busyIntervals={rescheduleBusyIntervals}
                  requestId={
                    selectedBookedAppointment.source === "MANUAL"
                      ? (selectedBookedAppointment.manualAppointmentId ?? "reschedule")
                      : (selectedBookedAppointment.requestId ?? "reschedule")
                  }
                  selectedSlots={rescheduleSelectedSlots}
                  onSelectedSlotsChange={(slots) => setRescheduleSelectedSlots(slots.slice(-1))}
                  isLoadingAvailability={rescheduleAvailabilityQuery.isLoading}
                  onMonthChange={setRescheduleSlotPickerMonth}
                />
                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={
                      rescheduleSelectedSlots.length !== 1 ||
                      rescheduleManualAppointmentMutation.isPending ||
                      rescheduleBookedSlotMutation.isPending
                    }
                    onClick={() => {
                      const slot = rescheduleSelectedSlots[0];
                      if (slot === undefined) {
                        return;
                      }
                      setLocalSubmitErrorMessage(null);
                      setSubmitSuccessMessage(null);
                      if (
                        selectedBookedAppointment.source === "MANUAL" &&
                        selectedBookedAppointment.manualAppointmentId !== null
                      ) {
                        rescheduleManualAppointmentMutation.mutate({
                          appointmentId: selectedBookedAppointment.manualAppointmentId,
                          input: {
                            startAt: slot.startAt,
                            endAt: slot.endAt,
                            timezone: slot.timezone,
                            summary:
                              selectedBookedAppointment.manualAppointment?.summary.trim() === ""
                                ? null
                                : (selectedBookedAppointment.manualAppointment?.summary ?? null)
                          }
                        });
                      } else if (
                        selectedBookedAppointment.source === "BOT" &&
                        selectedBookedBotRequest !== null
                      ) {
                        const eventSummary =
                          selectedBookedAppointment.patientDisplayName.trim() === ""
                            ? "Cita"
                            : `Cita - ${selectedBookedAppointment.patientDisplayName}`;
                        rescheduleBookedSlotMutation.mutate({
                          requestId: selectedBookedBotRequest.requestId,
                          input: {
                            startAt: slot.startAt,
                            endAt: slot.endAt,
                            timezone: slot.timezone,
                            eventSummary
                          }
                        });
                      }
                    }}
                    type="button"
                  >
                    {rescheduleManualAppointmentMutation.isPending ||
                    rescheduleBookedSlotMutation.isPending
                      ? "Guardando..."
                      : "Guardar reprogramación"}
                  </button>
                  <button
                    className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                    onClick={() => {
                      setExpandedBookedAction(null);
                      setRescheduleSelectedSlots([]);
                    }}
                    type="button"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            ) : null}

            {isBookedTab &&
            selectedBookedAppointment !== null &&
            expandedBookedAction === "change-modality"
              ? (() => {
                  const currentModality =
                    selectedBookedAppointment.source === "MANUAL" &&
                    selectedBookedAppointment.manualAppointment !== null
                      ? selectedBookedAppointment.manualAppointment.isVirtual
                        ? "VIRTUAL"
                        : "PRESENCIAL"
                      : selectedBookedAppointment.request?.appointmentModality === "PRESENCIAL"
                        ? "PRESENCIAL"
                        : "VIRTUAL";
                  const targetModality: "PRESENCIAL" | "VIRTUAL" =
                    currentModality === "PRESENCIAL" ? "VIRTUAL" : "PRESENCIAL";
                  const currentLabel = currentModality === "VIRTUAL" ? "virtual" : "presencial";
                  const targetLabel = targetModality === "VIRTUAL" ? "virtual" : "presencial";
                  const formattedDate = luxonModule.DateTime.fromISO(
                    selectedBookedAppointment.startAt.toISO() ?? "",
                    { setZone: true }
                  )
                    .setZone(timezone)
                    .setLocale("es")
                    .toFormat("EEE dd LLL yyyy");
                  return (
                    <div className="rounded-lg border border-border-subtle p-4 space-y-4">
                      <div>
                        <p className="text-sm font-semibold text-brand-ink">Cambiar modalidad</p>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {`¿Cambiar la cita de ${selectedBookedAppointment.patientDisplayName} del ${formattedDate} de ${currentLabel} a ${targetLabel}?`}
                        </p>
                        <p className="text-xs text-slate-500 mt-1">
                          Se enviará automáticamente un correo al paciente con los nuevos datos del
                          evento.
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2 pt-1">
                        <button
                          className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={changeModalityMutation.isPending}
                          onClick={() => {
                            const source = selectedBookedAppointment.source;
                            const id =
                              source === "BOT"
                                ? (selectedBookedAppointment.requestId ?? "")
                                : (selectedBookedAppointment.manualAppointmentId ?? "");
                            if (id === "") {
                              return;
                            }
                            setLocalSubmitErrorMessage(null);
                            setSubmitSuccessMessage(null);
                            changeModalityMutation.mutate({
                              source,
                              id,
                              newModality: targetModality
                            });
                          }}
                          type="button"
                        >
                          {changeModalityMutation.isPending ? "Guardando..." : "Confirmar cambio"}
                        </button>
                        <button
                          className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                          onClick={() => {
                            setExpandedBookedAction(null);
                          }}
                          type="button"
                        >
                          Cancelar
                        </button>
                      </div>
                    </div>
                  );
                })()
              : null}

            {isBookedTab && selectedBookedAppointment === null ? (
              <p className="text-sm text-slate-500">
                Selecciona una cita en el calendario para ver todos los detalles.
              </p>
            ) : !isBookedTab && selectedRequest === undefined ? (
              <p className="text-sm text-slate-500">
                Selecciona una solicitud para ver detalle y gestionar slots.
              </p>
            ) : !isBookedTab && selectedRequest !== undefined ? (
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
                              paymentAmountCop: null,
                              paymentCurrency: "COP"
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
                      <div
                        className="mt-3 rounded-lg border border-border-subtle p-4 space-y-4"
                        data-testid="reschedule-slotpicker-bot"
                      >
                        <div>
                          <p className="text-sm font-semibold text-brand-ink">Reprogramar cita</p>
                          <p className="text-xs text-slate-500 mt-0.5">
                            Selecciona un nuevo horario disponible.
                          </p>
                        </div>
                        <slotPickerModule.SlotPicker
                          timezone={colombiaTimezone}
                          busyIntervals={rescheduleBusyIntervals}
                          requestId={selectedBookedAppointment?.requestId ?? "reschedule"}
                          selectedSlots={rescheduleSelectedSlots}
                          onSelectedSlotsChange={(slots) =>
                            setRescheduleSelectedSlots(slots.slice(-1))
                          }
                          isLoadingAvailability={rescheduleAvailabilityQuery.isLoading}
                          onMonthChange={setRescheduleSlotPickerMonth}
                        />
                        <div className="flex flex-wrap gap-2 pt-1">
                          <button
                            className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={
                              rescheduleSelectedSlots.length !== 1 ||
                              rescheduleBookedSlotMutation.isPending
                            }
                            onClick={() => {
                              const slot = rescheduleSelectedSlots[0];
                              if (slot === undefined || selectedBookedBotRequest === null) {
                                return;
                              }
                              const eventSummary =
                                selectedBookedAppointment?.patientDisplayName.trim() === ""
                                  ? "Cita"
                                  : `Cita - ${selectedBookedAppointment?.patientDisplayName ?? ""}`;
                              setLocalSubmitErrorMessage(null);
                              setSubmitSuccessMessage(null);
                              rescheduleBookedSlotMutation.mutate({
                                requestId: selectedBookedBotRequest.requestId,
                                input: {
                                  startAt: slot.startAt,
                                  endAt: slot.endAt,
                                  timezone: slot.timezone,
                                  eventSummary
                                }
                              });
                            }}
                            type="button"
                          >
                            {rescheduleBookedSlotMutation.isPending
                              ? "Guardando..."
                              : "Guardar reprogramación"}
                          </button>
                          <button
                            className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                            onClick={() => {
                              setExpandedBookedAction(null);
                              setRescheduleSelectedSlots([]);
                            }}
                            type="button"
                          >
                            Cancelar
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
                            {cancelBookedSlotMutation.isPending ? "Cancelando..." : "Cancelar cita"}
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
                                  paymentCurrency:
                                    selectedBookedBotRequest.paymentCurrency ?? "COP",
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
            ) : null}

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

        {/* Desktop drawer — only for booked tab */}
        {isBookedTab ? (
          <appointmentDrawerModule.AppointmentDrawer
            isOpen={desktopDrawerOpen && selectedBookedAppointment !== null}
            onClose={() => {
              setDesktopDrawerOpen(false);
              setExpandedBookedAction(null);
              setLocalSubmitErrorMessage(null);
              setSubmitSuccessMessage(null);
            }}
          >
            {selectedBookedAppointment !== null ? (
              <>
                <appointmentDetailCardModule.AppointmentDetailCard
                  origin={selectedBookedAppointment.source === "MANUAL" ? "MANUAL" : "CHATBOT"}
                  modality={
                    selectedBookedAppointment.source === "MANUAL" &&
                    selectedBookedAppointment.manualAppointment !== null
                      ? selectedBookedAppointment.manualAppointment.isVirtual
                        ? "VIRTUAL"
                        : "PRESENCIAL"
                      : selectedBookedAppointment.request?.appointmentModality === "PRESENCIAL"
                        ? "PRESENCIAL"
                        : "VIRTUAL"
                  }
                  patientFullName={selectedBookedAppointment.patientDisplayName}
                  summary={
                    selectedBookedAppointment.source === "MANUAL"
                      ? selectedBookedAppointment.summary
                      : (selectedBookedAppointment.request?.consultationReason ?? null)
                  }
                  startAt={selectedBookedAppointment.startAt.toISO() ?? ""}
                  endAt={selectedBookedAppointment.endAt.toISO() ?? ""}
                  timezone={timezone}
                  durationMinutes={Math.round(
                    selectedBookedAppointment.endAt.diff(
                      selectedBookedAppointment.startAt,
                      "minutes"
                    ).minutes
                  )}
                  payment={
                    selectedBookedAppointment.source === "MANUAL" &&
                    selectedBookedAppointment.manualAppointment !== null
                      ? {
                          status: selectedBookedAppointment.manualAppointment.paymentStatus ?? null,
                          amountCop: selectedBookedAppointment.manualAppointment.paymentAmountCop,
                          currency: selectedBookedAppointment.manualAppointment.paymentCurrency,
                          category: selectedBookedAppointment.manualAppointment.paymentMethod
                        }
                      : {
                          status: selectedBookedAppointment.request?.paymentStatus ?? null,
                          amountCop: selectedBookedAppointment.request?.paymentAmountCop ?? null,
                          currency: selectedBookedAppointment.request?.paymentCurrency ?? "COP",
                          category: selectedBookedAppointment.request?.paymentMethod ?? null
                        }
                  }
                  paymentDraft={drawerPaymentDraft}
                  onPaymentDraftChange={setDrawerPaymentDraft}
                  isSavingPayment={
                    updateManualPaymentMutation.isPending || updateBookedPaymentMutation.isPending
                  }
                  onSavePayment={() => {
                    const amountCop = Number.parseInt(drawerPaymentDraft.amountCop, 10);
                    if (Number.isNaN(amountCop) || amountCop <= 0) {
                      setLocalSubmitErrorMessage("El valor del pago debe ser mayor a cero.");
                      return;
                    }
                    setLocalSubmitErrorMessage(null);
                    setSubmitSuccessMessage(null);
                    if (
                      selectedBookedAppointment.source === "MANUAL" &&
                      selectedBookedAppointment.manualAppointmentId !== null
                    ) {
                      updateManualPaymentMutation.mutate({
                        appointmentId: selectedBookedAppointment.manualAppointmentId,
                        input: {
                          paymentAmountCop: amountCop,
                          paymentCurrency:
                            selectedBookedAppointment.manualAppointment?.paymentCurrency ?? "COP",
                          paymentMethod: drawerPaymentDraft.category as "CASH" | "TRANSFER",
                          paymentStatus: "PAID"
                        }
                      });
                    } else if (
                      selectedBookedAppointment.source === "BOT" &&
                      selectedBookedAppointment.requestId !== null
                    ) {
                      updateBookedPaymentMutation.mutate({
                        requestId: selectedBookedAppointment.requestId,
                        input: {
                          paymentAmountCop: amountCop,
                          paymentCurrency:
                            selectedBookedAppointment.request?.paymentCurrency ?? "COP",
                          paymentMethod: drawerPaymentDraft.category as "CASH" | "TRANSFER",
                          paymentStatus: "PAID"
                        }
                      });
                    }
                  }}
                  onReschedule={() => {
                    setExpandedBookedAction(
                      expandedBookedAction === "reschedule" ? null : "reschedule"
                    );
                  }}
                  {...(selectedBookedAppointment.startAt > nowDate
                    ? {
                        onChangeModality: () => {
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          setExpandedBookedAction("change-modality");
                        }
                      }
                    : {})}
                  onCancel={() => {
                    if (selectedBookedAppointment === null) {
                      return;
                    }
                    const isConfirmed = window.confirm("¿Seguro que quieres cancelar esta cita?");
                    if (!isConfirmed) {
                      return;
                    }
                    setLocalSubmitErrorMessage(null);
                    setSubmitSuccessMessage(null);
                    if (
                      selectedBookedAppointment.source === "BOT" &&
                      selectedBookedBotRequest !== null
                    ) {
                      cancelBookedSlotMutation.mutate({
                        requestId: selectedBookedBotRequest.requestId,
                        input: { reason: null }
                      });
                    } else if (
                      selectedBookedAppointment.source === "MANUAL" &&
                      selectedBookedAppointment.manualAppointmentId !== null
                    ) {
                      cancelManualAppointmentMutation.mutate({
                        appointmentId: selectedBookedAppointment.manualAppointmentId,
                        input: { reason: null }
                      });
                    }
                  }}
                  errorMessage={localSubmitErrorMessage ?? submitErrorMessage}
                  successMessage={submitSuccessMessage}
                />

                {/* Expanded change-modality confirmation */}
                {expandedBookedAction === "change-modality"
                  ? (() => {
                      const currentModality =
                        selectedBookedAppointment.source === "MANUAL" &&
                        selectedBookedAppointment.manualAppointment !== null
                          ? selectedBookedAppointment.manualAppointment.isVirtual
                            ? "VIRTUAL"
                            : "PRESENCIAL"
                          : selectedBookedAppointment.request?.appointmentModality === "PRESENCIAL"
                            ? "PRESENCIAL"
                            : "VIRTUAL";
                      const targetModality: "PRESENCIAL" | "VIRTUAL" =
                        currentModality === "PRESENCIAL" ? "VIRTUAL" : "PRESENCIAL";
                      const currentLabel = currentModality === "VIRTUAL" ? "virtual" : "presencial";
                      const targetLabel = targetModality === "VIRTUAL" ? "virtual" : "presencial";
                      const formattedDate = luxonModule.DateTime.fromISO(
                        selectedBookedAppointment.startAt.toISO() ?? "",
                        { setZone: true }
                      )
                        .setZone(timezone)
                        .setLocale("es")
                        .toFormat("EEE dd LLL yyyy");
                      return (
                        <div className="border-t border-border-subtle px-5 py-4 space-y-4">
                          <div>
                            <p className="text-sm font-semibold text-brand-ink">
                              Cambiar modalidad
                            </p>
                            <p className="text-xs text-slate-500 mt-0.5">
                              {`¿Cambiar la cita de ${selectedBookedAppointment.patientDisplayName} del ${formattedDate} de ${currentLabel} a ${targetLabel}?`}
                            </p>
                            <p className="text-xs text-slate-500 mt-1">
                              Se enviará automáticamente un correo al paciente con los nuevos datos
                              del evento.
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2 pt-1">
                            <button
                              className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                              disabled={changeModalityMutation.isPending}
                              onClick={() => {
                                const source = selectedBookedAppointment.source;
                                const id =
                                  source === "BOT"
                                    ? (selectedBookedAppointment.requestId ?? "")
                                    : (selectedBookedAppointment.manualAppointmentId ?? "");
                                if (id === "") {
                                  return;
                                }
                                setLocalSubmitErrorMessage(null);
                                setSubmitSuccessMessage(null);
                                changeModalityMutation.mutate({
                                  source,
                                  id,
                                  newModality: targetModality
                                });
                              }}
                              type="button"
                            >
                              {changeModalityMutation.isPending
                                ? "Guardando..."
                                : "Confirmar cambio"}
                            </button>
                            <button
                              className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                              onClick={() => {
                                setExpandedBookedAction(null);
                              }}
                              type="button"
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      );
                    })()
                  : null}

                {/* Expanded reschedule form */}
                {expandedBookedAction === "reschedule" ? (
                  <div
                    className="border-t border-border-subtle px-5 py-4 space-y-4"
                    data-testid="reschedule-slotpicker-drawer"
                  >
                    <div>
                      <p className="text-sm font-semibold text-brand-ink">Reprogramar cita</p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Selecciona un nuevo horario disponible.
                      </p>
                    </div>
                    <slotPickerModule.SlotPicker
                      timezone={colombiaTimezone}
                      busyIntervals={rescheduleBusyIntervals}
                      requestId={
                        selectedBookedAppointment.source === "MANUAL"
                          ? (selectedBookedAppointment.manualAppointmentId ?? "reschedule")
                          : (selectedBookedAppointment.requestId ?? "reschedule")
                      }
                      selectedSlots={rescheduleSelectedSlots}
                      onSelectedSlotsChange={(slots) => setRescheduleSelectedSlots(slots.slice(-1))}
                      isLoadingAvailability={rescheduleAvailabilityQuery.isLoading}
                      onMonthChange={setRescheduleSlotPickerMonth}
                    />
                    <div className="flex flex-wrap gap-2 pt-1">
                      <button
                        className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={
                          rescheduleSelectedSlots.length !== 1 ||
                          rescheduleManualAppointmentMutation.isPending ||
                          rescheduleBookedSlotMutation.isPending
                        }
                        onClick={() => {
                          const slot = rescheduleSelectedSlots[0];
                          if (slot === undefined) {
                            return;
                          }
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          if (
                            selectedBookedAppointment.source === "MANUAL" &&
                            selectedBookedAppointment.manualAppointmentId !== null
                          ) {
                            rescheduleManualAppointmentMutation.mutate({
                              appointmentId: selectedBookedAppointment.manualAppointmentId,
                              input: {
                                startAt: slot.startAt,
                                endAt: slot.endAt,
                                timezone: slot.timezone,
                                summary:
                                  selectedBookedAppointment.manualAppointment?.summary.trim() === ""
                                    ? null
                                    : (selectedBookedAppointment.manualAppointment?.summary ?? null)
                              }
                            });
                          } else if (
                            selectedBookedAppointment.source === "BOT" &&
                            selectedBookedBotRequest !== null
                          ) {
                            const eventSummary =
                              selectedBookedAppointment.patientDisplayName.trim() === ""
                                ? "Cita"
                                : `Cita - ${selectedBookedAppointment.patientDisplayName}`;
                            rescheduleBookedSlotMutation.mutate({
                              requestId: selectedBookedBotRequest.requestId,
                              input: {
                                startAt: slot.startAt,
                                endAt: slot.endAt,
                                timezone: slot.timezone,
                                eventSummary
                              }
                            });
                          }
                        }}
                        type="button"
                      >
                        {rescheduleManualAppointmentMutation.isPending ||
                        rescheduleBookedSlotMutation.isPending
                          ? "Guardando..."
                          : "Guardar reprogramación"}
                      </button>
                      <button
                        className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                        onClick={() => {
                          setExpandedBookedAction(null);
                          setRescheduleSelectedSlots([]);
                        }}
                        type="button"
                      >
                        Cancelar
                      </button>
                    </div>
                  </div>
                ) : null}

                {/* Expanded cancel form */}
                {expandedBookedAction === "cancel" ? (
                  <div className="border-t border-border-subtle px-5 py-4">
                    <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Cancelar cita
                    </p>
                    <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Motivo de cancelación (opcional)
                      <textarea
                        className="mt-1 min-h-20 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm text-slate-700 transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
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
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        className="rounded-md bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={
                          cancelBookedSlotMutation.isPending ||
                          cancelManualAppointmentMutation.isPending
                        }
                        onClick={() => {
                          const isConfirmed = window.confirm(
                            "¿Seguro que quieres cancelar esta cita?"
                          );
                          if (!isConfirmed) {
                            return;
                          }
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          if (
                            selectedBookedAppointment.source === "BOT" &&
                            selectedBookedBotRequest !== null
                          ) {
                            cancelBookedSlotMutation.mutate({
                              requestId: selectedBookedBotRequest.requestId,
                              input: {
                                reason:
                                  bookedAppointmentFormState.cancelReason.trim() === ""
                                    ? null
                                    : bookedAppointmentFormState.cancelReason.trim()
                              }
                            });
                          } else if (
                            selectedBookedAppointment.source === "MANUAL" &&
                            selectedBookedAppointment.manualAppointmentId !== null
                          ) {
                            cancelManualAppointmentMutation.mutate({
                              appointmentId: selectedBookedAppointment.manualAppointmentId,
                              input: {
                                reason:
                                  bookedAppointmentFormState.cancelReason.trim() === ""
                                    ? null
                                    : bookedAppointmentFormState.cancelReason.trim()
                              }
                            });
                          }
                        }}
                        type="button"
                      >
                        {cancelBookedSlotMutation.isPending ||
                        cancelManualAppointmentMutation.isPending
                          ? "Cancelando..."
                          : "Cancelar cita"}
                      </button>
                      <button
                        className="rounded-lg border border-border-subtle px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                        onClick={() => setExpandedBookedAction(null)}
                        type="button"
                      >
                        Cerrar
                      </button>
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
          </appointmentDrawerModule.AppointmentDrawer>
        ) : null}
      </section>

      <NewManualAppointmentModal
        isOpen={isNewManualModalOpen}
        onClose={() => setIsNewManualModalOpen(false)}
        onCreated={() => {
          void queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey });
        }}
      />
    </appShellModule.AppShell>
  );
}

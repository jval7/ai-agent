import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type { BookedAppointment } from "@adapters/inbound/react/hooks/useBookedAppointments";
import {
  colombiaTimezone,
  manualAppointmentsQueryKey,
  schedulingRequestsQueryKey
} from "@adapters/inbound/react/hooks/useBookedAppointments";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as schedulingModel from "@domain/models/scheduling";
import * as calendarUtilsModule from "@shared/utils/calendar";
import * as uiErrorModule from "@shared/http/ui_error";

interface BookedAppointmentFormState {
  cancelReason: string;
}

export interface PaymentFormState {
  paymentAmountCop: string;
  paymentMethod: "CASH" | "TRANSFER";
  paymentStatus: "PENDING" | "PAID";
}

function emptyBookedAppointmentForm(): BookedAppointmentFormState {
  return { cancelReason: "" };
}

function emptyPaymentForm(): PaymentFormState {
  return {
    paymentAmountCop: "",
    paymentMethod: "CASH",
    paymentStatus: "PENDING"
  };
}

export type ExpandedBookedAction = "reschedule" | "cancel" | "payment" | "change-modality" | null;

export interface UseAgendaActionsResult {
  // Form state
  bookedAppointmentFormState: BookedAppointmentFormState;
  setBookedAppointmentFormState: reactModule.Dispatch<
    reactModule.SetStateAction<BookedAppointmentFormState>
  >;
  bookedPaymentFormState: PaymentFormState;
  setBookedPaymentFormState: reactModule.Dispatch<reactModule.SetStateAction<PaymentFormState>>;
  expandedBookedAction: ExpandedBookedAction;
  setExpandedBookedAction: (action: ExpandedBookedAction) => void;
  drawerPaymentDraft: { amountCop: string; category: string };
  setDrawerPaymentDraft: reactModule.Dispatch<
    reactModule.SetStateAction<{ amountCop: string; category: string }>
  >;
  // Reschedule state
  rescheduleSlotPickerMonth: { year: number; month: number };
  setRescheduleSlotPickerMonth: (month: { year: number; month: number }) => void;
  rescheduleSelectedSlots: { slotId: string; startAt: string; endAt: string; timezone: string }[];
  setRescheduleSelectedSlots: reactModule.Dispatch<
    reactModule.SetStateAction<
      { slotId: string; startAt: string; endAt: string; timezone: string }[]
    >
  >;
  rescheduleBusyIntervals: calendarUtilsModule.BusyIntervalRange[];
  rescheduleAvailabilityQuery: { isLoading: boolean };
  // Messages
  localSubmitErrorMessage: string | null;
  setLocalSubmitErrorMessage: (msg: string | null) => void;
  submitSuccessMessage: string | null;
  setSubmitSuccessMessage: (msg: string | null) => void;
  submitErrorMessage: string | null;
  // Aggregated pending flags
  isSavingPayment: boolean;
  isReschedulePending: boolean;
  isCancelPending: boolean;
  isChangeModalityPending: boolean;
  isPaymentReminderPending: boolean;
  isUpdateBotPaymentPending: boolean;
  // Handlers
  handleSavePayment: (appointment: BookedAppointment) => void;
  handleCancel: (appointment: BookedAppointment) => void;
  handleReschedule: (appointment: BookedAppointment) => void;
  handleChangeModality: (
    appointment: BookedAppointment,
    newModality: "PRESENCIAL" | "VIRTUAL"
  ) => void;
  handleSendPaymentReminder: (
    request: schedulingModel.SchedulingRequestSummary,
    bookedRequest: schedulingModel.SchedulingRequestSummary | null
  ) => void;
  /** Cancel a bot slot by requestId with optional reason — used in inline cancel form */
  handleCancelBotSlot: (requestId: string, reason: string | null) => void;
  /** Cancel a manual appointment by appointmentId with optional reason — used in inline cancel form */
  handleCancelManualAppointment: (appointmentId: string, reason: string | null) => void;
  /** Update bot payment directly from inline form */
  handleUpdateBotPayment: (
    requestId: string,
    paymentAmountCop: number,
    paymentCurrency: "COP" | "USD",
    paymentMethod: "CASH" | "TRANSFER",
    paymentStatus: "PENDING" | "PAID"
  ) => void;
}

export function useAgendaActions(options: {
  selectedBookedAppointment: BookedAppointment | null;
  timezone: string;
}): UseAgendaActionsResult {
  const { selectedBookedAppointment, timezone } = options;
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const [bookedAppointmentFormState, setBookedAppointmentFormState] =
    reactModule.useState<BookedAppointmentFormState>(emptyBookedAppointmentForm());
  const [bookedPaymentFormState, setBookedPaymentFormState] =
    reactModule.useState<PaymentFormState>(emptyPaymentForm());
  const [expandedBookedAction, setExpandedBookedAction] =
    reactModule.useState<ExpandedBookedAction>(null);
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
  const [localSubmitErrorMessage, setLocalSubmitErrorMessage] = reactModule.useState<string | null>(
    null
  );
  const [submitSuccessMessage, setSubmitSuccessMessage] = reactModule.useState<string | null>(null);

  const selectedBookedBotRequest =
    selectedBookedAppointment?.source === "BOT" ? selectedBookedAppointment.request : null;

  // Reset form state when selected appointment changes
  reactModule.useEffect(() => {
    setExpandedBookedAction(null);
    setBookedAppointmentFormState(emptyBookedAppointmentForm());
  }, [selectedBookedAppointment, selectedBookedBotRequest, timezone]);

  // Seed payment form from selected bot request
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
    const currentStartMs = selectedBookedAppointment.startAt.setZone(colombiaTimezone).toMillis();
    const currentEndMs = selectedBookedAppointment.endAt.setZone(colombiaTimezone).toMillis();
    return allBusy.filter((interval) => {
      return !(
        interval.start.toMillis() === currentStartMs && interval.end.toMillis() === currentEndMs
      );
    });
  }, [rescheduleAvailabilityQuery.data, selectedBookedAppointment]);

  // Mutations
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

  // High-level handlers
  function handleSavePayment(appointment: BookedAppointment): void {
    const amountCop = Number.parseInt(drawerPaymentDraft.amountCop, 10);
    if (Number.isNaN(amountCop) || amountCop <= 0) {
      setLocalSubmitErrorMessage("El valor del pago debe ser mayor a cero.");
      return;
    }
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    if (appointment.source === "MANUAL" && appointment.manualAppointmentId !== null) {
      updateManualPaymentMutation.mutate({
        appointmentId: appointment.manualAppointmentId,
        input: {
          paymentAmountCop: amountCop,
          paymentCurrency: appointment.manualAppointment?.paymentCurrency ?? "COP",
          paymentMethod: drawerPaymentDraft.category as "CASH" | "TRANSFER",
          paymentStatus: "PAID"
        }
      });
    } else if (appointment.source === "BOT" && appointment.requestId !== null) {
      updateBookedPaymentMutation.mutate({
        requestId: appointment.requestId,
        input: {
          paymentAmountCop: amountCop,
          paymentCurrency: appointment.request?.paymentCurrency ?? "COP",
          paymentMethod: drawerPaymentDraft.category as "CASH" | "TRANSFER",
          paymentStatus: "PAID"
        }
      });
    }
  }

  function handleCancel(appointment: BookedAppointment): void {
    const isConfirmed = window.confirm("¿Seguro que quieres cancelar esta cita?");
    if (!isConfirmed) {
      return;
    }
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    if (appointment.source === "BOT" && appointment.requestId !== null) {
      cancelBookedSlotMutation.mutate({
        requestId: appointment.requestId,
        input: { reason: null }
      });
    } else if (appointment.source === "MANUAL" && appointment.manualAppointmentId !== null) {
      cancelManualAppointmentMutation.mutate({
        appointmentId: appointment.manualAppointmentId,
        input: { reason: null }
      });
    }
  }

  function handleReschedule(appointment: BookedAppointment): void {
    const slot = rescheduleSelectedSlots[0];
    if (slot === undefined) {
      return;
    }
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    if (appointment.source === "MANUAL" && appointment.manualAppointmentId !== null) {
      rescheduleManualAppointmentMutation.mutate({
        appointmentId: appointment.manualAppointmentId,
        input: {
          startAt: slot.startAt,
          endAt: slot.endAt,
          timezone: slot.timezone,
          summary:
            appointment.manualAppointment?.summary.trim() === ""
              ? null
              : (appointment.manualAppointment?.summary ?? null)
        }
      });
    } else if (appointment.source === "BOT" && appointment.requestId !== null) {
      const eventSummary =
        appointment.patientDisplayName.trim() === ""
          ? "Cita"
          : `Cita - ${appointment.patientDisplayName}`;
      rescheduleBookedSlotMutation.mutate({
        requestId: appointment.requestId,
        input: {
          startAt: slot.startAt,
          endAt: slot.endAt,
          timezone: slot.timezone,
          eventSummary
        }
      });
    }
  }

  function handleChangeModality(
    appointment: BookedAppointment,
    newModality: "PRESENCIAL" | "VIRTUAL"
  ): void {
    const id =
      appointment.source === "BOT"
        ? (appointment.requestId ?? "")
        : (appointment.manualAppointmentId ?? "");
    if (id === "") {
      return;
    }
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    changeModalityMutation.mutate({
      source: appointment.source,
      id,
      newModality
    });
  }

  function handleSendPaymentReminder(
    request: schedulingModel.SchedulingRequestSummary,
    _bookedRequest: schedulingModel.SchedulingRequestSummary | null
  ): void {
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    resolvePaymentReviewMutation.mutate({
      request,
      decision: "SEND_REMINDER",
      professionalNote: null,
      paymentAmountCop: null,
      paymentCurrency: "COP"
    });
  }

  function handleCancelBotSlot(requestId: string, reason: string | null): void {
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    cancelBookedSlotMutation.mutate({ requestId, input: { reason } });
  }

  function handleCancelManualAppointment(appointmentId: string, reason: string | null): void {
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    cancelManualAppointmentMutation.mutate({ appointmentId, input: { reason } });
  }

  function handleUpdateBotPayment(
    requestId: string,
    paymentAmountCop: number,
    paymentCurrency: "COP" | "USD",
    paymentMethod: "CASH" | "TRANSFER",
    paymentStatus: "PENDING" | "PAID"
  ): void {
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    updateBookedPaymentMutation.mutate({
      requestId,
      input: { paymentAmountCop, paymentCurrency, paymentMethod, paymentStatus }
    });
  }

  return {
    bookedAppointmentFormState,
    setBookedAppointmentFormState,
    bookedPaymentFormState,
    setBookedPaymentFormState,
    expandedBookedAction,
    setExpandedBookedAction,
    drawerPaymentDraft,
    setDrawerPaymentDraft,
    rescheduleSlotPickerMonth,
    setRescheduleSlotPickerMonth,
    rescheduleSelectedSlots,
    setRescheduleSelectedSlots,
    rescheduleBusyIntervals,
    rescheduleAvailabilityQuery,
    localSubmitErrorMessage,
    setLocalSubmitErrorMessage,
    submitSuccessMessage,
    setSubmitSuccessMessage,
    submitErrorMessage,
    isSavingPayment: updateManualPaymentMutation.isPending || updateBookedPaymentMutation.isPending,
    isReschedulePending:
      rescheduleManualAppointmentMutation.isPending || rescheduleBookedSlotMutation.isPending,
    isCancelPending:
      cancelBookedSlotMutation.isPending || cancelManualAppointmentMutation.isPending,
    isChangeModalityPending: changeModalityMutation.isPending,
    isPaymentReminderPending: resolvePaymentReviewMutation.isPending,
    isUpdateBotPaymentPending: updateBookedPaymentMutation.isPending,
    handleSavePayment,
    handleCancel,
    handleReschedule,
    handleChangeModality,
    handleSendPaymentReminder,
    handleCancelBotSlot,
    handleCancelManualAppointment,
    handleUpdateBotPayment
  };
}

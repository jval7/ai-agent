import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as schedulingModel from "@domain/models/scheduling";
import * as uiErrorModule from "@shared/http/ui_error";

import {
  schedulingRequestsQueryKey,
  manualAppointmentsQueryKey
} from "@adapters/inbound/react/hooks/useAgendaData";

export interface BookedAppointmentFormState {
  cancelReason: string;
}

export interface PaymentFormState {
  paymentAmountCop: string;
  paymentMethod: "CASH" | "TRANSFER";
  paymentStatus: "PENDING" | "PAID";
}

export function emptyBookedAppointmentForm(): BookedAppointmentFormState {
  return { cancelReason: "" };
}

export function emptyPaymentForm(): PaymentFormState {
  return {
    paymentAmountCop: "",
    paymentMethod: "CASH",
    paymentStatus: "PENDING"
  };
}

export function useAgendaActions(options: {
  setActiveTab: (tab: schedulingModel.SchedulingRequestStatus) => void;
}) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const [bookedAppointmentFormState, setBookedAppointmentFormState] =
    reactModule.useState<BookedAppointmentFormState>(emptyBookedAppointmentForm());
  const [bookedPaymentFormState, setBookedPaymentFormState] =
    reactModule.useState<PaymentFormState>(emptyPaymentForm());
  const [drawerPaymentDraft, setDrawerPaymentDraft] = reactModule.useState<{
    amountCop: string;
    category: string;
  }>({ amountCop: "", category: "CASH" });
  const [localSubmitErrorMessage, setLocalSubmitErrorMessage] = reactModule.useState<string | null>(
    null
  );
  const [submitSuccessMessage, setSubmitSuccessMessage] = reactModule.useState<string | null>(null);

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
      options.setActiveTab(result.status);
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

  return {
    bookedAppointmentFormState,
    setBookedAppointmentFormState,
    bookedPaymentFormState,
    setBookedPaymentFormState,
    drawerPaymentDraft,
    setDrawerPaymentDraft,
    localSubmitErrorMessage,
    setLocalSubmitErrorMessage,
    submitSuccessMessage,
    setSubmitSuccessMessage,
    submitErrorMessage,
    resolvePaymentReviewMutation,
    rescheduleManualAppointmentMutation,
    cancelManualAppointmentMutation,
    updateManualPaymentMutation,
    rescheduleBookedSlotMutation,
    cancelBookedSlotMutation,
    updateBookedPaymentMutation,
    changeModalityMutation
  };
}

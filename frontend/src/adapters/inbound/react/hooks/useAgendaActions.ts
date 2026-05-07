import type * as reactModule from "react";

import * as useAgendaQueryModule from "@adapters/inbound/react/hooks/useAgendaQuery";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as schedulingModel from "@domain/models/scheduling";
import * as uiErrorModule from "@shared/http/ui_error";

interface UseAgendaActionsParams {
  tenantId: string | undefined;
  setSubmitSuccessMessage: reactModule.Dispatch<reactModule.SetStateAction<string | null>>;
  setLocalSubmitErrorMessage: reactModule.Dispatch<reactModule.SetStateAction<string | null>>;
  setActiveTab: reactModule.Dispatch<
    reactModule.SetStateAction<schedulingModel.SchedulingRequestStatus>
  >;
  setExpandedBookedAction: reactModule.Dispatch<
    reactModule.SetStateAction<"reschedule" | "cancel" | "payment" | "change-modality" | null>
  >;
}

export function useAgendaActions({
  tenantId,
  setSubmitSuccessMessage,
  setLocalSubmitErrorMessage,
  setActiveTab,
  setExpandedBookedAction
}: UseAgendaActionsParams) {
  const resolvePaymentReviewMutation =
    useAgendaQueryModule.useAgendaResolvePaymentReviewMutation(tenantId);
  const rescheduleManualAppointmentMutation =
    useAgendaQueryModule.useAgendaRescheduleManualAppointmentMutation(tenantId);
  const cancelManualAppointmentMutation =
    useAgendaQueryModule.useAgendaCancelManualAppointmentMutation(tenantId);
  const updateManualPaymentMutation =
    useAgendaQueryModule.useAgendaUpdateManualPaymentMutation(tenantId);
  const rescheduleBookedSlotMutation =
    useAgendaQueryModule.useAgendaRescheduleBookedSlotMutation(tenantId);
  const cancelBookedSlotMutation = useAgendaQueryModule.useAgendaCancelBookedSlotMutation(tenantId);
  const updateBookedPaymentMutation =
    useAgendaQueryModule.useAgendaUpdateBookedPaymentMutation(tenantId);
  const changeModalityMutation = useAgendaQueryModule.useAgendaChangeModalityMutation(tenantId);

  const handleRescheduleManualAppointment = (payload: {
    appointmentId: string;
    input: manualAppointmentModel.RescheduleManualAppointmentInput;
  }) => {
    rescheduleManualAppointmentMutation.mutate(payload, {
      onSuccess: () => {
        setSubmitSuccessMessage("Cita manual reprogramada correctamente.");
        setLocalSubmitErrorMessage(null);
      }
    });
  };

  const handleCancelManualAppointment = (payload: {
    appointmentId: string;
    input: manualAppointmentModel.CancelManualAppointmentInput;
  }) => {
    cancelManualAppointmentMutation.mutate(payload, {
      onSuccess: () => {
        setSubmitSuccessMessage("Cita manual cancelada correctamente.");
        setLocalSubmitErrorMessage(null);
      }
    });
  };

  const handleUpdateManualPayment = (payload: {
    appointmentId: string;
    input: manualAppointmentModel.UpdateManualAppointmentPaymentInput;
  }) => {
    updateManualPaymentMutation.mutate(payload, {
      onSuccess: () => {
        setSubmitSuccessMessage("Pago de cita manual actualizado.");
        setLocalSubmitErrorMessage(null);
      }
    });
  };

  const handleRescheduleBookedSlot = (payload: {
    requestId: string;
    input: schedulingModel.RescheduleBookedSlotInput;
  }) => {
    rescheduleBookedSlotMutation.mutate(payload, {
      onSuccess: () => {
        setSubmitSuccessMessage("Cita del chatbot reprogramada correctamente.");
        setLocalSubmitErrorMessage(null);
      }
    });
  };

  const handleCancelBookedSlot = (payload: {
    requestId: string;
    input: schedulingModel.CancelBookedSlotInput;
  }) => {
    cancelBookedSlotMutation.mutate(payload, {
      onSuccess: () => {
        setSubmitSuccessMessage("Cita del chatbot cancelada correctamente.");
        setLocalSubmitErrorMessage(null);
      }
    });
  };

  const handleUpdateBookedPayment = (payload: {
    requestId: string;
    input: schedulingModel.UpdateBookedSlotPaymentInput;
  }) => {
    updateBookedPaymentMutation.mutate(payload, {
      onSuccess: () => {
        setSubmitSuccessMessage("Pago de cita chatbot actualizado.");
        setLocalSubmitErrorMessage(null);
      }
    });
  };

  const handleChangeModality = (payload: {
    source: "BOT" | "MANUAL";
    id: string;
    newModality: "PRESENCIAL" | "VIRTUAL";
  }) => {
    changeModalityMutation.mutate(payload, {
      onSuccess: () => {
        const modalityLabel = payload.newModality === "VIRTUAL" ? "virtual" : "presencial";
        setSubmitSuccessMessage(`Modalidad cambiada a ${modalityLabel} correctamente.`);
        setLocalSubmitErrorMessage(null);
        setExpandedBookedAction(null);
      }
    });
  };

  const handleResolvePaymentReview = (payload: {
    request: schedulingModel.SchedulingRequestSummary;
    decision: "APPROVE" | "SEND_REMINDER";
    professionalNote: string | null;
    paymentAmountCop: number | null;
    paymentCurrency: "COP" | "USD";
  }) => {
    resolvePaymentReviewMutation.mutate(payload, {
      onSuccess: (result) => {
        setSubmitSuccessMessage(result.assistantText);
        setLocalSubmitErrorMessage(null);
        setActiveTab(result.status);
      }
    });
  };

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
    // mutations (for pending states)
    resolvePaymentReviewMutation,
    rescheduleManualAppointmentMutation,
    cancelManualAppointmentMutation,
    updateManualPaymentMutation,
    rescheduleBookedSlotMutation,
    cancelBookedSlotMutation,
    updateBookedPaymentMutation,
    changeModalityMutation,
    // handlers
    handleRescheduleManualAppointment,
    handleCancelManualAppointment,
    handleUpdateManualPayment,
    handleRescheduleBookedSlot,
    handleCancelBookedSlot,
    handleUpdateBookedPayment,
    handleChangeModality,
    handleResolvePaymentReview,
    // derived error
    submitErrorMessage
  };
}

import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as schedulingModel from "@domain/models/scheduling";

function schedulingRequestsQueryKey(tenantId?: string) {
  return tenantId !== undefined
    ? ["admin", tenantId, "scheduling-requests"]
    : ["scheduling-requests"];
}

function patientsQueryKey(tenantId?: string) {
  return tenantId !== undefined ? ["admin", tenantId, "patients"] : ["patients"];
}

function manualAppointmentsQueryKey(tenantId?: string) {
  return tenantId !== undefined
    ? ["admin", tenantId, "manual-appointments"]
    : ["manual-appointments"];
}

function googleCalendarConnectionQueryKey(tenantId?: string) {
  return tenantId !== undefined
    ? ["admin", tenantId, "google-calendar-connection"]
    : ["google-calendar-connection"];
}

export function useAgendaSchedulingRequestsQuery(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: schedulingRequestsQueryKey(tenantId),
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListSchedulingRequests(tenantId)
        : appContainer.schedulingUseCase.listRequests(),
    refetchInterval: 60_000
  });
}

export function useAgendaGoogleCalendarConnectionQuery(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: googleCalendarConnectionQueryKey(tenantId),
    queryFn: () =>
      tenantId !== undefined
        ? Promise.resolve(null)
        : appContainer.onboardingUseCase.getGoogleCalendarConnectionStatus()
  });
}

export function useAgendaPatientsQuery(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: patientsQueryKey(tenantId),
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListPatients(tenantId)
        : appContainer.patientUseCase.listPatients()
  });
}

export function useAgendaManualAppointmentsQuery(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: manualAppointmentsQueryKey(tenantId),
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListManualAppointments(tenantId)
        : appContainer.manualAppointmentUseCase.listAppointments()
  });
}

export function useAgendaAvailabilityQuery(
  params: {
    fromIso: string | null;
    toIso: string | null;
    enabled: boolean;
  },
  tenantId?: string
) {
  const appContainer = appContainerContextModule.useAppContainer();
  const key =
    tenantId !== undefined
      ? [
          "admin",
          tenantId,
          "google-calendar-availability",
          "reschedule",
          params.fromIso,
          params.toIso
        ]
      : ["google-calendar-availability", "reschedule", params.fromIso, params.toIso];
  return reactQueryModule.useQuery({
    queryKey: key,
    enabled: params.enabled && params.fromIso !== null && params.toIso !== null,
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminGetGoogleCalendarAvailability(
            tenantId,
            params.fromIso!,
            params.toIso!
          )
        : appContainer.schedulingUseCase.getAvailability(params.fromIso!, params.toIso!)
  });
}

export function useAgendaCreateManualAppointmentMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (input: manualAppointmentModel.CreateManualAppointmentInput) =>
      tenantId !== undefined
        ? appContainer.api.adminCreateManualAppointment(tenantId, input)
        : appContainer.manualAppointmentUseCase.createAppointment(input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey(tenantId) });
    }
  });
}

export function useAgendaRescheduleManualAppointmentMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (payload: {
      appointmentId: string;
      input: manualAppointmentModel.RescheduleManualAppointmentInput;
    }) =>
      tenantId !== undefined
        ? appContainer.api.adminRescheduleManualAppointment(
            tenantId,
            payload.appointmentId,
            payload.input
          )
        : appContainer.manualAppointmentUseCase.rescheduleAppointment(
            payload.appointmentId,
            payload.input
          ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey(tenantId) });
    }
  });
}

export function useAgendaCancelManualAppointmentMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (payload: {
      appointmentId: string;
      input: manualAppointmentModel.CancelManualAppointmentInput;
    }) =>
      tenantId !== undefined
        ? appContainer.api.adminCancelManualAppointment(
            tenantId,
            payload.appointmentId,
            payload.input
          )
        : appContainer.manualAppointmentUseCase.cancelAppointment(
            payload.appointmentId,
            payload.input
          ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey(tenantId) });
    }
  });
}

export function useAgendaUpdateManualPaymentMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (payload: {
      appointmentId: string;
      input: manualAppointmentModel.UpdateManualAppointmentPaymentInput;
    }) =>
      tenantId !== undefined
        ? appContainer.api.adminUpdateManualAppointmentPayment(
            tenantId,
            payload.appointmentId,
            payload.input
          )
        : appContainer.manualAppointmentUseCase.updatePayment(payload.appointmentId, payload.input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey(tenantId) });
    }
  });
}

export function useAgendaRescheduleBookedSlotMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (payload: {
      requestId: string;
      input: schedulingModel.RescheduleBookedSlotInput;
    }) =>
      tenantId !== undefined
        ? appContainer.api.adminRescheduleBookedSlot(tenantId, payload.requestId, payload.input)
        : appContainer.schedulingUseCase.rescheduleBookedSlot(payload.requestId, payload.input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey(tenantId) });
    }
  });
}

export function useAgendaCancelBookedSlotMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (payload: { requestId: string; input: schedulingModel.CancelBookedSlotInput }) =>
      tenantId !== undefined
        ? appContainer.api.adminCancelBookedSlot(tenantId, payload.requestId, payload.input)
        : appContainer.schedulingUseCase.cancelBookedSlot(payload.requestId, payload.input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey(tenantId) });
    }
  });
}

export function useAgendaUpdateBookedPaymentMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (payload: {
      requestId: string;
      input: schedulingModel.UpdateBookedSlotPaymentInput;
    }) =>
      tenantId !== undefined
        ? appContainer.api.adminUpdateBookedSlotPayment(tenantId, payload.requestId, payload.input)
        : appContainer.schedulingUseCase.updateBookedPayment(payload.requestId, payload.input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey(tenantId) });
    }
  });
}

export function useAgendaChangeModalityMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation<
    void,
    Error,
    { source: "BOT" | "MANUAL"; id: string; newModality: "PRESENCIAL" | "VIRTUAL" }
  >({
    mutationFn: async (payload) => {
      if (payload.source === "BOT") {
        if (tenantId !== undefined) {
          await appContainer.api.adminChangeBookedSlotModality(tenantId, payload.id, {
            newModality: payload.newModality
          });
        } else {
          await appContainer.schedulingUseCase.changeBookedSlotModality(payload.id, {
            newModality: payload.newModality
          });
        }
      } else {
        if (tenantId !== undefined) {
          await appContainer.api.adminChangeManualAppointmentModality(tenantId, payload.id, {
            newModality: payload.newModality
          });
        } else {
          await appContainer.manualAppointmentUseCase.changeModality(payload.id, {
            newModality: payload.newModality
          });
        }
      }
    },
    onSuccess: async (_data, payload) => {
      if (payload.source === "BOT") {
        await queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey(tenantId) });
      } else {
        await queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey(tenantId) });
      }
    }
  });
}

export function useAgendaResolvePaymentReviewMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      decision: "APPROVE" | "SEND_REMINDER";
      professionalNote: string | null;
      paymentAmountCop: number | null;
      paymentCurrency: "COP" | "USD";
    }) =>
      tenantId !== undefined
        ? appContainer.api.adminResolvePaymentReview(
            tenantId,
            payload.request.conversationId,
            payload.request.requestId,
            {
              decision: payload.decision,
              professionalNote: payload.professionalNote,
              paymentAmountCop: payload.paymentAmountCop,
              paymentCurrency: payload.paymentCurrency
            }
          )
        : appContainer.schedulingUseCase.resolvePaymentReview(
            payload.request.conversationId,
            payload.request.requestId,
            {
              decision: payload.decision,
              professionalNote: payload.professionalNote,
              paymentAmountCop: payload.paymentAmountCop,
              paymentCurrency: payload.paymentCurrency
            }
          ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey(tenantId) });
    }
  });
}

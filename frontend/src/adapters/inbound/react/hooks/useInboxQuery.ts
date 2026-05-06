import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as conversationModel from "@domain/models/conversation";
import type * as schedulingModel from "@domain/models/scheduling";

function conversationsQueryKey(tenantId?: string) {
  return tenantId !== undefined ? ["admin", tenantId, "conversations"] : ["conversations"];
}

function blacklistQueryKey(tenantId?: string) {
  return tenantId !== undefined ? ["admin", tenantId, "blacklist"] : ["blacklist"];
}

function schedulingRequestsQueryKey(tenantId?: string) {
  return tenantId !== undefined
    ? ["admin", tenantId, "scheduling-requests"]
    : ["scheduling-requests"];
}

function devFeaturesQueryKey() {
  return ["dev-features"] as const;
}

function agentSettingsQueryKey(tenantId?: string) {
  return tenantId !== undefined ? ["admin", tenantId, "agent-settings"] : ["agent-settings"];
}

function patientsQueryKey(tenantId?: string) {
  return tenantId !== undefined ? ["admin", tenantId, "patients"] : ["patients"];
}

export function useInboxPatientsQuery(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: patientsQueryKey(tenantId),
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListPatients(tenantId)
        : appContainer.patientUseCase.listPatients()
  });
}

export function useConversationsQuery(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: conversationsQueryKey(tenantId),
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListConversations(tenantId)
        : appContainer.conversationUseCase.listConversations(),
    refetchInterval: 5_000
  });
}

export function useConversationMessagesQuery(
  selectedConversationId: string | null,
  tenantId?: string
) {
  const appContainer = appContainerContextModule.useAppContainer();
  const key =
    tenantId !== undefined
      ? ["admin", tenantId, "conversation-messages", selectedConversationId]
      : ["conversation-messages", selectedConversationId];
  return reactQueryModule.useQuery({
    queryKey: key,
    enabled: selectedConversationId !== null,
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListConversationMessages(tenantId, selectedConversationId ?? "")
        : appContainer.conversationUseCase.listMessages(selectedConversationId ?? ""),
    refetchInterval: 5_000
  });
}

export function useBlacklistQuery(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: blacklistQueryKey(tenantId),
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListBlacklist(tenantId)
        : appContainer.blacklistUseCase.list()
  });
}

export function useInboxSchedulingRequestsQuery(tenantId?: string) {
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

export function useDevFeaturesQuery() {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: devFeaturesQueryKey(),
    queryFn: () => appContainer.agentUseCase.getDevFeatures(),
    staleTime: Infinity
  });
}

export function useInboxAgentSettingsQuery(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: agentSettingsQueryKey(tenantId),
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminGetAgentSettings(tenantId)
        : appContainer.agentUseCase.getAgentSettings()
  });
}

export function useControlModeMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: ({
      conversationId,
      controlMode
    }: {
      conversationId: string;
      controlMode: conversationModel.ControlMode;
    }) =>
      tenantId !== undefined
        ? appContainer.api.adminUpdateConversationControlMode(tenantId, conversationId, controlMode)
        : appContainer.conversationUseCase.updateControlMode(conversationId, controlMode),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: conversationsQueryKey(tenantId) });
    }
  });
}

export function useAssistantEnabledMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: async (assistantEnabled: boolean) => {
      const fresh =
        tenantId !== undefined
          ? queryClient.getQueryData<{ assistantEnabled: boolean }>(agentSettingsQueryKey(tenantId))
          : queryClient.getQueryData<{ assistantEnabled: boolean }>(agentSettingsQueryKey());
      if (fresh === undefined) {
        throw new Error("Agent settings not loaded yet");
      }
      if (tenantId !== undefined) {
        const fullSettings = queryClient.getQueryData<{
          messageDebounceDelaySeconds: number;
          assistantEnabled: boolean;
          appointmentReminderEnabled: boolean;
          appointmentReminderDaysBefore: number | null;
          appointmentReminderAttendanceTemplateName: string | null;
          appointmentReminderPaymentTemplateName: string | null;
          paymentDetailsText: string | null;
          officeLocation: { address: string; arrivalInstructions: string | null } | null;
          paymentTiming: "BEFORE_SESSION" | "AFTER_SESSION";
        }>(agentSettingsQueryKey(tenantId));
        if (fullSettings === undefined) {
          throw new Error("Agent settings not loaded yet");
        }
        return appContainer.api.adminUpdateAgentSettings(tenantId, {
          messageDebounceDelaySeconds: fullSettings.messageDebounceDelaySeconds,
          assistantEnabled,
          appointmentReminderEnabled: fullSettings.appointmentReminderEnabled,
          appointmentReminderDaysBefore: fullSettings.appointmentReminderDaysBefore,
          appointmentReminderAttendanceTemplateName:
            fullSettings.appointmentReminderAttendanceTemplateName,
          appointmentReminderPaymentTemplateName:
            fullSettings.appointmentReminderPaymentTemplateName,
          paymentDetailsText: fullSettings.paymentDetailsText,
          officeLocation: fullSettings.officeLocation,
          paymentTiming: fullSettings.paymentTiming
        });
      }
      const fullSettings = queryClient.getQueryData<{
        messageDebounceDelaySeconds: number;
        assistantEnabled: boolean;
        appointmentReminderEnabled: boolean;
        appointmentReminderDaysBefore: number | null;
        appointmentReminderAttendanceTemplateName: string | null;
        appointmentReminderPaymentTemplateName: string | null;
        paymentDetailsText: string | null;
        officeLocation: { address: string; arrivalInstructions: string | null } | null;
        paymentTiming: "BEFORE_SESSION" | "AFTER_SESSION";
      }>(agentSettingsQueryKey());
      if (fullSettings === undefined) {
        throw new Error("Agent settings not loaded yet");
      }
      return appContainer.agentUseCase.updateAgentSettings({
        messageDebounceDelaySeconds: fullSettings.messageDebounceDelaySeconds,
        assistantEnabled,
        appointmentReminderEnabled: fullSettings.appointmentReminderEnabled,
        appointmentReminderDaysBefore: fullSettings.appointmentReminderDaysBefore,
        appointmentReminderAttendanceTemplateName:
          fullSettings.appointmentReminderAttendanceTemplateName,
        appointmentReminderPaymentTemplateName: fullSettings.appointmentReminderPaymentTemplateName,
        paymentDetailsText: fullSettings.paymentDetailsText,
        officeLocation: fullSettings.officeLocation,
        paymentTiming: fullSettings.paymentTiming
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: agentSettingsQueryKey(tenantId) });
    }
  });
}

export function useAddBlacklistMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (whatsappUserId: string) =>
      tenantId !== undefined
        ? appContainer.api.adminAddBlacklist(tenantId, whatsappUserId)
        : appContainer.blacklistUseCase.add(whatsappUserId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: blacklistQueryKey(tenantId) });
    }
  });
}

export function useRemoveBlacklistMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (whatsappUserId: string) =>
      tenantId !== undefined
        ? appContainer.api.adminRemoveBlacklist(tenantId, whatsappUserId)
        : appContainer.blacklistUseCase.remove(whatsappUserId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: blacklistQueryKey(tenantId) });
    }
  });
}

export function useResetMessagesMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (conversationId: string) =>
      tenantId !== undefined
        ? appContainer.api.adminResetConversationMessages(tenantId, conversationId)
        : appContainer.conversationUseCase.resetMessages(conversationId),
    onSuccess: async (_data, conversationId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: conversationsQueryKey(tenantId) }),
        queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey(tenantId) }),
        queryClient.invalidateQueries({ queryKey: patientsQueryKey(tenantId) }),
        queryClient.invalidateQueries({
          queryKey:
            tenantId !== undefined
              ? ["admin", tenantId, "conversation-messages", conversationId]
              : ["conversation-messages", conversationId]
        })
      ]);
    }
  });
}

export function useSendMessageMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: ({
      conversationId,
      messageText
    }: {
      conversationId: string;
      messageText: string;
    }) =>
      tenantId !== undefined
        ? appContainer.api.adminSendConversationMessage(tenantId, conversationId, messageText)
        : appContainer.conversationUseCase.sendMessage(conversationId, messageText),
    onSuccess: async (_data, { conversationId }) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: conversationsQueryKey(tenantId) }),
        queryClient.invalidateQueries({
          queryKey:
            tenantId !== undefined
              ? ["admin", tenantId, "conversation-messages", conversationId]
              : ["conversation-messages", conversationId]
        })
      ]);
    }
  });
}

export function useSubmitSlotsMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      slots: schedulingModel.ProfessionalSlotInput[];
      professionalNote: string | null;
    }) =>
      tenantId !== undefined
        ? appContainer.api.adminSubmitProfessionalSlots(
            tenantId,
            payload.request.conversationId,
            payload.request.requestId,
            { slots: payload.slots, professionalNote: payload.professionalNote }
          )
        : appContainer.schedulingUseCase.submitProfessionalSlots(
            payload.request.conversationId,
            payload.request.requestId,
            { slots: payload.slots, professionalNote: payload.professionalNote }
          ),
    onSuccess: async (_data, _payload, _context) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey(tenantId) })
      ]);
    }
  });
}

export function useResolvePaymentMutation(
  selectedConversationId: string | null,
  tenantId?: string
) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      decision: "APPROVE" | "SEND_REMINDER";
      paymentAmountCop: number | null;
      paymentCurrency: "COP" | "USD";
      professionalNote: string | null;
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
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey(tenantId) }),
        queryClient.invalidateQueries({
          queryKey:
            tenantId !== undefined
              ? ["admin", tenantId, "conversation-messages", selectedConversationId]
              : ["conversation-messages", selectedConversationId]
        })
      ]);
    }
  });
}

export function useInboxCloseSessionMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (conversationId: string) =>
      tenantId !== undefined
        ? appContainer.api.adminCloseSession(tenantId, conversationId)
        : appContainer.schedulingUseCase.closeSession(conversationId),
    onSuccess: async (_data, conversationId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: conversationsQueryKey(tenantId) }),
        queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey(tenantId) }),
        queryClient.invalidateQueries({
          queryKey:
            tenantId !== undefined
              ? ["admin", tenantId, "conversation-messages", conversationId]
              : ["conversation-messages", conversationId]
        })
      ]);
    }
  });
}

export function useInboxAvailabilityQuery(
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
      ? ["admin", tenantId, "google-calendar-availability", params.fromIso, params.toIso]
      : ["google-calendar-availability", params.fromIso, params.toIso];
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

export function useSandboxMutation() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (enabled: boolean) => appContainer.agentUseCase.updateSandboxMode(enabled),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: devFeaturesQueryKey() });
    }
  });
}

import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as agentModel from "@domain/models/agent";

export function useSystemPromptQuery(
  tenantId?: string
): reactQueryModule.UseQueryResult<agentModel.SystemPrompt> {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: tenantId !== undefined ? ["admin", tenantId, "system-prompt"] : ["system-prompt"],
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminGetSystemPrompt(tenantId)
        : appContainer.agentUseCase.getSystemPrompt()
  });
}

export function useUpdateSystemPromptMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (systemPrompt: string) =>
      tenantId !== undefined
        ? appContainer.api.adminUpdateSystemPrompt(tenantId, systemPrompt)
        : appContainer.agentUseCase.updateSystemPrompt(systemPrompt),
    onSuccess: async () => {
      if (tenantId !== undefined) {
        await queryClient.invalidateQueries({ queryKey: ["admin", tenantId, "system-prompt"] });
      } else {
        await queryClient.invalidateQueries({ queryKey: ["system-prompt"] });
      }
    }
  });
}

export function useAgentSettingsQuery(
  tenantId?: string
): reactQueryModule.UseQueryResult<agentModel.AgentSettings> {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: tenantId !== undefined ? ["admin", tenantId, "agent-settings"] : ["agent-settings"],
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminGetAgentSettings(tenantId)
        : appContainer.agentUseCase.getAgentSettings()
  });
}

export function useUpdateAgentSettingsMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (input: agentModel.UpdateAgentSettingsInput) =>
      tenantId !== undefined
        ? appContainer.api.adminUpdateAgentSettings(tenantId, input)
        : appContainer.agentUseCase.updateAgentSettings(input),
    onSuccess: async () => {
      if (tenantId !== undefined) {
        await queryClient.invalidateQueries({ queryKey: ["admin", tenantId, "agent-settings"] });
      } else {
        await queryClient.invalidateQueries({ queryKey: ["agent-settings"] });
      }
    }
  });
}

export function useProfessionalProfileQuery(
  tenantId?: string
): reactQueryModule.UseQueryResult<agentModel.ProfessionalProfile> {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey:
      tenantId !== undefined
        ? ["admin", tenantId, "professional-profile"]
        : ["professional-profile"],
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminGetProfessionalProfile(tenantId)
        : appContainer.agentUseCase.getProfessionalProfile()
  });
}

export function useUpdateProfessionalProfileMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (input: agentModel.UpdateProfessionalProfileInput) =>
      tenantId !== undefined
        ? appContainer.api.adminUpdateProfessionalProfile(tenantId, input)
        : appContainer.agentUseCase.updateProfessionalProfile(input),
    onSuccess: async () => {
      if (tenantId !== undefined) {
        await queryClient.invalidateQueries({
          queryKey: ["admin", tenantId, "professional-profile"]
        });
      } else {
        await queryClient.invalidateQueries({ queryKey: ["professional-profile"] });
      }
    }
  });
}

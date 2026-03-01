import * as agentUseCaseModule from "@application/use_cases/agent_use_case";
import * as authUseCaseModule from "@application/use_cases/auth_use_case";
import * as blacklistUseCaseModule from "@application/use_cases/blacklist_use_case";
import * as conversationUseCaseModule from "@application/use_cases/conversation_use_case";
import * as onboardingUseCaseModule from "@application/use_cases/onboarding_use_case";
import * as schedulingUseCaseModule from "@application/use_cases/scheduling_use_case";
import * as backendApiAdapterModule from "@adapters/outbound/http/backend_api_adapter";
import * as browserTokenSessionAdapterModule from "@adapters/outbound/storage/browser_token_session_adapter";
import * as envModule from "@infrastructure/config/env";

export interface AppContainer {
  authUseCase: authUseCaseModule.AuthUseCase;
  onboardingUseCase: onboardingUseCaseModule.OnboardingUseCase;
  conversationUseCase: conversationUseCaseModule.ConversationUseCase;
  schedulingUseCase: schedulingUseCaseModule.SchedulingUseCase;
  blacklistUseCase: blacklistUseCaseModule.BlacklistUseCase;
  agentUseCase: agentUseCaseModule.AgentUseCase;
}

export function createAppContainer(): AppContainer {
  const tokenSession = new browserTokenSessionAdapterModule.BrowserTokenSessionAdapter();
  const backendApi = new backendApiAdapterModule.BackendApiAdapter(
    envModule.envConfig.apiBaseUrl,
    tokenSession
  );

  return {
    authUseCase: new authUseCaseModule.AuthUseCase(backendApi, tokenSession),
    onboardingUseCase: new onboardingUseCaseModule.OnboardingUseCase(backendApi),
    conversationUseCase: new conversationUseCaseModule.ConversationUseCase(backendApi),
    schedulingUseCase: new schedulingUseCaseModule.SchedulingUseCase(backendApi),
    blacklistUseCase: new blacklistUseCaseModule.BlacklistUseCase(backendApi),
    agentUseCase: new agentUseCaseModule.AgentUseCase(backendApi)
  };
}

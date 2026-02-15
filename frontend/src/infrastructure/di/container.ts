import * as agentUseCaseModule from "@application/use_cases/agent_use_case";
import * as authUseCaseModule from "@application/use_cases/auth_use_case";
import * as blacklistUseCaseModule from "@application/use_cases/blacklist_use_case";
import * as conversationUseCaseModule from "@application/use_cases/conversation_use_case";
import * as whatsappOnboardingUseCaseModule from "@application/use_cases/whatsapp_onboarding_use_case";
import * as backendApiAdapterModule from "@adapters/outbound/http/backend_api_adapter";
import * as browserTokenSessionAdapterModule from "@adapters/outbound/storage/browser_token_session_adapter";
import * as envModule from "@infrastructure/config/env";

export interface AppContainer {
  authUseCase: authUseCaseModule.AuthUseCase;
  onboardingUseCase: whatsappOnboardingUseCaseModule.WhatsappOnboardingUseCase;
  conversationUseCase: conversationUseCaseModule.ConversationUseCase;
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
    onboardingUseCase: new whatsappOnboardingUseCaseModule.WhatsappOnboardingUseCase(backendApi),
    conversationUseCase: new conversationUseCaseModule.ConversationUseCase(backendApi),
    blacklistUseCase: new blacklistUseCaseModule.BlacklistUseCase(backendApi),
    agentUseCase: new agentUseCaseModule.AgentUseCase(backendApi)
  };
}

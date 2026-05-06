import * as agentUseCaseModule from "@application/use_cases/agent_use_case";
import * as authUseCaseModule from "@application/use_cases/auth_use_case";
import * as blacklistUseCaseModule from "@application/use_cases/blacklist_use_case";
import * as conversationUseCaseModule from "@application/use_cases/conversation_use_case";
import * as evaluationUseCaseModule from "@application/use_cases/evaluation_use_case";
import * as manualAppointmentUseCaseModule from "@application/use_cases/manual_appointment_use_case";
import * as onboardingUseCaseModule from "@application/use_cases/onboarding_use_case";
import * as patientUseCaseModule from "@application/use_cases/patient_use_case";
import * as reminderUseCaseModule from "@application/use_cases/reminder_use_case";
import * as schedulingUseCaseModule from "@application/use_cases/scheduling_use_case";
import * as tenantUseCaseModule from "@application/use_cases/tenant_use_case";
import * as whatsappOnboardingUseCaseModule from "@application/use_cases/whatsapp_onboarding_use_case";
import * as whatsappTemplateUseCaseModule from "@application/use_cases/whatsapp_template_use_case";
import * as backendApiAdapterModule from "@adapters/outbound/http/backend_api_adapter";
import * as backendEventStreamAdapterModule from "@adapters/outbound/http/backend_event_stream_adapter";
import * as browserTokenSessionAdapterModule from "@adapters/outbound/storage/browser_token_session_adapter";
import * as envModule from "@infrastructure/config/env";
import type * as backendApiPort from "@ports/backend_api_port";
import type * as eventStreamPortModule from "@ports/event_stream_port";

export interface AppContainer {
  api: backendApiPort.BackendApiPort;
  authUseCase: authUseCaseModule.AuthUseCase;
  onboardingUseCase: onboardingUseCaseModule.OnboardingUseCase;
  whatsappOnboardingUseCase: whatsappOnboardingUseCaseModule.WhatsappOnboardingUseCase;
  conversationUseCase: conversationUseCaseModule.ConversationUseCase;
  evaluationUseCase: evaluationUseCaseModule.EvaluationUseCase;
  patientUseCase: patientUseCaseModule.PatientUseCase;
  manualAppointmentUseCase: manualAppointmentUseCaseModule.ManualAppointmentUseCase;
  schedulingUseCase: schedulingUseCaseModule.SchedulingUseCase;
  blacklistUseCase: blacklistUseCaseModule.BlacklistUseCase;
  agentUseCase: agentUseCaseModule.AgentUseCase;
  whatsappTemplateUseCase: whatsappTemplateUseCaseModule.WhatsappTemplateUseCase;
  reminderUseCase: reminderUseCaseModule.ReminderUseCase;
  tenantUseCase: tenantUseCaseModule.TenantUseCase;
  eventStream: eventStreamPortModule.EventStreamPort;
}

export function createAppContainer(): AppContainer {
  const tokenSession = new browserTokenSessionAdapterModule.BrowserTokenSessionAdapter();
  const backendApi = new backendApiAdapterModule.BackendApiAdapter(
    envModule.envConfig.apiBaseUrl,
    tokenSession
  );

  return {
    api: backendApi,
    authUseCase: new authUseCaseModule.AuthUseCase(backendApi, tokenSession),
    onboardingUseCase: new onboardingUseCaseModule.OnboardingUseCase(backendApi),
    whatsappOnboardingUseCase: new whatsappOnboardingUseCaseModule.WhatsappOnboardingUseCase(
      backendApi
    ),
    conversationUseCase: new conversationUseCaseModule.ConversationUseCase(backendApi),
    evaluationUseCase: new evaluationUseCaseModule.EvaluationUseCase(backendApi),
    patientUseCase: new patientUseCaseModule.PatientUseCase(backendApi),
    manualAppointmentUseCase: new manualAppointmentUseCaseModule.ManualAppointmentUseCase(
      backendApi
    ),
    schedulingUseCase: new schedulingUseCaseModule.SchedulingUseCase(backendApi),
    blacklistUseCase: new blacklistUseCaseModule.BlacklistUseCase(backendApi),
    agentUseCase: new agentUseCaseModule.AgentUseCase(backendApi),
    whatsappTemplateUseCase: new whatsappTemplateUseCaseModule.WhatsappTemplateUseCase(backendApi),
    reminderUseCase: new reminderUseCaseModule.ReminderUseCase(backendApi),
    tenantUseCase: new tenantUseCaseModule.TenantUseCase(backendApi),
    eventStream: new backendEventStreamAdapterModule.BackendEventStreamAdapter(
      envModule.envConfig.apiBaseUrl,
      tokenSession
    )
  };
}

import type * as agentModel from "@domain/models/agent";
import type * as authModel from "@domain/models/auth";
import type * as blacklistModel from "@domain/models/blacklist";
import type * as conversationModel from "@domain/models/conversation";
import type * as googleCalendarModel from "@domain/models/google_calendar";
import type * as onboardingModel from "@domain/models/onboarding";
import type * as patientModel from "@domain/models/patient";
import type * as schedulingModel from "@domain/models/scheduling";
import type * as whatsappModel from "@domain/models/whatsapp";

export interface BackendApiPort {
  register(input: authModel.RegisterInput): Promise<authModel.AuthTokens>;
  login(input: authModel.LoginInput): Promise<authModel.AuthTokens>;
  refresh(refreshToken: string): Promise<authModel.AuthTokens>;
  logout(refreshToken: string): Promise<void>;

  getSystemPrompt(): Promise<agentModel.SystemPrompt>;
  updateSystemPrompt(systemPrompt: string): Promise<agentModel.SystemPrompt>;

  createEmbeddedSignupSession(): Promise<whatsappModel.EmbeddedSignupSession>;
  getWhatsappConnection(): Promise<whatsappModel.WhatsappConnection>;
  createGoogleOauthSession(): Promise<googleCalendarModel.GoogleOauthSession>;
  getGoogleCalendarConnection(): Promise<googleCalendarModel.GoogleCalendarConnection>;
  getOnboardingStatus(): Promise<onboardingModel.OnboardingStatus>;
  getGoogleCalendarAvailability(
    fromIso: string,
    toIso: string
  ): Promise<googleCalendarModel.GoogleCalendarAvailability>;

  listConversations(): Promise<conversationModel.ConversationSummary[]>;
  listConversationMessages(
    conversationId: string
  ): Promise<conversationModel.ConversationMessage[]>;
  updateConversationControlMode(
    conversationId: string,
    controlMode: conversationModel.ControlMode
  ): Promise<conversationModel.ControlMode>;

  listBlacklist(): Promise<blacklistModel.BlacklistEntry[]>;
  addBlacklist(whatsappUserId: string): Promise<blacklistModel.BlacklistEntry>;
  removeBlacklist(whatsappUserId: string): Promise<void>;

  listPatients(): Promise<patientModel.Patient[]>;
  getPatient(whatsappUserId: string): Promise<patientModel.Patient>;

  listSchedulingRequests(
    status?: schedulingModel.SchedulingRequestStatus
  ): Promise<schedulingModel.SchedulingRequestSummary[]>;
  listConversationSchedulingRequests(
    conversationId: string
  ): Promise<schedulingModel.SchedulingRequestSummary[]>;
  submitProfessionalSlots(
    conversationId: string,
    requestId: string,
    input: schedulingModel.SubmitProfessionalSlotsInput
  ): Promise<schedulingModel.SubmitProfessionalSlotsResult>;
  resolveConsultationReview(
    conversationId: string,
    requestId: string,
    input: schedulingModel.ResolveConsultationReviewInput
  ): Promise<schedulingModel.ResolveConsultationReviewResult>;
}

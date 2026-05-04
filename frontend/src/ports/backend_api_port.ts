import type * as agentModel from "@domain/models/agent";
import type * as authModel from "@domain/models/auth";
import type * as blacklistModel from "@domain/models/blacklist";
import type * as conversationModel from "@domain/models/conversation";
import type * as evaluationModel from "@domain/models/evaluation";
import type * as googleCalendarModel from "@domain/models/google_calendar";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as onboardingModel from "@domain/models/onboarding";
import type * as patientModel from "@domain/models/patient";
import type * as scheduledReminderModel from "@domain/models/scheduled_reminder";
import type * as schedulingModel from "@domain/models/scheduling";
import type * as tenantModel from "@domain/models/tenant";
import type * as whatsappModel from "@domain/models/whatsapp";
import type * as whatsappTemplateModel from "@domain/models/whatsapp_template";

export interface BackendApiPort {
  login(input: authModel.LoginInput): Promise<authModel.AuthTokens>;
  refresh(refreshToken: string): Promise<authModel.AuthTokens>;
  logout(refreshToken: string): Promise<void>;

  getSystemPrompt(): Promise<agentModel.SystemPrompt>;
  updateSystemPrompt(systemPrompt: string): Promise<agentModel.SystemPrompt>;
  getAgentSettings(): Promise<agentModel.AgentSettings>;
  updateAgentSettings(
    input: agentModel.UpdateAgentSettingsInput
  ): Promise<agentModel.AgentSettings>;
  listReminders(status?: string): Promise<scheduledReminderModel.ScheduledReminderList>;
  sendReminderNow(reminderId: string): Promise<void>;

  createEmbeddedSignupSession(
    registrationPin?: string
  ): Promise<whatsappModel.EmbeddedSignupSession>;
  completeEmbeddedSignup(
    request: whatsappModel.EmbeddedSignupCompleteRequest
  ): Promise<whatsappModel.WhatsappConnection>;
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
  resetConversationMessages(conversationId: string): Promise<void>;
  sendConversationMessage(
    conversationId: string,
    messageText: string
  ): Promise<conversationModel.MessageSent>;

  listBlacklist(): Promise<blacklistModel.BlacklistEntry[]>;
  addBlacklist(whatsappUserId: string): Promise<blacklistModel.BlacklistEntry>;
  removeBlacklist(whatsappUserId: string): Promise<void>;

  listPatients(params?: { search?: string }): Promise<patientModel.Patient[]>;
  getPatient(whatsappUserId: string): Promise<patientModel.Patient>;
  createPatient(input: patientModel.CreatePatientInput): Promise<patientModel.Patient>;
  updatePatient(
    whatsappUserId: string,
    input: patientModel.UpdatePatientInput
  ): Promise<patientModel.Patient>;
  removePatient(whatsappUserId: string): Promise<void>;

  listManualAppointments(
    status?: manualAppointmentModel.ManualAppointmentStatus
  ): Promise<manualAppointmentModel.ManualAppointment[]>;
  createManualAppointment(
    input: manualAppointmentModel.CreateManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment>;
  rescheduleManualAppointment(
    appointmentId: string,
    input: manualAppointmentModel.RescheduleManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment>;
  cancelManualAppointment(
    appointmentId: string,
    input: manualAppointmentModel.CancelManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment>;
  updateManualAppointmentPayment(
    appointmentId: string,
    input: manualAppointmentModel.UpdateManualAppointmentPaymentInput
  ): Promise<manualAppointmentModel.ManualAppointment>;

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
  resolvePaymentReview(
    conversationId: string,
    requestId: string,
    input: schedulingModel.ResolvePaymentReviewInput
  ): Promise<schedulingModel.ResolvePaymentReviewResult>;
  rescheduleBookedSlot(
    requestId: string,
    input: schedulingModel.RescheduleBookedSlotInput
  ): Promise<schedulingModel.SchedulingRequestSummary>;
  cancelBookedSlot(
    requestId: string,
    input: schedulingModel.CancelBookedSlotInput
  ): Promise<schedulingModel.SchedulingRequestSummary>;
  updateBookedSlotPayment(
    requestId: string,
    input: schedulingModel.UpdateBookedSlotPaymentInput
  ): Promise<schedulingModel.SchedulingRequestSummary>;
  closeSession(conversationId: string): Promise<{ status: string }>;

  getProfessionalProfile(): Promise<agentModel.ProfessionalProfile>;
  updateProfessionalProfile(
    input: agentModel.UpdateProfessionalProfileInput
  ): Promise<agentModel.ProfessionalProfile>;

  getTenantProfile(): Promise<tenantModel.TenantProfile>;
  updateTenantProfile(
    input: tenantModel.UpdateTenantProfileInput
  ): Promise<tenantModel.TenantProfile>;

  getDevFeatures(): Promise<{ enabled: boolean; sandbox_enabled: boolean | null }>;
  updateSandboxMode(enabled: boolean): Promise<{ sandbox_enabled: boolean }>;

  listWhatsappTemplates(): Promise<whatsappTemplateModel.WhatsappTemplate[]>;
  createWhatsappTemplate(
    request: whatsappTemplateModel.CreateTemplateRequest
  ): Promise<whatsappTemplateModel.WhatsappTemplate>;
  deleteWhatsappTemplate(name: string): Promise<void>;

  listOfficialTemplateStatus(): Promise<whatsappTemplateModel.OfficialTemplateStatus[]>;
  activateOfficialTemplate(
    kind: whatsappTemplateModel.OfficialReminderKind
  ): Promise<whatsappTemplateModel.OfficialTemplateStatus>;
  deactivateOfficialTemplate(kind: whatsappTemplateModel.OfficialReminderKind): Promise<void>;

  listEvalShapes(): Promise<evaluationModel.EvalShape[]>;
  listEvalPersonas(): Promise<evaluationModel.EvalPersona[]>;
  listEvalPromptVersions(): Promise<evaluationModel.EvalPromptVersion[]>;
  listEvalRuns(limit?: number): Promise<evaluationModel.EvalRunListItem[]>;
  getEvalRun(runDocId: string): Promise<evaluationModel.EvalRunDetail>;
  deleteEvalRun(runId: string): Promise<evaluationModel.EvalDeleteResult>;
  listEvalCapabilities(): Promise<evaluationModel.EvalCapabilityDoc[]>;
}

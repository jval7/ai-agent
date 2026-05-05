import * as vitestModule from "vitest";

import type * as adminModel from "@domain/models/admin";
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
import type * as backendApiPort from "@ports/backend_api_port";
import type * as schedulingModel from "@domain/models/scheduling";
import type * as tenantModel from "@domain/models/tenant";
import type * as whatsappModel from "@domain/models/whatsapp";
import type * as whatsappTemplateModel from "@domain/models/whatsapp_template";

import * as authUseCaseModule from "./auth_use_case";

class InMemoryTokenSession {
  private accessToken: string | null;
  private refreshToken: string | null;

  constructor(accessToken: string | null, refreshToken: string | null) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  setAccessToken(token: string): void {
    this.accessToken = token;
  }

  clearAccessToken(): void {
    this.accessToken = null;
  }

  getRefreshToken(): string | null {
    return this.refreshToken;
  }

  setRefreshToken(token: string): void {
    this.refreshToken = token;
  }

  clearRefreshToken(): void {
    this.refreshToken = null;
  }

  clearAll(): void {
    this.clearAccessToken();
    this.clearRefreshToken();
  }
}

const fakeProfile: authModel.UserProfile = {
  userId: "user-1",
  email: "owner@acme.com",
  role: "professional",
  tenantId: "tenant-1"
};

class FakeBackendApi implements backendApiPort.BackendApiPort {
  refreshCalls = 0;

  async login(_input: authModel.LoginInput): Promise<authModel.AuthTokens> {
    throw new Error("not used");
  }

  async acceptInvitation(_input: authModel.AcceptInvitationInput): Promise<authModel.AuthTokens> {
    throw new Error("not used");
  }

  async requestPasswordReset(_input: authModel.RequestPasswordResetInput): Promise<void> {
    return;
  }

  async confirmPasswordReset(_input: authModel.ConfirmPasswordResetInput): Promise<void> {
    return;
  }

  async refresh(_refreshToken: string): Promise<authModel.AuthTokens> {
    this.refreshCalls += 1;
    return {
      accessToken: "access-new",
      refreshToken: "refresh-new",
      expiresInSeconds: 1800
    };
  }

  async logout(_refreshToken: string): Promise<void> {
    return;
  }

  async getMe(): Promise<authModel.UserProfile> {
    return fakeProfile;
  }

  async getSystemPrompt(): Promise<agentModel.SystemPrompt> {
    throw new Error("not used");
  }

  async updateSystemPrompt(_systemPrompt: string): Promise<agentModel.SystemPrompt> {
    throw new Error("not used");
  }

  async getAgentSettings(): Promise<agentModel.AgentSettings> {
    throw new Error("not used");
  }

  async updateAgentSettings(
    _input: agentModel.UpdateAgentSettingsInput
  ): Promise<agentModel.AgentSettings> {
    throw new Error("not used");
  }

  async getProfessionalProfile(): Promise<agentModel.ProfessionalProfile> {
    throw new Error("not used");
  }

  async updateProfessionalProfile(
    _input: agentModel.UpdateProfessionalProfileInput
  ): Promise<agentModel.ProfessionalProfile> {
    throw new Error("not used");
  }

  async getTenantProfile(): Promise<tenantModel.TenantProfile> {
    throw new Error("not used");
  }

  async updateTenantProfile(
    _input: tenantModel.UpdateTenantProfileInput
  ): Promise<tenantModel.TenantProfile> {
    throw new Error("not used");
  }

  async listReminders(_status?: string): Promise<scheduledReminderModel.ScheduledReminderList> {
    throw new Error("not used");
  }

  async sendReminderNow(_reminderId: string): Promise<void> {
    throw new Error("not used");
  }

  async createEmbeddedSignupSession(): Promise<whatsappModel.EmbeddedSignupSession> {
    throw new Error("not used");
  }

  async completeEmbeddedSignup(
    _request: whatsappModel.EmbeddedSignupCompleteRequest
  ): Promise<whatsappModel.WhatsappConnection> {
    throw new Error("not used");
  }

  async getWhatsappConnection(): Promise<whatsappModel.WhatsappConnection> {
    throw new Error("not used");
  }

  async createGoogleOauthSession(): Promise<googleCalendarModel.GoogleOauthSession> {
    throw new Error("not used");
  }

  async getGoogleCalendarConnection(): Promise<googleCalendarModel.GoogleCalendarConnection> {
    throw new Error("not used");
  }

  async getOnboardingStatus(): Promise<onboardingModel.OnboardingStatus> {
    throw new Error("not used");
  }

  async getGoogleCalendarAvailability(
    _fromIso: string,
    _toIso: string
  ): Promise<googleCalendarModel.GoogleCalendarAvailability> {
    throw new Error("not used");
  }

  async listConversations(): Promise<conversationModel.ConversationSummary[]> {
    throw new Error("not used");
  }

  async listConversationMessages(
    _conversationId: string
  ): Promise<conversationModel.ConversationMessage[]> {
    throw new Error("not used");
  }

  async updateConversationControlMode(
    _conversationId: string,
    _controlMode: "AI" | "HUMAN"
  ): Promise<conversationModel.ControlMode> {
    throw new Error("not used");
  }

  async resetConversationMessages(_conversationId: string): Promise<void> {
    return;
  }

  async sendConversationMessage(
    _conversationId: string,
    _messageText: string
  ): Promise<conversationModel.MessageSent> {
    throw new Error("not used");
  }

  async listSchedulingRequests(
    _status?: schedulingModel.SchedulingRequestStatus
  ): Promise<schedulingModel.SchedulingRequestSummary[]> {
    throw new Error("not used");
  }

  async listConversationSchedulingRequests(
    _conversationId: string
  ): Promise<schedulingModel.SchedulingRequestSummary[]> {
    throw new Error("not used");
  }

  async submitProfessionalSlots(
    _conversationId: string,
    _requestId: string,
    _input: schedulingModel.SubmitProfessionalSlotsInput
  ): Promise<schedulingModel.SubmitProfessionalSlotsResult> {
    throw new Error("not used");
  }

  async resolveConsultationReview(
    _conversationId: string,
    _requestId: string,
    _input: schedulingModel.ResolveConsultationReviewInput
  ): Promise<schedulingModel.ResolveConsultationReviewResult> {
    throw new Error("not used");
  }

  async resolvePaymentReview(
    _conversationId: string,
    _requestId: string,
    _input: schedulingModel.ResolvePaymentReviewInput
  ): Promise<schedulingModel.ResolvePaymentReviewResult> {
    throw new Error("not used");
  }

  async listBlacklist(): Promise<blacklistModel.BlacklistEntry[]> {
    throw new Error("not used");
  }

  async addBlacklist(_whatsappUserId: string): Promise<blacklistModel.BlacklistEntry> {
    throw new Error("not used");
  }

  async removeBlacklist(_whatsappUserId: string): Promise<void> {
    return;
  }

  async listPatients(): Promise<patientModel.Patient[]> {
    throw new Error("not used");
  }

  async getPatient(_whatsappUserId: string): Promise<patientModel.Patient> {
    throw new Error("not used");
  }

  async createPatient(_input: patientModel.CreatePatientInput): Promise<patientModel.Patient> {
    throw new Error("not used");
  }

  async updatePatient(
    _whatsappUserId: string,
    _input: patientModel.UpdatePatientInput
  ): Promise<patientModel.Patient> {
    throw new Error("not used");
  }

  async removePatient(_whatsappUserId: string): Promise<void> {
    return;
  }

  async listManualAppointments(
    _status?: manualAppointmentModel.ManualAppointmentStatus
  ): Promise<manualAppointmentModel.ManualAppointment[]> {
    throw new Error("not used");
  }

  async createManualAppointment(
    _input: manualAppointmentModel.CreateManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    throw new Error("not used");
  }

  async rescheduleManualAppointment(
    _appointmentId: string,
    _input: manualAppointmentModel.RescheduleManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    throw new Error("not used");
  }

  async cancelManualAppointment(
    _appointmentId: string,
    _input: manualAppointmentModel.CancelManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    throw new Error("not used");
  }

  async updateManualAppointmentPayment(
    _appointmentId: string,
    _input: manualAppointmentModel.UpdateManualAppointmentPaymentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    throw new Error("not used");
  }

  async rescheduleBookedSlot(
    _requestId: string,
    _input: schedulingModel.RescheduleBookedSlotInput
  ): Promise<schedulingModel.SchedulingRequestSummary> {
    throw new Error("not used");
  }

  async cancelBookedSlot(
    _requestId: string,
    _input: schedulingModel.CancelBookedSlotInput
  ): Promise<schedulingModel.SchedulingRequestSummary> {
    throw new Error("not used");
  }

  async updateBookedSlotPayment(
    _requestId: string,
    _input: schedulingModel.UpdateBookedSlotPaymentInput
  ): Promise<schedulingModel.SchedulingRequestSummary> {
    throw new Error("not used");
  }

  async changeBookedSlotModality(
    _requestId: string,
    _input: schedulingModel.ChangeBookedSlotModalityInput
  ): Promise<schedulingModel.SchedulingRequestSummary> {
    throw new Error("not used");
  }

  async changeManualAppointmentModality(
    _appointmentId: string,
    _input: manualAppointmentModel.ChangeManualAppointmentModalityInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    throw new Error("not used");
  }

  async closeSession(_conversationId: string): Promise<{ status: string }> {
    throw new Error("not used");
  }

  async getDevFeatures(): Promise<{ enabled: boolean; sandbox_enabled: boolean | null }> {
    throw new Error("not used");
  }

  async updateSandboxMode(_enabled: boolean): Promise<{ sandbox_enabled: boolean }> {
    throw new Error("not used");
  }

  async listWhatsappTemplates(): Promise<whatsappTemplateModel.WhatsappTemplate[]> {
    throw new Error("not used");
  }

  async createWhatsappTemplate(
    _request: whatsappTemplateModel.CreateTemplateRequest
  ): Promise<whatsappTemplateModel.WhatsappTemplate> {
    throw new Error("not used");
  }

  async deleteWhatsappTemplate(_name: string): Promise<void> {
    return;
  }

  async listOfficialTemplateStatus(): Promise<whatsappTemplateModel.OfficialTemplateStatus[]> {
    throw new Error("not used");
  }

  async activateOfficialTemplate(
    _kind: whatsappTemplateModel.OfficialReminderKind
  ): Promise<whatsappTemplateModel.OfficialTemplateStatus> {
    throw new Error("not used");
  }

  async deactivateOfficialTemplate(
    _kind: whatsappTemplateModel.OfficialReminderKind
  ): Promise<void> {
    return;
  }

  async listEvalShapes(): Promise<evaluationModel.EvalShape[]> {
    throw new Error("not used");
  }

  async listEvalPersonas(): Promise<evaluationModel.EvalPersona[]> {
    throw new Error("not used");
  }

  async listEvalPromptVersions(): Promise<evaluationModel.EvalPromptVersion[]> {
    throw new Error("not used");
  }

  async listEvalRuns(_limit?: number): Promise<evaluationModel.EvalRunListItem[]> {
    throw new Error("not used");
  }

  async getEvalRun(_runDocId: string): Promise<evaluationModel.EvalRunDetail> {
    throw new Error("not used");
  }

  async deleteEvalRun(_runId: string): Promise<evaluationModel.EvalDeleteResult> {
    throw new Error("not used");
  }

  async listEvalCapabilities(): Promise<evaluationModel.EvalCapabilityDoc[]> {
    throw new Error("not used");
  }

  async adminGetGlobalMetrics(): Promise<adminModel.GlobalMetrics> {
    throw new Error("not used");
  }

  async adminListTenants(_search?: string): Promise<adminModel.TenantSummary[]> {
    throw new Error("not used");
  }

  async adminGetTenantSummary(_tenantId: string): Promise<adminModel.TenantSummary> {
    throw new Error("not used");
  }

  async adminListPatients(_tenantId: string): Promise<patientModel.Patient[]> {
    throw new Error("not used");
  }

  async adminGetPatient(_tenantId: string, _whatsappUserId: string): Promise<patientModel.Patient> {
    throw new Error("not used");
  }

  async adminCreatePatient(
    _tenantId: string,
    _input: patientModel.CreatePatientInput
  ): Promise<patientModel.Patient> {
    throw new Error("not used");
  }

  async adminUpdatePatient(
    _tenantId: string,
    _whatsappUserId: string,
    _input: patientModel.UpdatePatientInput
  ): Promise<patientModel.Patient> {
    throw new Error("not used");
  }

  async adminRemovePatient(_tenantId: string, _whatsappUserId: string): Promise<void> {
    return;
  }

  async adminListConversations(
    _tenantId: string
  ): Promise<conversationModel.ConversationSummary[]> {
    throw new Error("not used");
  }

  async adminListConversationMessages(
    _tenantId: string,
    _conversationId: string
  ): Promise<conversationModel.ConversationMessage[]> {
    throw new Error("not used");
  }

  async adminUpdateConversationControlMode(
    _tenantId: string,
    _conversationId: string,
    _controlMode: conversationModel.ControlMode
  ): Promise<conversationModel.ControlMode> {
    throw new Error("not used");
  }

  async adminSendConversationMessage(
    _tenantId: string,
    _conversationId: string,
    _messageText: string
  ): Promise<conversationModel.MessageSent> {
    throw new Error("not used");
  }

  async adminListManualAppointments(
    _tenantId: string,
    _status?: manualAppointmentModel.ManualAppointmentStatus
  ): Promise<manualAppointmentModel.ManualAppointment[]> {
    throw new Error("not used");
  }

  async adminCreateManualAppointment(
    _tenantId: string,
    _input: manualAppointmentModel.CreateManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    throw new Error("not used");
  }

  async adminRescheduleManualAppointment(
    _tenantId: string,
    _appointmentId: string,
    _input: manualAppointmentModel.RescheduleManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    throw new Error("not used");
  }

  async adminCancelManualAppointment(
    _tenantId: string,
    _appointmentId: string,
    _input: manualAppointmentModel.CancelManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    throw new Error("not used");
  }

  async adminUpdateManualAppointmentPayment(
    _tenantId: string,
    _appointmentId: string,
    _input: manualAppointmentModel.UpdateManualAppointmentPaymentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    throw new Error("not used");
  }

  async adminChangeManualAppointmentModality(
    _tenantId: string,
    _appointmentId: string,
    _input: manualAppointmentModel.ChangeManualAppointmentModalityInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    throw new Error("not used");
  }

  async adminListSchedulingRequests(
    _tenantId: string,
    _status?: schedulingModel.SchedulingRequestStatus
  ): Promise<schedulingModel.SchedulingRequestSummary[]> {
    throw new Error("not used");
  }

  async adminListReminders(
    _tenantId: string,
    _status?: string
  ): Promise<scheduledReminderModel.ScheduledReminderList> {
    throw new Error("not used");
  }

  async adminSendReminderNow(_tenantId: string, _reminderId: string): Promise<void> {
    return;
  }

  async adminListBlacklist(_tenantId: string): Promise<blacklistModel.BlacklistEntry[]> {
    throw new Error("not used");
  }

  async adminAddBlacklist(
    _tenantId: string,
    _whatsappUserId: string
  ): Promise<blacklistModel.BlacklistEntry> {
    throw new Error("not used");
  }

  async adminRemoveBlacklist(_tenantId: string, _whatsappUserId: string): Promise<void> {
    return;
  }

  async adminGetSystemPrompt(_tenantId: string): Promise<agentModel.SystemPrompt> {
    throw new Error("not used");
  }

  async adminUpdateSystemPrompt(
    _tenantId: string,
    _systemPrompt: string
  ): Promise<agentModel.SystemPrompt> {
    throw new Error("not used");
  }

  async adminGetAgentSettings(_tenantId: string): Promise<agentModel.AgentSettings> {
    throw new Error("not used");
  }

  async adminUpdateAgentSettings(
    _tenantId: string,
    _input: agentModel.UpdateAgentSettingsInput
  ): Promise<agentModel.AgentSettings> {
    throw new Error("not used");
  }

  async adminGetProfessionalProfile(_tenantId: string): Promise<agentModel.ProfessionalProfile> {
    throw new Error("not used");
  }

  async adminUpdateProfessionalProfile(
    _tenantId: string,
    _input: agentModel.UpdateProfessionalProfileInput
  ): Promise<agentModel.ProfessionalProfile> {
    throw new Error("not used");
  }
}

vitestModule.describe("AuthUseCase", () => {
  vitestModule.it("bootstraps session from refresh token and returns user profile", async () => {
    const api = new FakeBackendApi();
    const tokenSession = new InMemoryTokenSession(null, "refresh-old");
    const authUseCase = new authUseCaseModule.AuthUseCase(api, tokenSession);

    const profile = await authUseCase.bootstrapSession();

    vitestModule.expect(profile).not.toBeNull();
    vitestModule.expect(profile?.userId).toBe("user-1");
    vitestModule.expect(profile?.role).toBe("professional");
    vitestModule.expect(api.refreshCalls).toBe(1);
    vitestModule.expect(tokenSession.getAccessToken()).toBe("access-new");
    vitestModule.expect(tokenSession.getRefreshToken()).toBe("refresh-new");
  });

  vitestModule.it("returns null when no tokens present", async () => {
    const api = new FakeBackendApi();
    const tokenSession = new InMemoryTokenSession(null, null);
    const authUseCase = new authUseCaseModule.AuthUseCase(api, tokenSession);

    const profile = await authUseCase.bootstrapSession();

    vitestModule.expect(profile).toBeNull();
    vitestModule.expect(api.refreshCalls).toBe(0);
  });
});

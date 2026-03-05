import * as vitestModule from "vitest";

import type * as agentModel from "@domain/models/agent";
import type * as authModel from "@domain/models/auth";
import type * as blacklistModel from "@domain/models/blacklist";
import type * as conversationModel from "@domain/models/conversation";
import type * as googleCalendarModel from "@domain/models/google_calendar";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as onboardingModel from "@domain/models/onboarding";
import type * as patientModel from "@domain/models/patient";
import type * as backendApiPort from "@ports/backend_api_port";
import type * as schedulingModel from "@domain/models/scheduling";
import type * as whatsappModel from "@domain/models/whatsapp";

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

class FakeBackendApi implements backendApiPort.BackendApiPort {
  refreshCalls = 0;

  async login(_input: authModel.LoginInput): Promise<authModel.AuthTokens> {
    throw new Error("not used");
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

  async getSystemPrompt(): Promise<agentModel.SystemPrompt> {
    throw new Error("not used");
  }

  async updateSystemPrompt(_systemPrompt: string): Promise<agentModel.SystemPrompt> {
    throw new Error("not used");
  }

  async createEmbeddedSignupSession(): Promise<whatsappModel.EmbeddedSignupSession> {
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
}

vitestModule.describe("AuthUseCase", () => {
  vitestModule.it("bootstraps session from refresh token", async () => {
    const api = new FakeBackendApi();
    const tokenSession = new InMemoryTokenSession(null, "refresh-old");
    const authUseCase = new authUseCaseModule.AuthUseCase(api, tokenSession);

    const hasSession = await authUseCase.bootstrapSession();

    vitestModule.expect(hasSession).toBe(true);
    vitestModule.expect(api.refreshCalls).toBe(1);
    vitestModule.expect(tokenSession.getAccessToken()).toBe("access-new");
    vitestModule.expect(tokenSession.getRefreshToken()).toBe("refresh-new");
  });
});

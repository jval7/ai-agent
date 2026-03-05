import type * as agentModel from "@domain/models/agent";
import type * as authModel from "@domain/models/auth";
import type * as blacklistModel from "@domain/models/blacklist";
import type * as conversationModel from "@domain/models/conversation";
import type * as googleCalendarModel from "@domain/models/google_calendar";
import type * as onboardingModel from "@domain/models/onboarding";
import type * as patientModel from "@domain/models/patient";
import type * as schedulingModel from "@domain/models/scheduling";
import type * as whatsappModel from "@domain/models/whatsapp";
import type * as backendApiPort from "@ports/backend_api_port";
import type * as tokenSessionPort from "@ports/token_session_port";
import * as apiErrorModule from "@shared/http/api_error";
import * as requestIdModule from "@shared/http/request_id";

import type * as httpTypes from "./http_types";

interface RequestOptions {
  method: "GET" | "POST" | "PUT" | "DELETE";
  authRequired: boolean;
  body?: string;
  retryOnUnauthorized?: boolean;
  requestId?: string;
}

export class BackendApiAdapter implements backendApiPort.BackendApiPort {
  private readonly baseUrl: string;
  private readonly tokenSession: tokenSessionPort.TokenSessionPort;
  private refreshInFlight: Promise<string | null> | null;

  constructor(baseUrl: string, tokenSession: tokenSessionPort.TokenSessionPort) {
    this.baseUrl = baseUrl;
    this.tokenSession = tokenSession;
    this.refreshInFlight = null;
  }

  async login(input: authModel.LoginInput): Promise<authModel.AuthTokens> {
    const payload = await this.request<httpTypes.AuthTokensApiResponse>("/v1/auth/login", {
      method: "POST",
      authRequired: false,
      body: JSON.stringify({
        email: input.email,
        password: input.password
      })
    });
    return mapAuthTokens(payload);
  }

  async refresh(refreshToken: string): Promise<authModel.AuthTokens> {
    const payload = await this.refreshTokens(refreshToken);
    return mapAuthTokens(payload);
  }

  async logout(refreshToken: string): Promise<void> {
    await this.request<void>("/v1/auth/logout", {
      method: "POST",
      authRequired: true,
      body: JSON.stringify({
        refresh_token: refreshToken
      })
    });
  }

  async getSystemPrompt(): Promise<agentModel.SystemPrompt> {
    const payload = await this.request<httpTypes.SystemPromptApiResponse>(
      "/v1/agent/system-prompt",
      {
        method: "GET",
        authRequired: true
      }
    );
    return {
      tenantId: payload.tenant_id,
      systemPrompt: payload.system_prompt
    };
  }

  async updateSystemPrompt(systemPrompt: string): Promise<agentModel.SystemPrompt> {
    const payload = await this.request<httpTypes.SystemPromptApiResponse>(
      "/v1/agent/system-prompt",
      {
        method: "PUT",
        authRequired: true,
        body: JSON.stringify({
          system_prompt: systemPrompt
        })
      }
    );
    return {
      tenantId: payload.tenant_id,
      systemPrompt: payload.system_prompt
    };
  }

  async createEmbeddedSignupSession(): Promise<whatsappModel.EmbeddedSignupSession> {
    const payload = await this.request<httpTypes.EmbeddedSignupSessionApiResponse>(
      "/v1/whatsapp/embedded-signup/session",
      {
        method: "POST",
        authRequired: true
      }
    );

    return {
      state: payload.state,
      connectUrl: payload.connect_url
    };
  }

  async getWhatsappConnection(): Promise<whatsappModel.WhatsappConnection> {
    const payload = await this.request<httpTypes.WhatsappConnectionApiResponse>(
      "/v1/whatsapp/connection",
      {
        method: "GET",
        authRequired: true
      }
    );

    return {
      tenantId: payload.tenant_id,
      status: payload.status,
      phoneNumberId: payload.phone_number_id,
      businessAccountId: payload.business_account_id
    };
  }

  async createGoogleOauthSession(): Promise<googleCalendarModel.GoogleOauthSession> {
    const payload = await this.request<httpTypes.GoogleOauthSessionApiResponse>(
      "/v1/google-calendar/oauth/session",
      {
        method: "POST",
        authRequired: true
      }
    );

    return {
      state: payload.state,
      connectUrl: payload.connect_url
    };
  }

  async getGoogleCalendarConnection(): Promise<googleCalendarModel.GoogleCalendarConnection> {
    const payload = await this.request<httpTypes.GoogleCalendarConnectionApiResponse>(
      "/v1/google-calendar/connection",
      {
        method: "GET",
        authRequired: true
      }
    );

    return {
      tenantId: payload.tenant_id,
      status: payload.status,
      calendarId: payload.calendar_id,
      professionalTimezone: payload.professional_timezone,
      connectedAt: payload.connected_at
    };
  }

  async getOnboardingStatus(): Promise<onboardingModel.OnboardingStatus> {
    const payload = await this.request<httpTypes.OnboardingStatusApiResponse>(
      "/v1/onboarding/status",
      {
        method: "GET",
        authRequired: true
      }
    );

    return {
      whatsappConnected: payload.whatsapp_connected,
      googleCalendarConnected: payload.google_calendar_connected,
      ready: payload.ready
    };
  }

  async getGoogleCalendarAvailability(
    fromIso: string,
    toIso: string
  ): Promise<googleCalendarModel.GoogleCalendarAvailability> {
    const queryParams = new URLSearchParams({
      from: fromIso,
      to: toIso
    });
    const payload = await this.request<httpTypes.GoogleCalendarAvailabilityApiResponse>(
      `/v1/google-calendar/availability?${queryParams.toString()}`,
      {
        method: "GET",
        authRequired: true
      }
    );

    return {
      tenantId: payload.tenant_id,
      calendarId: payload.calendar_id,
      timezone: payload.timezone,
      busyIntervals: payload.busy_intervals.map((interval) => ({
        startAt: interval.start_at,
        endAt: interval.end_at
      }))
    };
  }

  async listConversations(): Promise<conversationModel.ConversationSummary[]> {
    const payload = await this.request<httpTypes.ConversationListApiResponse>("/v1/conversations", {
      method: "GET",
      authRequired: true
    });

    return payload.items.map((item) => ({
      conversationId: item.conversation_id,
      whatsappUserId: item.whatsapp_user_id,
      lastMessagePreview: item.last_message_preview,
      updatedAt: item.updated_at,
      controlMode: item.control_mode
    }));
  }

  async listConversationMessages(
    conversationId: string
  ): Promise<conversationModel.ConversationMessage[]> {
    const payload = await this.request<httpTypes.MessageListApiResponse>(
      `/v1/conversations/${conversationId}/messages`,
      {
        method: "GET",
        authRequired: true
      }
    );

    return payload.items.map((item) => ({
      messageId: item.message_id,
      conversationId: item.conversation_id,
      role: item.role,
      direction: item.direction,
      content: item.content,
      createdAt: item.created_at
    }));
  }

  async updateConversationControlMode(
    conversationId: string,
    controlMode: conversationModel.ControlMode
  ): Promise<conversationModel.ControlMode> {
    const payload = await this.request<httpTypes.ConversationControlModeApiResponse>(
      `/v1/conversations/${conversationId}/control-mode`,
      {
        method: "PUT",
        authRequired: true,
        body: JSON.stringify({
          control_mode: controlMode
        })
      }
    );

    return payload.control_mode;
  }

  async resetConversationMessages(conversationId: string): Promise<void> {
    await this.request<void>(`/v1/conversations/${conversationId}/messages`, {
      method: "DELETE",
      authRequired: true
    });
  }

  async listBlacklist(): Promise<blacklistModel.BlacklistEntry[]> {
    const payload = await this.request<httpTypes.BlacklistListApiResponse>("/v1/blacklist", {
      method: "GET",
      authRequired: true
    });

    return payload.items.map((item) => ({
      tenantId: item.tenant_id,
      whatsappUserId: item.whatsapp_user_id,
      createdAt: item.created_at
    }));
  }

  async addBlacklist(whatsappUserId: string): Promise<blacklistModel.BlacklistEntry> {
    const payload = await this.request<httpTypes.BlacklistEntryApiResponse>("/v1/blacklist", {
      method: "POST",
      authRequired: true,
      body: JSON.stringify({
        whatsapp_user_id: whatsappUserId
      })
    });

    return {
      tenantId: payload.tenant_id,
      whatsappUserId: payload.whatsapp_user_id,
      createdAt: payload.created_at
    };
  }

  async removeBlacklist(whatsappUserId: string): Promise<void> {
    await this.request<void>(`/v1/blacklist/${whatsappUserId}`, {
      method: "DELETE",
      authRequired: true
    });
  }

  async listPatients(): Promise<patientModel.Patient[]> {
    const payload = await this.request<httpTypes.PatientListApiResponse>("/v1/patients", {
      method: "GET",
      authRequired: true
    });
    return payload.items.map(mapPatient);
  }

  async getPatient(whatsappUserId: string): Promise<patientModel.Patient> {
    const payload = await this.request<httpTypes.PatientApiResponse>(
      `/v1/patients/${whatsappUserId}`,
      {
        method: "GET",
        authRequired: true
      }
    );
    return mapPatient(payload);
  }

  async removePatient(whatsappUserId: string): Promise<void> {
    await this.request<void>(`/v1/patients/${whatsappUserId}`, {
      method: "DELETE",
      authRequired: true
    });
  }

  async listSchedulingRequests(
    status?: schedulingModel.SchedulingRequestStatus
  ): Promise<schedulingModel.SchedulingRequestSummary[]> {
    const queryParams = new URLSearchParams();
    if (status !== undefined) {
      queryParams.set("status", status);
    }
    const queryString = queryParams.toString();
    const path =
      queryString.length > 0 ? `/v1/scheduling-requests?${queryString}` : "/v1/scheduling-requests";
    const payload = await this.request<httpTypes.SchedulingRequestListApiResponse>(path, {
      method: "GET",
      authRequired: true
    });

    return payload.items.map(mapSchedulingRequestSummary);
  }

  async listConversationSchedulingRequests(
    conversationId: string
  ): Promise<schedulingModel.SchedulingRequestSummary[]> {
    const payload = await this.request<httpTypes.SchedulingRequestListApiResponse>(
      `/v1/conversations/${conversationId}/scheduling/requests`,
      {
        method: "GET",
        authRequired: true
      }
    );

    return payload.items.map(mapSchedulingRequestSummary);
  }

  async submitProfessionalSlots(
    conversationId: string,
    requestId: string,
    input: schedulingModel.SubmitProfessionalSlotsInput
  ): Promise<schedulingModel.SubmitProfessionalSlotsResult> {
    const payload = await this.request<httpTypes.SubmitProfessionalSlotsApiResponse>(
      `/v1/conversations/${conversationId}/scheduling/requests/${requestId}/professional-slots`,
      {
        method: "POST",
        authRequired: true,
        body: JSON.stringify({
          slots: input.slots.map((slot) => ({
            slot_id: slot.slotId,
            start_at: slot.startAt,
            end_at: slot.endAt,
            timezone: slot.timezone
          })),
          professional_note: input.professionalNote
        } satisfies httpTypes.SubmitProfessionalSlotsApiRequest)
      }
    );

    return {
      status: payload.status,
      slotBatchId: payload.slot_batch_id,
      outboundMessageId: payload.outbound_message_id,
      assistantText: payload.assistant_text
    };
  }

  async resolveConsultationReview(
    conversationId: string,
    requestId: string,
    input: schedulingModel.ResolveConsultationReviewInput
  ): Promise<schedulingModel.ResolveConsultationReviewResult> {
    const payload = await this.request<httpTypes.ResolveConsultationReviewApiResponse>(
      `/v1/conversations/${conversationId}/scheduling/requests/${requestId}/consultation-review`,
      {
        method: "POST",
        authRequired: true,
        body: JSON.stringify({
          decision: input.decision,
          professional_note: input.professionalNote
        } satisfies httpTypes.ResolveConsultationReviewApiRequest)
      }
    );

    return {
      status: payload.status,
      outboundMessageId: payload.outbound_message_id,
      assistantText: payload.assistant_text
    };
  }

  private async request<T>(path: string, options: RequestOptions): Promise<T> {
    const retryOnUnauthorized = options.retryOnUnauthorized ?? true;
    const requestId = options.requestId ?? requestIdModule.createRequestId();

    const headers = new Headers();
    headers.set("Content-Type", "application/json");
    headers.set("X-Request-ID", requestId);

    if (options.authRequired) {
      const accessToken = this.tokenSession.getAccessToken();
      if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }
    }

    const requestInit: RequestInit = {
      method: options.method,
      headers
    };
    if (options.body !== undefined) {
      requestInit.body = options.body;
    }

    const response = await fetch(`${this.baseUrl}${path}`, requestInit);

    if (response.status === 401 && options.authRequired && retryOnUnauthorized) {
      const refreshedToken = await this.refreshAccessTokenWithLock();
      if (refreshedToken === null) {
        throw new apiErrorModule.ApiError(401, "token expired", requestId);
      }

      return this.request<T>(path, {
        ...options,
        retryOnUnauthorized: false,
        requestId
      });
    }

    if (!response.ok) {
      throw await this.parseError(response, requestId);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const payload = (await response.json()) as T;
    return payload;
  }

  private async refreshAccessTokenWithLock(): Promise<string | null> {
    if (this.refreshInFlight !== null) {
      return this.refreshInFlight;
    }

    const refreshToken = this.tokenSession.getRefreshToken();
    if (refreshToken === null) {
      return null;
    }

    this.refreshInFlight = this.performRefresh(refreshToken);

    try {
      return await this.refreshInFlight;
    } finally {
      this.refreshInFlight = null;
    }
  }

  private async performRefresh(refreshToken: string): Promise<string | null> {
    try {
      const payload = await this.refreshTokens(refreshToken);
      const tokens = mapAuthTokens(payload);
      this.tokenSession.setAccessToken(tokens.accessToken);
      this.tokenSession.setRefreshToken(tokens.refreshToken);
      return tokens.accessToken;
    } catch (error: unknown) {
      if (!(error instanceof apiErrorModule.ApiError) && !(error instanceof TypeError)) {
        throw error;
      }
      this.tokenSession.clearAll();
      return null;
    }
  }

  private async refreshTokens(refreshToken: string): Promise<httpTypes.AuthTokensApiResponse> {
    const requestId = requestIdModule.createRequestId();
    const response = await fetch(`${this.baseUrl}/v1/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Request-ID": requestId
      },
      body: JSON.stringify({
        refresh_token: refreshToken
      })
    });

    if (!response.ok) {
      throw await this.parseError(response, requestId);
    }

    const payload = (await response.json()) as httpTypes.AuthTokensApiResponse;
    return payload;
  }

  private async parseError(
    response: Response,
    fallbackRequestId: string
  ): Promise<apiErrorModule.ApiError> {
    const fallbackMessage = `request failed with status ${response.status}`;
    const requestIdFromHeader = response.headers.get("X-Request-ID");
    const resolvedRequestId = normalizeRequestId(requestIdFromHeader) ?? fallbackRequestId;
    const contentType = response.headers.get("content-type") ?? "";

    if (!contentType.includes("application/json")) {
      return new apiErrorModule.ApiError(response.status, fallbackMessage, resolvedRequestId);
    }

    let payload: Partial<httpTypes.ApiErrorResponse>;
    try {
      payload = (await response.json()) as Partial<httpTypes.ApiErrorResponse>;
    } catch (error: unknown) {
      if (error instanceof SyntaxError) {
        return new apiErrorModule.ApiError(response.status, fallbackMessage, resolvedRequestId);
      }
      throw error;
    }

    const requestIdFromBody =
      typeof payload.request_id === "string" ? normalizeRequestId(payload.request_id) : null;
    const finalRequestId = requestIdFromBody ?? resolvedRequestId;

    if (typeof payload.detail !== "string" || payload.detail.trim() === "") {
      return new apiErrorModule.ApiError(response.status, fallbackMessage, finalRequestId);
    }

    return new apiErrorModule.ApiError(response.status, payload.detail, finalRequestId);
  }
}

function normalizeRequestId(rawRequestId: string | null): string | null {
  if (rawRequestId === null) {
    return null;
  }
  const normalizedRequestId = rawRequestId.trim();
  if (normalizedRequestId === "") {
    return null;
  }
  return normalizedRequestId;
}

function mapAuthTokens(payload: httpTypes.AuthTokensApiResponse): authModel.AuthTokens {
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    expiresInSeconds: payload.expires_in_seconds
  };
}

function mapPatient(payload: httpTypes.PatientApiResponse): patientModel.Patient {
  return {
    tenantId: payload.tenant_id,
    whatsappUserId: payload.whatsapp_user_id,
    firstName: payload.first_name,
    lastName: payload.last_name,
    email: payload.email,
    age: payload.age,
    consultationReason: payload.consultation_reason,
    location: payload.location,
    phone: payload.phone,
    createdAt: payload.created_at
  };
}

function mapSchedulingRequestSummary(
  payload: httpTypes.SchedulingRequestSummaryApiResponse
): schedulingModel.SchedulingRequestSummary {
  return {
    requestId: payload.request_id,
    conversationId: payload.conversation_id,
    whatsappUserId: payload.whatsapp_user_id,
    requestKind: payload.request_kind,
    status: payload.status,
    roundNumber: payload.round_number,
    patientPreferenceNote: payload.patient_preference_note,
    rejectionSummary: payload.rejection_summary,
    professionalNote: payload.professional_note,
    patientFirstName: payload.patient_first_name,
    patientLastName: payload.patient_last_name,
    patientAge: payload.patient_age,
    consultationReason: payload.consultation_reason,
    consultationDetails: payload.consultation_details,
    appointmentModality: payload.appointment_modality,
    patientLocation: payload.patient_location,
    slotOptionsMap: payload.slot_options_map,
    selectedSlotId: payload.selected_slot_id,
    calendarEventId: payload.calendar_event_id,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
    slots: payload.slots.map((slot) => ({
      slotId: slot.slot_id,
      startAt: slot.start_at,
      endAt: slot.end_at,
      timezone: slot.timezone,
      status: slot.status
    }))
  };
}

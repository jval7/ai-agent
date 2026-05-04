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
  customHeaders?: Record<string, string>;
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

  async acceptInvitation(input: authModel.AcceptInvitationInput): Promise<authModel.AuthTokens> {
    const payload = await this.request<httpTypes.AuthTokensApiResponse>("/v1/auth/accept-invite", {
      method: "POST",
      authRequired: false,
      body: JSON.stringify({
        token: input.token,
        new_password: input.password
      })
    });
    return mapAuthTokens(payload);
  }

  async requestPasswordReset(input: authModel.RequestPasswordResetInput): Promise<void> {
    await this.request<void>("/v1/auth/password-reset/request", {
      method: "POST",
      authRequired: false,
      body: JSON.stringify({
        email: input.email
      })
    });
  }

  async confirmPasswordReset(input: authModel.ConfirmPasswordResetInput): Promise<void> {
    await this.request<void>("/v1/auth/password-reset/confirm", {
      method: "POST",
      authRequired: false,
      body: JSON.stringify({
        token: input.token,
        new_password: input.password
      })
    });
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

  async getAgentSettings(): Promise<agentModel.AgentSettings> {
    const raw = await this.request<{
      tenant_id: string;
      message_debounce_delay_seconds: number;
      assistant_enabled: boolean | null | undefined;
      appointment_reminder_enabled: boolean;
      appointment_reminder_days_before: number | null;
      appointment_reminder_attendance_template_name: string | null;
      appointment_reminder_payment_template_name: string | null;
      payment_details_text: string | null;
      office_location: {
        address: string;
        arrival_instructions: string | null;
      } | null;
      payment_timing: agentModel.PaymentTiming | null | undefined;
    }>("/v1/agent/settings", { method: "GET", authRequired: true });
    return {
      tenantId: raw.tenant_id,
      messageDebounceDelaySeconds: raw.message_debounce_delay_seconds,
      assistantEnabled: raw.assistant_enabled ?? true,
      appointmentReminderEnabled: raw.appointment_reminder_enabled,
      appointmentReminderDaysBefore: raw.appointment_reminder_days_before,
      appointmentReminderAttendanceTemplateName: raw.appointment_reminder_attendance_template_name,
      appointmentReminderPaymentTemplateName: raw.appointment_reminder_payment_template_name,
      paymentDetailsText: raw.payment_details_text,
      officeLocation:
        raw.office_location !== null && raw.office_location !== undefined
          ? {
              address: raw.office_location.address,
              arrivalInstructions: raw.office_location.arrival_instructions
            }
          : null,
      paymentTiming: raw.payment_timing ?? "BEFORE_SESSION"
    };
  }

  async updateAgentSettings(
    input: agentModel.UpdateAgentSettingsInput
  ): Promise<agentModel.AgentSettings> {
    const raw = await this.request<{
      tenant_id: string;
      message_debounce_delay_seconds: number;
      assistant_enabled: boolean | null | undefined;
      appointment_reminder_enabled: boolean;
      appointment_reminder_days_before: number | null;
      appointment_reminder_attendance_template_name: string | null;
      appointment_reminder_payment_template_name: string | null;
      payment_details_text: string | null;
      office_location: {
        address: string;
        arrival_instructions: string | null;
      } | null;
      payment_timing: agentModel.PaymentTiming | null | undefined;
    }>("/v1/agent/settings", {
      method: "PUT",
      authRequired: true,
      body: JSON.stringify({
        message_debounce_delay_seconds: input.messageDebounceDelaySeconds,
        assistant_enabled: input.assistantEnabled,
        appointment_reminder_enabled: input.appointmentReminderEnabled,
        appointment_reminder_days_before: input.appointmentReminderDaysBefore,
        appointment_reminder_attendance_template_name:
          input.appointmentReminderAttendanceTemplateName,
        appointment_reminder_payment_template_name: input.appointmentReminderPaymentTemplateName,
        payment_details_text: input.paymentDetailsText,
        office_location:
          input.officeLocation !== null
            ? {
                address: input.officeLocation.address,
                arrival_instructions: input.officeLocation.arrivalInstructions
              }
            : null,
        payment_timing: input.paymentTiming
      })
    });
    return {
      tenantId: raw.tenant_id,
      messageDebounceDelaySeconds: raw.message_debounce_delay_seconds,
      assistantEnabled: raw.assistant_enabled ?? true,
      appointmentReminderEnabled: raw.appointment_reminder_enabled,
      appointmentReminderDaysBefore: raw.appointment_reminder_days_before,
      appointmentReminderAttendanceTemplateName: raw.appointment_reminder_attendance_template_name,
      appointmentReminderPaymentTemplateName: raw.appointment_reminder_payment_template_name,
      paymentDetailsText: raw.payment_details_text,
      officeLocation:
        raw.office_location !== null && raw.office_location !== undefined
          ? {
              address: raw.office_location.address,
              arrivalInstructions: raw.office_location.arrival_instructions
            }
          : null,
      paymentTiming: raw.payment_timing ?? "BEFORE_SESSION"
    };
  }

  async getProfessionalProfile(): Promise<agentModel.ProfessionalProfile> {
    const raw = await this.request<httpTypes.ProfessionalProfileApiResponse>(
      "/v1/agent/professional-profile",
      { method: "GET", authRequired: true }
    );
    return mapProfessionalProfile(raw);
  }

  async updateProfessionalProfile(
    input: agentModel.UpdateProfessionalProfileInput
  ): Promise<agentModel.ProfessionalProfile> {
    const raw = await this.request<httpTypes.ProfessionalProfileApiResponse>(
      "/v1/agent/professional-profile",
      {
        method: "PUT",
        authRequired: true,
        body: JSON.stringify(
          profileInputToApi(input) satisfies httpTypes.UpdateProfessionalProfileApiRequest
        )
      }
    );
    return mapProfessionalProfile(raw);
  }

  async listReminders(status?: string): Promise<scheduledReminderModel.ScheduledReminderList> {
    const params = status !== undefined ? `?status=${status}` : "";
    const raw = await this.request<{
      items: {
        reminder_id: string;
        source_type: string;
        source_id: string;
        patient_whatsapp_user_id: string;
        patient_name: string;
        appointment_start_at: string;
        reminder_scheduled_for: string;
        template_name: string;
        status: string;
        failure_reason: string | null;
        created_at: string;
      }[];
    }>(`/v1/reminders${params}`, { method: "GET", authRequired: true });
    return {
      items: raw.items.map((item) => ({
        reminderId: item.reminder_id,
        sourceType: item.source_type as "SCHEDULING_REQUEST" | "MANUAL_APPOINTMENT",
        sourceId: item.source_id,
        patientWhatsappUserId: item.patient_whatsapp_user_id,
        patientName: item.patient_name,
        appointmentStartAt: item.appointment_start_at,
        reminderScheduledFor: item.reminder_scheduled_for,
        templateName: item.template_name,
        status: item.status as "PENDING" | "SENT" | "FAILED" | "CANCELLED",
        failureReason: item.failure_reason,
        createdAt: item.created_at
      }))
    };
  }

  async sendReminderNow(reminderId: string): Promise<void> {
    await this.request<{ status: string }>(`/v1/reminders/${reminderId}/send-now`, {
      method: "POST",
      authRequired: true
    });
  }

  async createEmbeddedSignupSession(
    registrationPin?: string
  ): Promise<whatsappModel.EmbeddedSignupSession> {
    const bodyPayload: Record<string, string> = {};
    if (registrationPin) {
      bodyPayload["registration_pin"] = registrationPin;
    }

    const payload = await this.request<httpTypes.EmbeddedSignupSessionApiResponse>(
      "/v1/whatsapp/embedded-signup/session",
      {
        method: "POST",
        authRequired: true,
        body: JSON.stringify(bodyPayload)
      }
    );

    return {
      state: payload.state,
      connectUrl: payload.connect_url,
      appId: payload.app_id,
      configId: payload.config_id
    };
  }

  async completeEmbeddedSignup(
    request: whatsappModel.EmbeddedSignupCompleteRequest
  ): Promise<whatsappModel.WhatsappConnection> {
    const payload = await this.request<httpTypes.WhatsappConnectionApiResponse>(
      "/v1/whatsapp/embedded-signup/complete",
      {
        method: "POST",
        authRequired: true,
        body: JSON.stringify({
          code: request.code ?? null,
          state: request.state,
          registration_pin: request.registrationPin ?? null,
          origin_url: request.originUrl ?? null,
          access_token: request.accessToken ?? null,
          phone_number_id: request.phoneNumberId ?? null,
          waba_id: request.wabaId ?? null
        })
      }
    );
    return {
      tenantId: payload.tenant_id,
      status: payload.status,
      phoneNumberId: payload.phone_number_id,
      businessAccountId: payload.business_account_id
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
      contactName: item.contact_name ?? null,
      lastMessagePreview: item.last_message_preview,
      updatedAt: item.updated_at,
      controlMode: item.control_mode,
      tags: (item.tags ?? []).map((tag) => ({
        id: tag.id,
        name: tag.name,
        slug: tag.slug,
        color: tag.color,
        tagType: tag.tag_type
      }))
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

  async sendConversationMessage(
    conversationId: string,
    messageText: string
  ): Promise<conversationModel.MessageSent> {
    const payload = await this.request<httpTypes.MessageSentApiResponse>(
      `/v1/conversations/${conversationId}/messages`,
      {
        method: "POST",
        authRequired: true,
        body: JSON.stringify({
          message_text: messageText
        } satisfies httpTypes.SendMessageApiRequest)
      }
    );

    return {
      messageId: payload.message_id,
      conversationId: payload.conversation_id,
      role: payload.role,
      content: payload.content,
      createdAt: payload.created_at
    };
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

  async listPatients(params?: { search?: string }): Promise<patientModel.Patient[]> {
    const search = params?.search?.trim();
    const qs = search !== undefined && search !== "" ? `?search=${encodeURIComponent(search)}` : "";
    const payload = await this.request<httpTypes.PatientListApiResponse>(`/v1/patients${qs}`, {
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

  async createPatient(input: patientModel.CreatePatientInput): Promise<patientModel.Patient> {
    const payload = await this.request<httpTypes.PatientApiResponse>("/v1/patients", {
      method: "POST",
      authRequired: true,
      body: JSON.stringify({
        whatsapp_user_id: input.whatsappUserId,
        first_name: input.firstName,
        last_name: input.lastName,
        email: input.email,
        age: input.age,
        location: input.location,
        phone_prefix: input.phonePrefix,
        phone: input.phone
      } satisfies httpTypes.CreatePatientApiRequest)
    });
    return mapPatient(payload);
  }

  async updatePatient(
    whatsappUserId: string,
    input: patientModel.UpdatePatientInput
  ): Promise<patientModel.Patient> {
    const payload = await this.request<httpTypes.PatientApiResponse>(
      `/v1/patients/${whatsappUserId}`,
      {
        method: "PUT",
        authRequired: true,
        body: JSON.stringify({
          first_name: input.firstName,
          last_name: input.lastName,
          email: input.email,
          age: input.age,
          location: input.location,
          phone_prefix: input.phonePrefix,
          phone: input.phone
        } satisfies httpTypes.UpdatePatientApiRequest)
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

  async listManualAppointments(
    status?: manualAppointmentModel.ManualAppointmentStatus
  ): Promise<manualAppointmentModel.ManualAppointment[]> {
    const queryParams = new URLSearchParams();
    if (status !== undefined) {
      queryParams.set("status", status);
    }
    const queryString = queryParams.toString();
    const path =
      queryString.length > 0 ? `/v1/manual-appointments?${queryString}` : "/v1/manual-appointments";
    const payload = await this.request<httpTypes.ManualAppointmentListApiResponse>(path, {
      method: "GET",
      authRequired: true
    });
    return payload.items.map(mapManualAppointment);
  }

  async createManualAppointment(
    input: manualAppointmentModel.CreateManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    const payload = await this.request<httpTypes.ManualAppointmentApiResponse>(
      "/v1/manual-appointments",
      {
        method: "POST",
        authRequired: true,
        body: JSON.stringify({
          patient_whatsapp_user_id: input.patientWhatsappUserId,
          start_at: input.startAt,
          end_at: input.endAt,
          timezone: input.timezone,
          summary: input.summary,
          is_virtual: input.isVirtual,
          payment_amount_cop: input.paymentAmountCop,
          payment_currency: input.paymentCurrency,
          payment_status: input.paymentStatus,
          payment_method: input.paymentMethod
        } satisfies httpTypes.CreateManualAppointmentApiRequest)
      }
    );
    return mapManualAppointment(payload);
  }

  async rescheduleManualAppointment(
    appointmentId: string,
    input: manualAppointmentModel.RescheduleManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    const payload = await this.request<httpTypes.ManualAppointmentApiResponse>(
      `/v1/manual-appointments/${appointmentId}/reschedule`,
      {
        method: "PUT",
        authRequired: true,
        body: JSON.stringify({
          start_at: input.startAt,
          end_at: input.endAt,
          timezone: input.timezone,
          summary: input.summary
        } satisfies httpTypes.RescheduleManualAppointmentApiRequest)
      }
    );
    return mapManualAppointment(payload);
  }

  async cancelManualAppointment(
    appointmentId: string,
    input: manualAppointmentModel.CancelManualAppointmentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    const payload = await this.request<httpTypes.ManualAppointmentApiResponse>(
      `/v1/manual-appointments/${appointmentId}`,
      {
        method: "DELETE",
        authRequired: true,
        body: JSON.stringify({
          reason: input.reason
        } satisfies httpTypes.CancelManualAppointmentApiRequest)
      }
    );
    return mapManualAppointment(payload);
  }

  async updateManualAppointmentPayment(
    appointmentId: string,
    input: manualAppointmentModel.UpdateManualAppointmentPaymentInput
  ): Promise<manualAppointmentModel.ManualAppointment> {
    const payload = await this.request<httpTypes.ManualAppointmentApiResponse>(
      `/v1/manual-appointments/${appointmentId}/payment`,
      {
        method: "PUT",
        authRequired: true,
        body: JSON.stringify({
          payment_amount_cop: input.paymentAmountCop,
          payment_currency: input.paymentCurrency ?? "COP",
          payment_method: input.paymentMethod,
          payment_status: input.paymentStatus
        } satisfies httpTypes.UpdateManualAppointmentPaymentApiRequest)
      }
    );
    return mapManualAppointment(payload);
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

  async resolvePaymentReview(
    conversationId: string,
    requestId: string,
    input: schedulingModel.ResolvePaymentReviewInput
  ): Promise<schedulingModel.ResolvePaymentReviewResult> {
    const payload = await this.request<httpTypes.ResolvePaymentReviewApiResponse>(
      `/v1/conversations/${conversationId}/scheduling/requests/${requestId}/payment-review`,
      {
        method: "POST",
        authRequired: true,
        body: JSON.stringify({
          decision: input.decision,
          professional_note: input.professionalNote,
          payment_amount_cop: input.paymentAmountCop,
          payment_currency: input.paymentCurrency
        } satisfies httpTypes.ResolvePaymentReviewApiRequest)
      }
    );

    return {
      status: payload.status,
      outboundMessageId: payload.outbound_message_id,
      assistantText: payload.assistant_text
    };
  }

  async rescheduleBookedSlot(
    requestId: string,
    input: schedulingModel.RescheduleBookedSlotInput
  ): Promise<schedulingModel.SchedulingRequestSummary> {
    const payload = await this.request<httpTypes.SchedulingRequestSummaryApiResponse>(
      `/v1/scheduling-requests/${requestId}/booked-slot/reschedule`,
      {
        method: "PUT",
        authRequired: true,
        body: JSON.stringify({
          start_at: input.startAt,
          end_at: input.endAt,
          timezone: input.timezone,
          event_summary: input.eventSummary
        } satisfies httpTypes.RescheduleBookedSlotApiRequest)
      }
    );
    return mapSchedulingRequestSummary(payload);
  }

  async cancelBookedSlot(
    requestId: string,
    input: schedulingModel.CancelBookedSlotInput
  ): Promise<schedulingModel.SchedulingRequestSummary> {
    const payload = await this.request<httpTypes.SchedulingRequestSummaryApiResponse>(
      `/v1/scheduling-requests/${requestId}/booked-slot`,
      {
        method: "DELETE",
        authRequired: true,
        body: JSON.stringify({
          reason: input.reason
        } satisfies httpTypes.CancelBookedSlotApiRequest)
      }
    );
    return mapSchedulingRequestSummary(payload);
  }

  async updateBookedSlotPayment(
    requestId: string,
    input: schedulingModel.UpdateBookedSlotPaymentInput
  ): Promise<schedulingModel.SchedulingRequestSummary> {
    const payload = await this.request<httpTypes.SchedulingRequestSummaryApiResponse>(
      `/v1/scheduling-requests/${requestId}/booked-slot/payment`,
      {
        method: "PUT",
        authRequired: true,
        body: JSON.stringify({
          payment_amount_cop: input.paymentAmountCop,
          payment_currency: input.paymentCurrency,
          payment_method: input.paymentMethod,
          payment_status: input.paymentStatus
        } satisfies httpTypes.UpdateBookedSlotPaymentApiRequest)
      }
    );
    return mapSchedulingRequestSummary(payload);
  }

  async closeSession(conversationId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(
      `/v1/conversations/${conversationId}/scheduling/close-session`,
      {
        method: "POST",
        authRequired: true
      }
    );
  }

  async getDevFeatures(): Promise<{ enabled: boolean; sandbox_enabled: boolean | null }> {
    return this.request<{ enabled: boolean; sandbox_enabled: boolean | null }>(
      "/v1/settings/dev-features",
      {
        method: "GET",
        authRequired: true
      }
    );
  }

  async updateSandboxMode(enabled: boolean): Promise<{ sandbox_enabled: boolean }> {
    return this.request<{ sandbox_enabled: boolean }>("/v1/settings/sandbox", {
      method: "PUT",
      authRequired: true,
      body: JSON.stringify({ sandbox_enabled: enabled })
    });
  }

  async getTenantProfile(): Promise<tenantModel.TenantProfile> {
    const payload = await this.request<httpTypes.TenantProfileResponse>("/v1/tenant/profile", {
      method: "GET",
      authRequired: true
    });
    return mapTenantProfile(payload);
  }

  async updateTenantProfile(
    input: tenantModel.UpdateTenantProfileInput
  ): Promise<tenantModel.TenantProfile> {
    const requestBody: httpTypes.UpdateTenantProfileRequest = {
      professional_name: input.professionalName
    };
    const payload = await this.request<httpTypes.TenantProfileResponse>("/v1/tenant/profile", {
      method: "PUT",
      authRequired: true,
      body: JSON.stringify(requestBody)
    });
    return mapTenantProfile(payload);
  }

  async listWhatsappTemplates(): Promise<whatsappTemplateModel.WhatsappTemplate[]> {
    const payload = await this.request<httpTypes.TemplateListApiResponse>(
      "/v1/whatsapp/templates",
      {
        method: "GET",
        authRequired: true
      }
    );
    return payload.templates.map(mapWhatsappTemplate);
  }

  async createWhatsappTemplate(
    request: whatsappTemplateModel.CreateTemplateRequest
  ): Promise<whatsappTemplateModel.WhatsappTemplate> {
    const payload = await this.request<httpTypes.WhatsappTemplateApiResponse>(
      "/v1/whatsapp/templates",
      {
        method: "POST",
        authRequired: true,
        body: JSON.stringify({
          name: request.name,
          category: request.category,
          language: request.language,
          components: request.components.map((c) => ({
            type: c.type,
            text: c.text,
            ...(c.exampleValues && c.exampleValues.length > 0
              ? { example_values: c.exampleValues }
              : {})
          }))
        } satisfies httpTypes.CreateTemplateApiRequest)
      }
    );
    return mapWhatsappTemplate(payload);
  }

  async deleteWhatsappTemplate(name: string): Promise<void> {
    await this.request<void>(`/v1/whatsapp/templates/${name}`, {
      method: "DELETE",
      authRequired: true
    });
  }

  async listOfficialTemplateStatus(): Promise<whatsappTemplateModel.OfficialTemplateStatus[]> {
    const raw = await this.request<{
      items: {
        kind: string;
        name: string;
        meta_status: string;
        rejection_reason: string | null;
      }[];
    }>("/v1/whatsapp/templates/official/status", { method: "GET", authRequired: true });
    return raw.items.map(mapOfficialTemplateStatus);
  }

  async activateOfficialTemplate(
    kind: whatsappTemplateModel.OfficialReminderKind
  ): Promise<whatsappTemplateModel.OfficialTemplateStatus> {
    const raw = await this.request<{
      kind: string;
      name: string;
      meta_status: string;
      rejection_reason: string | null;
    }>(`/v1/whatsapp/templates/official/${kind}/activate`, {
      method: "POST",
      authRequired: true
    });
    return mapOfficialTemplateStatus(raw);
  }

  async deactivateOfficialTemplate(
    kind: whatsappTemplateModel.OfficialReminderKind
  ): Promise<void> {
    await this.request<void>(`/v1/whatsapp/templates/official/${kind}/deactivate`, {
      method: "POST",
      authRequired: true
    });
  }

  async listEvalShapes(): Promise<evaluationModel.EvalShape[]> {
    const raw = await this.request<{
      items: {
        name: string;
        description: string;
        required_combos: string[][];
        rendered_system_prompt: string;
      }[];
    }>("/v1/eval/shapes", { method: "GET", authRequired: false });
    return raw.items.map((item) => ({
      name: item.name,
      description: item.description,
      requiredCombos: item.required_combos,
      renderedSystemPrompt: item.rendered_system_prompt
    }));
  }

  async listEvalPersonas(): Promise<evaluationModel.EvalPersona[]> {
    const raw = await this.request<{
      items: {
        id: string;
        display_name: string;
        capabilities: string[];
        profile_group: string;
      }[];
    }>("/v1/eval/personas", { method: "GET", authRequired: false });
    return raw.items.map((item) => ({
      id: item.id,
      displayName: item.display_name,
      capabilities: item.capabilities,
      profileGroup: item.profile_group
    }));
  }

  async listEvalPromptVersions(): Promise<evaluationModel.EvalPromptVersion[]> {
    const raw = await this.request<{
      items: {
        id: string;
        label: string;
        active: boolean;
      }[];
    }>("/v1/eval/prompt-versions", { method: "GET", authRequired: false });
    return raw.items.map((item) => ({
      id: item.id,
      label: item.label,
      active: item.active
    }));
  }

  async listEvalRuns(limit?: number): Promise<evaluationModel.EvalRunListItem[]> {
    const qs = limit !== undefined ? `?limit=${limit}` : "";
    const raw = await this.request<{
      items: {
        run_doc_id: string;
        run_id: string;
        shape_name: string;
        started_at: string;
        finished_at: string | null;
        total_personas: number;
        ok: number;
        fail: number;
        skipped: boolean;
      }[];
    }>(`/v1/eval/runs${qs}`, { method: "GET", authRequired: false });
    return raw.items.map((item) => ({
      runDocId: item.run_doc_id,
      runId: item.run_id,
      shapeName: item.shape_name,
      startedAt: item.started_at,
      finishedAt: item.finished_at,
      totalPersonas: item.total_personas,
      ok: item.ok,
      fail: item.fail,
      skipped: item.skipped
    }));
  }

  async deleteEvalRun(runId: string): Promise<evaluationModel.EvalDeleteResult> {
    // Usa JWT del tenant logueado (cualquier role del ambiente dev). El
    // EVAL_ADMIN_SECRET solo aplica a /v1/dev/eval-tenants (writes invasivos
    // de tenants), no al borrado de un run.
    const raw = await this.request<{ eval_runs_deleted: number; tenants_deleted: number }>(
      `/v1/dev/eval-runs/${runId}`,
      { method: "DELETE", authRequired: true }
    );
    return {
      evalRunsDeleted: raw.eval_runs_deleted,
      tenantsDeleted: raw.tenants_deleted
    };
  }

  async listEvalCapabilities(): Promise<evaluationModel.EvalCapabilityDoc[]> {
    const raw = await this.request<{
      items: {
        id: string;
        description: string;
        implications: string;
        category: evaluationModel.EvalCapabilityCategory;
      }[];
    }>("/v1/eval/capabilities", { method: "GET", authRequired: false });
    return raw.items.map((item) => ({
      id: item.id,
      description: item.description,
      implications: item.implications,
      category: item.category
    }));
  }

  async getEvalRun(runDocId: string): Promise<evaluationModel.EvalRunDetail> {
    const raw = await this.request<{
      run_doc_id: string;
      run_id: string;
      shape_name: string;
      prompt_version_id: string | null;
      started_at: string;
      finished_at: string | null;
      total_personas: number;
      ok: number;
      fail: number;
      skipped: boolean;
      conversations: {
        persona_id: string;
        combos_satisfied: string[][];
        status: "ok" | "fail" | "skipped";
        elapsed_seconds: number | null;
        conversation_id: string | null;
        scheduling_request_id: string | null;
        final_status: string | null;
        error: string | null;
        transcript: {
          direction: "INBOUND" | "OUTBOUND";
          content: string;
          timestamp: string;
        }[];
        judge_verdict: {
          declared_capabilities: string[];
          verifications: {
            capability: string;
            verified: boolean;
            evidence: string | null;
            reasoning: string | null;
          }[];
          overall: "all_verified" | "partial" | "none";
          judge_model: string;
          judged_at: string;
          error: string | null;
        } | null;
      }[];
    }>(`/v1/eval/runs/${runDocId}`, { method: "GET", authRequired: false });
    return {
      runDocId: raw.run_doc_id,
      runId: raw.run_id,
      shapeName: raw.shape_name,
      promptVersionId: raw.prompt_version_id,
      startedAt: raw.started_at,
      finishedAt: raw.finished_at,
      totalPersonas: raw.total_personas,
      ok: raw.ok,
      fail: raw.fail,
      skipped: raw.skipped,
      conversations: raw.conversations.map((conv) => ({
        personaId: conv.persona_id,
        combosSatisfied: conv.combos_satisfied,
        status: conv.status,
        elapsedSeconds: conv.elapsed_seconds,
        conversationId: conv.conversation_id,
        schedulingRequestId: conv.scheduling_request_id,
        finalStatus: conv.final_status,
        error: conv.error,
        transcript: conv.transcript.map((msg) => ({
          direction: msg.direction,
          content: msg.content,
          timestamp: msg.timestamp
        })),
        judgeVerdict:
          conv.judge_verdict !== null && conv.judge_verdict !== undefined
            ? {
                declaredCapabilities: conv.judge_verdict.declared_capabilities,
                verifications: conv.judge_verdict.verifications.map((v) => ({
                  capability: v.capability,
                  verified: v.verified,
                  evidence: v.evidence,
                  reasoning: v.reasoning
                })),
                overall: conv.judge_verdict.overall,
                judgeModel: conv.judge_verdict.judge_model,
                judgedAt: conv.judge_verdict.judged_at,
                error: conv.judge_verdict.error
              }
            : null
      }))
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

    if (options.customHeaders !== undefined) {
      for (const [key, value] of Object.entries(options.customHeaders)) {
        headers.set(key, value);
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

    let payload: Partial<httpTypes.ApiErrorResponse> & { detail?: unknown };
    try {
      payload = (await response.json()) as Partial<httpTypes.ApiErrorResponse> & {
        detail?: unknown;
      };
    } catch (error: unknown) {
      if (error instanceof SyntaxError) {
        return new apiErrorModule.ApiError(response.status, fallbackMessage, resolvedRequestId);
      }
      throw error;
    }

    const requestIdFromBody =
      typeof payload.request_id === "string" ? normalizeRequestId(payload.request_id) : null;
    const finalRequestId = requestIdFromBody ?? resolvedRequestId;

    const detail = payload.detail;
    if (typeof detail === "string") {
      const trimmed = detail.trim();
      if (trimmed === "") {
        return new apiErrorModule.ApiError(response.status, fallbackMessage, finalRequestId);
      }
      return new apiErrorModule.ApiError(response.status, detail, finalRequestId, detail);
    }
    if (detail !== null && typeof detail === "object") {
      const detailObject = detail as Record<string, unknown>;
      const detailMessage = detailObject["message"];
      const messageFromDetail =
        typeof detailMessage === "string" && detailMessage.trim() !== ""
          ? detailMessage
          : fallbackMessage;
      return new apiErrorModule.ApiError(
        response.status,
        messageFromDetail,
        finalRequestId,
        detailObject
      );
    }
    return new apiErrorModule.ApiError(response.status, fallbackMessage, finalRequestId);
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
    location: payload.location,
    phonePrefix: payload.phone_prefix ?? null,
    phone: payload.phone,
    createdAt: payload.created_at
  };
}

function mapManualAppointment(
  payload: httpTypes.ManualAppointmentApiResponse
): manualAppointmentModel.ManualAppointment {
  return {
    appointmentId: payload.appointment_id,
    tenantId: payload.tenant_id,
    patientWhatsappUserId: payload.patient_whatsapp_user_id,
    status: payload.status,
    calendarEventId: payload.calendar_event_id,
    startAt: payload.start_at,
    endAt: payload.end_at,
    timezone: payload.timezone,
    summary: payload.summary,
    isVirtual: payload.is_virtual,
    meetUrl: payload.meet_url,
    paymentAmountCop: payload.payment_amount_cop ?? null,
    paymentCurrency: payload.payment_currency ?? "COP",
    paymentMethod: payload.payment_method ?? null,
    paymentStatus: payload.payment_status ?? "PENDING",
    paymentUpdatedAt: payload.payment_updated_at ?? null,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
    cancelledAt: payload.cancelled_at
  };
}

function mapWhatsappTemplate(
  payload: httpTypes.WhatsappTemplateApiResponse
): whatsappTemplateModel.WhatsappTemplate {
  return {
    id: payload.id,
    name: payload.name,
    category: payload.category,
    language: payload.language,
    status: payload.status,
    components: payload.components.map((c) => ({
      type: c.type,
      text: c.text,
      ...(c.example_values ? { exampleValues: c.example_values } : {})
    }))
  };
}

function mapOfficialTemplateStatus(raw: {
  kind: string;
  name: string;
  meta_status: string;
  rejection_reason: string | null;
}): whatsappTemplateModel.OfficialTemplateStatus {
  return {
    kind: raw.kind as whatsappTemplateModel.OfficialReminderKind,
    name: raw.name,
    metaStatus: raw.meta_status as whatsappTemplateModel.OfficialTemplateMetaStatus,
    rejectionReason: raw.rejection_reason
  };
}

function mapTenantProfile(payload: httpTypes.TenantProfileResponse): tenantModel.TenantProfile {
  return {
    tenantId: payload.tenant_id,
    name: payload.name,
    professionalName: payload.professional_name
  };
}

function mapTariffOption(raw: httpTypes.TariffOptionApiResponse): agentModel.TariffOption {
  return {
    label: raw.label,
    description: raw.description,
    prices: raw.prices.map((p) => ({ currency: p.currency, amount: p.amount }))
  };
}

function tariffOptionToApi(item: agentModel.TariffOption): httpTypes.TariffOptionApiResponse {
  return {
    label: item.label,
    description: item.description,
    prices: item.prices.map((p) => ({ currency: p.currency, amount: p.amount }))
  };
}

function mapScheduleBlock(raw: httpTypes.ScheduleBlockApiResponse): agentModel.ScheduleBlock {
  return {
    weekdayFrom: raw.weekday_from as agentModel.Weekday,
    weekdayTo:
      raw.weekday_to !== null && raw.weekday_to !== undefined
        ? (raw.weekday_to as agentModel.Weekday)
        : null,
    startTime: raw.start_time,
    endTime: raw.end_time
  };
}

function scheduleBlockToApi(item: agentModel.ScheduleBlock): httpTypes.ScheduleBlockApiResponse {
  return {
    weekday_from: item.weekdayFrom,
    weekday_to: item.weekdayTo,
    start_time: item.startTime,
    end_time: item.endTime
  };
}

function mapServiceOffering(raw: httpTypes.ServiceOfferingApiResponse): agentModel.ServiceOffering {
  // Default fully-visible when the field is missing (legacy data).
  const rawTargetPatients =
    raw.target_patients !== undefined &&
    raw.target_patients !== null &&
    raw.target_patients.length > 0
      ? raw.target_patients
      : ["NEW", "RETURNING"];
  return {
    name: raw.name,
    description: raw.description,
    modalities: raw.modalities as agentModel.Modality[],
    targetPatients: rawTargetPatients as agentModel.TargetPatient[],
    tariffs: raw.tariffs.map(mapTariffOption)
  };
}

function serviceOfferingToApi(
  item: agentModel.ServiceOffering
): httpTypes.ServiceOfferingApiResponse {
  return {
    name: item.name,
    description: item.description,
    modalities: item.modalities,
    target_patients: item.targetPatients,
    tariffs: item.tariffs.map(tariffOptionToApi)
  };
}

function mapPaymentMethod(raw: httpTypes.PaymentMethodApiResponse): agentModel.PaymentMethod {
  return {
    currency: raw.currency,
    methodName: raw.method_name,
    holder: raw.holder,
    instructions: raw.instructions,
    appliesWhen: raw.applies_when
  };
}

function paymentMethodToApi(item: agentModel.PaymentMethod): httpTypes.PaymentMethodApiResponse {
  return {
    currency: item.currency,
    method_name: item.methodName,
    holder: item.holder,
    instructions: item.instructions,
    applies_when: item.appliesWhen
  };
}

function mapProfessionalProfile(
  raw: httpTypes.ProfessionalProfileApiResponse
): agentModel.ProfessionalProfile {
  return {
    tenantId: raw.tenant_id,
    identity:
      raw.identity !== null && raw.identity !== undefined
        ? {
            assistantName: raw.identity.assistant_name,
            professionalTitle: raw.identity.professional_title,
            professionalName: raw.identity.professional_name,
            professionalAddressTerm: raw.identity.professional_address_term,
            mainCity: raw.identity.main_city,
            tone: raw.identity.tone,
            languages: raw.identity.languages
          }
        : null,
    professionalContext:
      raw.professional_context !== null && raw.professional_context !== undefined
        ? {
            approach: raw.professional_context.approach,
            commonTopics: raw.professional_context.common_topics,
            servicesNotOffered: raw.professional_context.services_not_offered,
            coverageNotes: raw.professional_context.coverage_notes
          }
        : null,
    services: raw.services.map(mapServiceOffering),
    presencialSchedule: raw.presencial_schedule.map(mapScheduleBlock),
    virtualSchedule: raw.virtual_schedule.map(mapScheduleBlock),
    paymentMethods: raw.payment_methods.map(mapPaymentMethod)
  };
}

function profileInputToApi(
  input: agentModel.UpdateProfessionalProfileInput
): httpTypes.UpdateProfessionalProfileApiRequest {
  return {
    identity:
      input.identity !== null
        ? {
            assistant_name: input.identity.assistantName,
            professional_title: input.identity.professionalTitle,
            professional_name: input.identity.professionalName,
            professional_address_term: input.identity.professionalAddressTerm,
            main_city: input.identity.mainCity,
            tone: input.identity.tone,
            languages: input.identity.languages
          }
        : null,
    professional_context:
      input.professionalContext !== null
        ? {
            approach: input.professionalContext.approach,
            common_topics: input.professionalContext.commonTopics,
            services_not_offered: input.professionalContext.servicesNotOffered,
            coverage_notes: input.professionalContext.coverageNotes
          }
        : null,
    services: input.services.map(serviceOfferingToApi),
    presencial_schedule: input.presencialSchedule.map(scheduleBlockToApi),
    virtual_schedule: input.virtualSchedule.map(scheduleBlockToApi),
    payment_methods: input.paymentMethods.map(paymentMethodToApi)
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
    audienceType: payload.audience_type ?? null,
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
    paymentAmountCop: payload.payment_amount_cop ?? null,
    paymentCurrency: payload.payment_currency ?? "COP",
    paymentMethod: payload.payment_method ?? null,
    paymentStatus: payload.payment_status ?? "PENDING",
    paymentUpdatedAt: payload.payment_updated_at ?? null,
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

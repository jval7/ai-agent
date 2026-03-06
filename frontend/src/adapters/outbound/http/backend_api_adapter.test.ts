import * as mswModule from "msw";
import * as vitestModule from "vitest";

import * as serverModule from "@shared/testing/msw/server";

import * as backendApiAdapterModule from "./backend_api_adapter";

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

vitestModule.describe("BackendApiAdapter", () => {
  vitestModule.it("maps login response to domain tokens", async () => {
    serverModule.server.use(
      mswModule.http.post("http://api.test/v1/auth/login", ({ request }) => {
        const requestId = request.headers.get("x-request-id");
        vitestModule.expect(typeof requestId).toBe("string");
        vitestModule.expect(requestId?.trim().length ?? 0).toBeGreaterThan(0);
        return mswModule.HttpResponse.json({
          access_token: "access-1",
          refresh_token: "refresh-1",
          token_type: "bearer",
          expires_in_seconds: 1800
        });
      })
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const tokens = await adapter.login({ email: "owner@acme.com", password: "supersecret" });

    vitestModule.expect(tokens.accessToken).toBe("access-1");
    vitestModule.expect(tokens.refreshToken).toBe("refresh-1");
    vitestModule.expect(tokens.expiresInSeconds).toBe(1800);
  });

  vitestModule.it("refreshes access token on 401 and retries original request", async () => {
    let getPromptCalls = 0;

    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/agent/system-prompt", ({ request }) => {
        getPromptCalls += 1;
        const authHeader = request.headers.get("authorization");

        if (authHeader === "Bearer stale-access") {
          return new mswModule.HttpResponse(null, { status: 401 });
        }

        if (authHeader === "Bearer fresh-access") {
          return mswModule.HttpResponse.json({
            tenant_id: "tenant-1",
            system_prompt: "Hola"
          });
        }

        return new mswModule.HttpResponse(null, { status: 403 });
      }),
      mswModule.http.post("http://api.test/v1/auth/refresh", async ({ request }) => {
        const body = (await request.json()) as { refresh_token: string };
        vitestModule.expect(body.refresh_token).toBe("refresh-1");

        return mswModule.HttpResponse.json({
          access_token: "fresh-access",
          refresh_token: "refresh-2",
          token_type: "bearer",
          expires_in_seconds: 1800
        });
      })
    );

    const tokenSession = new InMemoryTokenSession("stale-access", "refresh-1");
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const prompt = await adapter.getSystemPrompt();

    vitestModule.expect(prompt.systemPrompt).toBe("Hola");
    vitestModule.expect(prompt.tenantId).toBe("tenant-1");
    vitestModule.expect(getPromptCalls).toBe(2);
    vitestModule.expect(tokenSession.getAccessToken()).toBe("fresh-access");
    vitestModule.expect(tokenSession.getRefreshToken()).toBe("refresh-2");
  });

  vitestModule.it("maps backend request_id into ApiError", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/agent/system-prompt", () =>
        mswModule.HttpResponse.json(
          {
            detail: "internal server error",
            request_id: "req-123"
          },
          { status: 500 }
        )
      )
    );

    const tokenSession = new InMemoryTokenSession("access-1", "refresh-1");
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    await vitestModule.expect(adapter.getSystemPrompt()).rejects.toMatchObject({
      name: "ApiError",
      statusCode: 500,
      message: "internal server error",
      requestId: "req-123"
    });
  });

  vitestModule.it("maps google calendar, onboarding and scheduling endpoints", async () => {
    serverModule.server.use(
      mswModule.http.post("http://api.test/v1/google-calendar/oauth/session", () => {
        return mswModule.HttpResponse.json({
          state: "state-1",
          connect_url: "https://google.test/oauth"
        });
      }),
      mswModule.http.get("http://api.test/v1/google-calendar/connection", () => {
        return mswModule.HttpResponse.json({
          tenant_id: "tenant-1",
          status: "CONNECTED",
          calendar_id: "primary",
          professional_timezone: "America/Bogota",
          connected_at: "2026-03-01T12:00:00Z"
        });
      }),
      mswModule.http.get("http://api.test/v1/onboarding/status", () => {
        return mswModule.HttpResponse.json({
          whatsapp_connected: true,
          google_calendar_connected: true,
          ready: true
        });
      }),
      mswModule.http.get("http://api.test/v1/google-calendar/availability", ({ request }) => {
        const url = new URL(request.url);
        vitestModule.expect(url.searchParams.get("from")).toBe("2026-03-01T00:00:00Z");
        vitestModule.expect(url.searchParams.get("to")).toBe("2026-03-31T23:59:59Z");
        return mswModule.HttpResponse.json({
          tenant_id: "tenant-1",
          calendar_id: "primary",
          timezone: "America/Bogota",
          busy_intervals: [
            {
              start_at: "2026-03-01T10:00:00Z",
              end_at: "2026-03-01T11:00:00Z"
            }
          ]
        });
      }),
      mswModule.http.get("http://api.test/v1/scheduling-requests", ({ request }) => {
        const url = new URL(request.url);
        vitestModule.expect(url.searchParams.get("status")).toBe("AWAITING_CONSULTATION_REVIEW");
        return mswModule.HttpResponse.json({
          items: [
            {
              request_id: "req-1",
              conversation_id: "conv-1",
              whatsapp_user_id: "wa-1",
              request_kind: "INITIAL",
              status: "AWAITING_CONSULTATION_REVIEW",
              round_number: 1,
              patient_preference_note: "prefiere tarde",
              rejection_summary: null,
              professional_note: null,
              slot_options_map: {},
              selected_slot_id: null,
              calendar_event_id: null,
              payment_amount_cop: null,
              payment_method: null,
              payment_status: "PENDING",
              payment_updated_at: null,
              created_at: "2026-03-01T10:00:00Z",
              updated_at: "2026-03-01T10:00:00Z",
              slots: []
            }
          ]
        });
      }),
      mswModule.http.get("http://api.test/v1/conversations/conv-1/scheduling/requests", () => {
        return mswModule.HttpResponse.json({
          items: []
        });
      }),
      mswModule.http.get("http://api.test/v1/patients", () => {
        return mswModule.HttpResponse.json({
          items: [
            {
              tenant_id: "tenant-1",
              whatsapp_user_id: "wa-1",
              first_name: "Jane",
              last_name: "Doe",
              email: "jane@example.com",
              age: 29,
              consultation_reason: "Ansiedad",
              location: "Bogota",
              phone: "573001112233",
              created_at: "2026-03-01T10:00:00Z"
            }
          ]
        });
      }),
      mswModule.http.get("http://api.test/v1/patients/wa-1", () => {
        return mswModule.HttpResponse.json({
          tenant_id: "tenant-1",
          whatsapp_user_id: "wa-1",
          first_name: "Jane",
          last_name: "Doe",
          email: "jane@example.com",
          age: 29,
          consultation_reason: "Ansiedad",
          location: "Bogota",
          phone: "573001112233",
          created_at: "2026-03-01T10:00:00Z"
        });
      }),
      mswModule.http.post(
        "http://api.test/v1/conversations/conv-1/scheduling/requests/req-1/professional-slots",
        async ({ request }) => {
          const body = (await request.json()) as {
            slots: {
              slot_id: string;
              start_at: string;
              end_at: string;
              timezone: string;
            }[];
            professional_note: string | null;
          };
          vitestModule.expect(body.slots).toHaveLength(1);
          vitestModule.expect(body.slots[0]?.slot_id).toBe("req-1_20260301_1000");
          vitestModule.expect(body.professional_note).toBe("elige cualquiera");
          return mswModule.HttpResponse.json({
            status: "AWAITING_PATIENT_CHOICE",
            slot_batch_id: "req-1",
            outbound_message_id: "wamid-1",
            assistant_text: "Listo, ya te mostré opciones."
          });
        }
      ),
      mswModule.http.put(
        "http://api.test/v1/manual-appointments/appt-1/payment",
        async ({ request }) => {
          const body = (await request.json()) as {
            payment_amount_cop: number;
            payment_method: "CASH" | "TRANSFER";
            payment_status: "PENDING" | "PAID";
          };
          vitestModule.expect(body.payment_amount_cop).toBe(120000);
          vitestModule.expect(body.payment_method).toBe("TRANSFER");
          vitestModule.expect(body.payment_status).toBe("PAID");
          return mswModule.HttpResponse.json({
            appointment_id: "appt-1",
            tenant_id: "tenant-1",
            patient_whatsapp_user_id: "wa-1",
            status: "SCHEDULED",
            calendar_event_id: "event-1",
            start_at: "2026-03-10T10:00:00Z",
            end_at: "2026-03-10T11:00:00Z",
            timezone: "America/Bogota",
            summary: "Cita control",
            payment_amount_cop: 120000,
            payment_method: "TRANSFER",
            payment_status: "PAID",
            payment_updated_at: "2026-03-10T09:00:00Z",
            created_at: "2026-03-01T10:00:00Z",
            updated_at: "2026-03-10T09:00:00Z",
            cancelled_at: null
          });
        }
      ),
      mswModule.http.put(
        "http://api.test/v1/scheduling-requests/req-1/booked-slot/payment",
        async ({ request }) => {
          const body = (await request.json()) as {
            payment_amount_cop: number;
            payment_method: "CASH" | "TRANSFER";
            payment_status: "PENDING" | "PAID";
          };
          vitestModule.expect(body.payment_amount_cop).toBe(80000);
          vitestModule.expect(body.payment_method).toBe("CASH");
          vitestModule.expect(body.payment_status).toBe("PENDING");
          return mswModule.HttpResponse.json({
            request_id: "req-1",
            conversation_id: "conv-1",
            whatsapp_user_id: "wa-1",
            request_kind: "INITIAL",
            status: "BOOKED",
            round_number: 1,
            patient_preference_note: "prefiere tarde",
            rejection_summary: null,
            professional_note: null,
            patient_first_name: "Jane",
            patient_last_name: "Doe",
            patient_age: 30,
            consultation_reason: "Control",
            consultation_details: null,
            appointment_modality: "VIRTUAL",
            patient_location: "Bogota",
            slot_options_map: {},
            selected_slot_id: "slot-1",
            calendar_event_id: "event-1",
            payment_amount_cop: 80000,
            payment_method: "CASH",
            payment_status: "PENDING",
            payment_updated_at: "2026-03-10T10:30:00Z",
            created_at: "2026-03-01T10:00:00Z",
            updated_at: "2026-03-10T10:30:00Z",
            slots: [
              {
                slot_id: "slot-1",
                start_at: "2026-03-10T10:00:00Z",
                end_at: "2026-03-10T11:00:00Z",
                timezone: "America/Bogota",
                status: "BOOKED"
              }
            ]
          });
        }
      )
    );

    const tokenSession = new InMemoryTokenSession("access-1", "refresh-1");
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const googleSession = await adapter.createGoogleOauthSession();
    const googleConnection = await adapter.getGoogleCalendarConnection();
    const onboardingStatus = await adapter.getOnboardingStatus();
    const availability = await adapter.getGoogleCalendarAvailability(
      "2026-03-01T00:00:00Z",
      "2026-03-31T23:59:59Z"
    );
    const requests = await adapter.listSchedulingRequests("AWAITING_CONSULTATION_REVIEW");
    const conversationRequests = await adapter.listConversationSchedulingRequests("conv-1");
    const patients = await adapter.listPatients();
    const patient = await adapter.getPatient("wa-1");
    const submitResult = await adapter.submitProfessionalSlots("conv-1", "req-1", {
      slots: [
        {
          slotId: "req-1_20260301_1000",
          startAt: "2026-03-01T10:00:00Z",
          endAt: "2026-03-01T11:00:00Z",
          timezone: "America/Bogota"
        }
      ],
      professionalNote: "elige cualquiera"
    });
    const manualPaymentUpdate = await adapter.updateManualAppointmentPayment("appt-1", {
      paymentAmountCop: 120000,
      paymentMethod: "TRANSFER",
      paymentStatus: "PAID"
    });
    const bookedPaymentUpdate = await adapter.updateBookedSlotPayment("req-1", {
      paymentAmountCop: 80000,
      paymentMethod: "CASH",
      paymentStatus: "PENDING"
    });

    vitestModule.expect(googleSession.connectUrl).toBe("https://google.test/oauth");
    vitestModule.expect(googleConnection.professionalTimezone).toBe("America/Bogota");
    vitestModule.expect(onboardingStatus.ready).toBe(true);
    vitestModule.expect(availability.busyIntervals).toHaveLength(1);
    vitestModule.expect(requests[0]?.requestId).toBe("req-1");
    vitestModule.expect(conversationRequests).toEqual([]);
    vitestModule.expect(patients[0]?.firstName).toBe("Jane");
    vitestModule.expect(patient.location).toBe("Bogota");
    vitestModule.expect(submitResult.outboundMessageId).toBe("wamid-1");
    vitestModule.expect(manualPaymentUpdate.paymentStatus).toBe("PAID");
    vitestModule.expect(bookedPaymentUpdate.paymentAmountCop).toBe(80000);
  });

  vitestModule.it("resets conversation messages with DELETE endpoint", async () => {
    serverModule.server.use(
      mswModule.http.delete("http://api.test/v1/conversations/conv-1/messages", ({ request }) => {
        const authHeader = request.headers.get("authorization");
        vitestModule.expect(authHeader).toBe("Bearer access-1");
        return new mswModule.HttpResponse(null, { status: 204 });
      })
    );

    const tokenSession = new InMemoryTokenSession("access-1", "refresh-1");
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    await adapter.resetConversationMessages("conv-1");
  });

  vitestModule.it("deletes patient with DELETE endpoint", async () => {
    serverModule.server.use(
      mswModule.http.delete("http://api.test/v1/patients/wa-1", ({ request }) => {
        const authHeader = request.headers.get("authorization");
        vitestModule.expect(authHeader).toBe("Bearer access-1");
        return new mswModule.HttpResponse(null, { status: 204 });
      })
    );

    const tokenSession = new InMemoryTokenSession("access-1", "refresh-1");
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    await adapter.removePatient("wa-1");
  });
});

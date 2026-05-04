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
              payment_currency: "COP",
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
              location: "Bogota",
              phone_prefix: null,
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
          location: "Bogota",
          phone_prefix: null,
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
            payment_currency: "COP" | "USD";
            payment_method: "CASH" | "TRANSFER";
            payment_status: "PENDING" | "PAID";
          };
          vitestModule.expect(body.payment_amount_cop).toBe(80000);
          vitestModule.expect(body.payment_currency).toBe("USD");
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
            payment_currency: "USD",
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
      paymentCurrency: "USD",
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
    vitestModule.expect(bookedPaymentUpdate.paymentCurrency).toBe("USD");
  });

  vitestModule.it("maps getTenantProfile and updateTenantProfile endpoints", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/tenant/profile", ({ request }) => {
        const authHeader = request.headers.get("authorization");
        vitestModule.expect(authHeader).toBe("Bearer access-1");
        return mswModule.HttpResponse.json({
          tenant_id: "tenant-1",
          name: "Ana Garcia",
          professional_name: "Dra. Ana Garcia"
        });
      }),
      mswModule.http.put("http://api.test/v1/tenant/profile", async ({ request }) => {
        const body = (await request.json()) as { professional_name: string | null };
        vitestModule.expect(body.professional_name).toBe("Dra. Ana M. Garcia");
        return mswModule.HttpResponse.json({
          tenant_id: "tenant-1",
          name: "Ana Garcia",
          professional_name: "Dra. Ana M. Garcia"
        });
      })
    );

    const tokenSession = new InMemoryTokenSession("access-1", "refresh-1");
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const profile = await adapter.getTenantProfile();
    vitestModule.expect(profile.tenantId).toBe("tenant-1");
    vitestModule.expect(profile.name).toBe("Ana Garcia");
    vitestModule.expect(profile.professionalName).toBe("Dra. Ana Garcia");

    const updated = await adapter.updateTenantProfile({ professionalName: "Dra. Ana M. Garcia" });
    vitestModule.expect(updated.professionalName).toBe("Dra. Ana M. Garcia");
  });

  vitestModule.it("maps null professional_name in getTenantProfile", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/tenant/profile", () => {
        return mswModule.HttpResponse.json({
          tenant_id: "tenant-1",
          name: "Ana Garcia",
          professional_name: null
        });
      })
    );

    const tokenSession = new InMemoryTokenSession("access-1", "refresh-1");
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const profile = await adapter.getTenantProfile();
    vitestModule.expect(profile.professionalName).toBeNull();
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

  vitestModule.it("listEvalShapes maps snake_case to camelCase", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/eval/shapes", () => {
        return mswModule.HttpResponse.json({
          items: [
            {
              name: "shape_minimal",
              description: "Shape mínima para testear onboarding básico",
              required_combos: [["new_patient"]],
              rendered_system_prompt: "Eres un asistente de agenda..."
            }
          ]
        });
      })
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const shapes = await adapter.listEvalShapes();

    vitestModule.expect(shapes).toHaveLength(1);
    vitestModule.expect(shapes[0]?.name).toBe("shape_minimal");
    vitestModule.expect(shapes[0]?.requiredCombos).toEqual([["new_patient"]]);
    vitestModule.expect(shapes[0]?.renderedSystemPrompt).toBe("Eres un asistente de agenda...");
  });

  vitestModule.it("listEvalPersonas maps snake_case to camelCase", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/eval/personas", () => {
        return mswModule.HttpResponse.json({
          items: [
            {
              id: "carlos_local_basic",
              display_name: "Carlos Pérez",
              capabilities: ["new_patient", "asks_about_price"],
              profile_group: "psicologa"
            }
          ]
        });
      })
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const personas = await adapter.listEvalPersonas();

    vitestModule.expect(personas).toHaveLength(1);
    vitestModule.expect(personas[0]?.id).toBe("carlos_local_basic");
    vitestModule.expect(personas[0]?.displayName).toBe("Carlos Pérez");
    vitestModule.expect(personas[0]?.capabilities).toEqual(["new_patient", "asks_about_price"]);
    vitestModule.expect(personas[0]?.profileGroup).toBe("psicologa");
  });

  vitestModule.it("listEvalPromptVersions maps items correctly", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/eval/prompt-versions", () => {
        return mswModule.HttpResponse.json({
          items: [{ id: "current", label: "Versión actual", active: true }]
        });
      })
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const versions = await adapter.listEvalPromptVersions();

    vitestModule.expect(versions).toHaveLength(1);
    vitestModule.expect(versions[0]?.id).toBe("current");
    vitestModule.expect(versions[0]?.active).toBe(true);
  });

  vitestModule.it("listEvalRuns maps snake_case to camelCase with limit param", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/eval/runs", ({ request }) => {
        const url = new URL(request.url);
        vitestModule.expect(url.searchParams.get("limit")).toBe("10");
        return mswModule.HttpResponse.json({
          items: [
            {
              run_doc_id: "doc-abc",
              run_id: "abc123",
              shape_name: "shape_minimal",
              started_at: "2026-04-30T10:00:00Z",
              finished_at: "2026-04-30T10:05:00Z",
              total_personas: 1,
              ok: 1,
              fail: 0,
              skipped: false
            }
          ]
        });
      })
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const runs = await adapter.listEvalRuns(10);

    vitestModule.expect(runs).toHaveLength(1);
    vitestModule.expect(runs[0]?.runDocId).toBe("doc-abc");
    vitestModule.expect(runs[0]?.runId).toBe("abc123");
    vitestModule.expect(runs[0]?.shapeName).toBe("shape_minimal");
    vitestModule.expect(runs[0]?.totalPersonas).toBe(1);
    vitestModule.expect(runs[0]?.ok).toBe(1);
    vitestModule.expect(runs[0]?.fail).toBe(0);
  });

  vitestModule.it("getEvalRun maps detail with conversations and transcript", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/eval/runs/doc-abc", () => {
        return mswModule.HttpResponse.json({
          run_doc_id: "doc-abc",
          run_id: "abc123",
          shape_name: "shape_minimal",
          prompt_version_id: null,
          started_at: "2026-04-30T10:00:00Z",
          finished_at: "2026-04-30T10:05:00Z",
          total_personas: 1,
          ok: 1,
          fail: 0,
          skipped: false,
          conversations: [
            {
              persona_id: "carlos_local_basic",
              combos_satisfied: [["new_patient"]],
              status: "ok",
              elapsed_seconds: 12.4,
              conversation_id: "conv-xyz",
              scheduling_request_id: "sr-xyz",
              final_status: "SESSION_CLOSED",
              error: null,
              transcript: [
                {
                  direction: "INBOUND",
                  content: "Hola, quiero una cita",
                  timestamp: "2026-04-30T10:01:00Z"
                },
                {
                  direction: "OUTBOUND",
                  content: "Claro, con gusto",
                  timestamp: "2026-04-30T10:01:05Z"
                }
              ],
              judge_verdict: null
            }
          ]
        });
      })
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const detail = await adapter.getEvalRun("doc-abc");

    vitestModule.expect(detail.runDocId).toBe("doc-abc");
    vitestModule.expect(detail.promptVersionId).toBeNull();
    vitestModule.expect(detail.conversations).toHaveLength(1);
    const conv = detail.conversations[0];
    vitestModule.expect(conv?.personaId).toBe("carlos_local_basic");
    vitestModule.expect(conv?.combosSatisfied).toEqual([["new_patient"]]);
    vitestModule.expect(conv?.status).toBe("ok");
    vitestModule.expect(conv?.elapsedSeconds).toBe(12.4);
    vitestModule.expect(conv?.transcript).toHaveLength(2);
    vitestModule.expect(conv?.transcript[0]?.direction).toBe("INBOUND");
    vitestModule.expect(conv?.transcript[1]?.direction).toBe("OUTBOUND");
  });

  vitestModule.it("getEvalRun maps judge_verdict with verifications to camelCase", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/eval/runs/doc-judge", () => {
        return mswModule.HttpResponse.json({
          run_doc_id: "doc-judge",
          run_id: "judge123",
          shape_name: "shape_full",
          prompt_version_id: null,
          started_at: "2026-05-01T10:00:00Z",
          finished_at: "2026-05-01T10:10:00Z",
          total_personas: 1,
          ok: 1,
          fail: 0,
          skipped: false,
          conversations: [
            {
              persona_id: "carlos_local_basic",
              combos_satisfied: [["asks_about_price", "new_patient"]],
              status: "ok",
              elapsed_seconds: 15.2,
              conversation_id: "conv-judge",
              scheduling_request_id: null,
              final_status: "SESSION_CLOSED",
              error: null,
              transcript: [],
              judge_verdict: {
                declared_capabilities: ["asks_about_price", "new_patient"],
                verifications: [
                  {
                    capability: "asks_about_price",
                    verified: true,
                    evidence: "Hola Dra. Cuánto vale la consulta?",
                    reasoning: "El paciente pregunta el precio en el primer mensaje."
                  },
                  {
                    capability: "new_patient",
                    verified: true,
                    evidence: null,
                    reasoning: "No menciona haber sido paciente antes."
                  }
                ],
                overall: "all_verified",
                judge_model: "gemini-2.5-flash",
                judged_at: "2026-05-01T17:49:46Z",
                error: null
              }
            }
          ]
        });
      })
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const detail = await adapter.getEvalRun("doc-judge");
    const conv = detail.conversations[0];
    const verdict = conv?.judgeVerdict;

    vitestModule.expect(verdict).not.toBeNull();
    vitestModule.expect(verdict?.overall).toBe("all_verified");
    vitestModule.expect(verdict?.judgeModel).toBe("gemini-2.5-flash");
    vitestModule.expect(verdict?.judgedAt).toBe("2026-05-01T17:49:46Z");
    vitestModule.expect(verdict?.declaredCapabilities).toEqual(["asks_about_price", "new_patient"]);
    vitestModule.expect(verdict?.verifications).toHaveLength(2);
    vitestModule.expect(verdict?.verifications[0]?.capability).toBe("asks_about_price");
    vitestModule.expect(verdict?.verifications[0]?.verified).toBe(true);
    vitestModule
      .expect(verdict?.verifications[0]?.evidence)
      .toBe("Hola Dra. Cuánto vale la consulta?");
    vitestModule.expect(verdict?.verifications[1]?.evidence).toBeNull();
    vitestModule.expect(verdict?.error).toBeNull();
  });

  vitestModule.it("getEvalRun maps judge_verdict: null to judgeVerdict: null", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/eval/runs/doc-no-judge", () => {
        return mswModule.HttpResponse.json({
          run_doc_id: "doc-no-judge",
          run_id: "nojudge",
          shape_name: "shape_minimal",
          prompt_version_id: null,
          started_at: "2026-05-01T10:00:00Z",
          finished_at: null,
          total_personas: 1,
          ok: 0,
          fail: 1,
          skipped: false,
          conversations: [
            {
              persona_id: "persona-a",
              combos_satisfied: [],
              status: "fail",
              elapsed_seconds: null,
              conversation_id: null,
              scheduling_request_id: null,
              final_status: null,
              error: "timeout",
              transcript: [],
              judge_verdict: null
            }
          ]
        });
      })
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const detail = await adapter.getEvalRun("doc-no-judge");
    const conv = detail.conversations[0];

    vitestModule.expect(conv?.judgeVerdict).toBeNull();
  });

  vitestModule.it("getEvalRun maps judge_verdict with error and empty verifications", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/eval/runs/doc-judge-err", () => {
        return mswModule.HttpResponse.json({
          run_doc_id: "doc-judge-err",
          run_id: "judgerr",
          shape_name: "shape_full",
          prompt_version_id: null,
          started_at: "2026-05-01T10:00:00Z",
          finished_at: "2026-05-01T10:05:00Z",
          total_personas: 1,
          ok: 0,
          fail: 1,
          skipped: false,
          conversations: [
            {
              persona_id: "persona-b",
              combos_satisfied: [],
              status: "fail",
              elapsed_seconds: 5.0,
              conversation_id: "conv-err",
              scheduling_request_id: null,
              final_status: null,
              error: null,
              transcript: [],
              judge_verdict: {
                declared_capabilities: ["asks_about_price"],
                verifications: [],
                overall: "none",
                judge_model: "gemini-2.5-flash",
                judged_at: "2026-05-01T10:04:00Z",
                error: "parse_error: schema mismatch"
              }
            }
          ]
        });
      })
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const detail = await adapter.getEvalRun("doc-judge-err");
    const verdict = detail.conversations[0]?.judgeVerdict;

    vitestModule.expect(verdict).not.toBeNull();
    vitestModule.expect(verdict?.overall).toBe("none");
    vitestModule.expect(verdict?.verifications).toHaveLength(0);
    vitestModule.expect(verdict?.error).toBe("parse_error: schema mismatch");
  });

  vitestModule.it("maps phone_prefix round-trip for create and get patient", async () => {
    serverModule.server.use(
      mswModule.http.post("http://api.test/v1/patients", async ({ request }) => {
        const body = (await request.json()) as {
          phone_prefix: string | null;
          phone: string;
        };
        vitestModule.expect(body.phone_prefix).toBe("+57");
        vitestModule.expect(body.phone).toBe("3001112233");
        return mswModule.HttpResponse.json({
          tenant_id: "tenant-1",
          whatsapp_user_id: "573001112233",
          first_name: "Jane",
          last_name: "Doe",
          email: "jane@example.com",
          age: 29,
          location: "Bogota",
          phone_prefix: "+57",
          phone: "3001112233",
          created_at: "2026-03-01T10:00:00Z"
        });
      }),
      mswModule.http.get("http://api.test/v1/patients/wa-null-prefix", () => {
        return mswModule.HttpResponse.json({
          tenant_id: "tenant-1",
          whatsapp_user_id: "wa-null-prefix",
          first_name: "Legacy",
          last_name: "Patient",
          email: "legacy@example.com",
          age: 40,
          location: "Cali",
          phone_prefix: null,
          phone: "573009998888",
          created_at: "2025-01-01T00:00:00Z"
        });
      })
    );

    const tokenSession = new InMemoryTokenSession("access-1", "refresh-1");
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const created = await adapter.createPatient({
      whatsappUserId: "573001112233",
      firstName: "Jane",
      lastName: "Doe",
      email: "jane@example.com",
      age: 29,
      location: "Bogota",
      phonePrefix: "+57",
      phone: "3001112233"
    });
    vitestModule.expect(created.phonePrefix).toBe("+57");
    vitestModule.expect(created.phone).toBe("3001112233");

    const legacy = await adapter.getPatient("wa-null-prefix");
    vitestModule.expect(legacy.phonePrefix).toBeNull();
    vitestModule.expect(legacy.phone).toBe("573009998888");
  });

  vitestModule.it("deleteEvalRun sends JWT and maps response (no admin secret)", async () => {
    serverModule.server.use(
      mswModule.http.delete("http://api.test/v1/dev/eval-runs/run-to-delete", ({ request }) => {
        // El borrado de runs ya no requiere EVAL_ADMIN_SECRET — usa JWT
        // del tenant logueado. Solo /v1/dev/eval-tenants requiere el secret.
        const adminSecret = request.headers.get("x-eval-admin-secret");
        vitestModule.expect(adminSecret).toBeNull();
        const authHeader = request.headers.get("authorization");
        vitestModule.expect(authHeader).toBe("Bearer test-access-token");
        return mswModule.HttpResponse.json({
          eval_runs_deleted: 3,
          tenants_deleted: 2
        });
      })
    );

    const tokenSession = new InMemoryTokenSession("test-access-token", null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const result = await adapter.deleteEvalRun("run-to-delete");

    vitestModule.expect(result.evalRunsDeleted).toBe(3);
    vitestModule.expect(result.tenantsDeleted).toBe(2);
  });

  vitestModule.it("listEvalCapabilities maps snake_case to camelCase and category", async () => {
    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/eval/capabilities", () => {
        return mswModule.HttpResponse.json({
          items: [
            {
              id: "returning_patient",
              description: "El paciente ya ha tenido citas anteriores.",
              implications: "EL RUNNER pre-seed una cita pasada antes de iniciar la conversacion.",
              category: "cohort"
            },
            {
              id: "local_patient",
              description: "El paciente esta en la misma ciudad que el profesional.",
              implications: "No requiere configuracion adicional.",
              category: "location"
            }
          ]
        });
      })
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const caps = await adapter.listEvalCapabilities();

    vitestModule.expect(caps).toHaveLength(2);
    vitestModule.expect(caps[0]?.id).toBe("returning_patient");
    vitestModule.expect(caps[0]?.category).toBe("cohort");
    vitestModule.expect(caps[0]?.implications).toContain("EL RUNNER");
    vitestModule.expect(caps[1]?.id).toBe("local_patient");
    vitestModule.expect(caps[1]?.category).toBe("location");
  });
});

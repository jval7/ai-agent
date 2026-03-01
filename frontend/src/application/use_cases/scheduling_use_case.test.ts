import * as vitestModule from "vitest";

import type * as backendApiPort from "@ports/backend_api_port";

import * as schedulingUseCaseModule from "./scheduling_use_case";

vitestModule.describe("SchedulingUseCase", () => {
  vitestModule.it("delegates scheduling operations to api port", async () => {
    const apiMock = {
      listSchedulingRequests: vitestModule.vi.fn(async () => [
        {
          requestId: "req-1",
          conversationId: "conv-1",
          whatsappUserId: "wa-1",
          requestKind: "INITIAL",
          status: "AWAITING_PROFESSIONAL_SLOTS",
          roundNumber: 1,
          patientPreferenceNote: "prefiere tarde",
          rejectionSummary: null,
          professionalNote: null,
          selectedSlotId: null,
          calendarEventId: null,
          createdAt: "2026-03-01T10:00:00Z",
          updatedAt: "2026-03-01T10:00:00Z",
          slots: []
        }
      ]),
      listConversationSchedulingRequests: vitestModule.vi.fn(async () => []),
      getGoogleCalendarAvailability: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        calendarId: "primary",
        timezone: "America/Bogota",
        busyIntervals: []
      })),
      submitProfessionalSlots: vitestModule.vi.fn(async () => ({
        status: "AWAITING_PATIENT_CHOICE",
        slotBatchId: "req-1",
        outboundMessageId: "wamid-1",
        assistantText: "Listo"
      }))
    } as Partial<backendApiPort.BackendApiPort> as backendApiPort.BackendApiPort;

    const useCase = new schedulingUseCaseModule.SchedulingUseCase(apiMock);
    const requests = await useCase.listRequests("AWAITING_PROFESSIONAL_SLOTS");
    const conversationRequests = await useCase.listRequestsByConversation("conv-1");
    const availability = await useCase.getAvailability(
      "2026-03-01T00:00:00Z",
      "2026-03-31T23:59:59Z"
    );
    const submitResult = await useCase.submitProfessionalSlots("conv-1", "req-1", {
      slots: [
        {
          slotId: "req-1_20260301_1000",
          startAt: "2026-03-01T10:00:00Z",
          endAt: "2026-03-01T11:00:00Z",
          timezone: "America/Bogota"
        }
      ],
      professionalNote: "nota"
    });

    vitestModule.expect(requests[0]?.requestId).toBe("req-1");
    vitestModule.expect(conversationRequests).toEqual([]);
    vitestModule.expect(availability.timezone).toBe("America/Bogota");
    vitestModule.expect(submitResult.status).toBe("AWAITING_PATIENT_CHOICE");
  });
});

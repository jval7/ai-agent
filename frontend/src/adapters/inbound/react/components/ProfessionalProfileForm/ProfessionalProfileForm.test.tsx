import * as mswModule from "msw";
import * as reactQueryModule from "@tanstack/react-query";
import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as serverModule from "@shared/testing/msw/server";
import type * as agentModel from "@domain/models/agent";
import type * as containerModule from "@infrastructure/di/container";
import type * as agentUseCaseModule from "@application/use_cases/agent_use_case";
import * as professionalProfileFormModule from "./ProfessionalProfileForm";

// --- Minimal fake backend adapter ---

const EMPTY_PROFILE: agentModel.ProfessionalProfile = {
  tenantId: "test-tenant",
  identity: null,
  professionalContext: null,
  services: [],
  presencialSchedule: [],
  virtualSchedule: [],
  paymentMethods: []
};

const FULL_PROFILE: agentModel.ProfessionalProfile = {
  tenantId: "test-tenant",
  identity: {
    assistantName: "Claudia",
    professionalTitle: "Psicóloga",
    professionalAddressTerm: "la Doc",
    mainCity: "Cali",
    tone: "Profesional y cálida.",
    languages: ["español"]
  },
  professionalContext: {
    approach: "Enfoque humanista.",
    commonTopics: ["ansiedad", "duelo"],
    servicesNotOffered: ["terapia de pareja"],
    coverageNotes: null
  },
  services: [
    {
      name: "Consulta Individual",
      description: null,
      modalities: ["PRESENCIAL", "VIRTUAL"],
      tariffs: [
        {
          label: "Sesión",
          description: null,
          prices: [{ currency: "COP", amount: 130000 }]
        }
      ]
    }
  ],
  presencialSchedule: [
    { weekdayFrom: "WED", weekdayTo: "FRI", startTime: "08:00", endTime: "16:00" }
  ],
  virtualSchedule: [],
  paymentMethods: [
    {
      currency: "COP",
      methodName: "Nequi",
      holder: "Alejandra Escobar",
      instructions: "318 732 6409",
      appliesWhen: "Colombia"
    }
  ]
};

interface FakeResources {
  container: containerModule.AppContainer;
  updateSpy: ReturnType<typeof vitestModule.vi.fn>;
}

function createFakeResources(profile: agentModel.ProfessionalProfile): FakeResources {
  const updateSpy = vitestModule.vi.fn().mockResolvedValue(profile);
  const container: containerModule.AppContainer = {
    agentUseCase: {
      getProfessionalProfile: vitestModule.vi.fn().mockResolvedValue(profile),
      updateProfessionalProfile: updateSpy,
      getSystemPrompt: vitestModule.vi.fn().mockRejectedValue(new Error("not used")),
      updateSystemPrompt: vitestModule.vi.fn().mockRejectedValue(new Error("not used")),
      getAgentSettings: vitestModule.vi.fn().mockRejectedValue(new Error("not used")),
      updateAgentSettings: vitestModule.vi.fn().mockRejectedValue(new Error("not used")),
      getDevFeatures: vitestModule.vi.fn().mockRejectedValue(new Error("not used")),
      updateSandboxMode: vitestModule.vi.fn().mockRejectedValue(new Error("not used"))
    } as unknown as agentUseCaseModule.AgentUseCase
  } as unknown as containerModule.AppContainer;
  return { container, updateSpy };
}

function renderForm(profile: agentModel.ProfessionalProfile) {
  const { container, updateSpy } = createFakeResources(profile);
  const queryClient = new reactQueryModule.QueryClient({
    defaultOptions: { queries: { retry: false } }
  });

  const result = testingLibraryReactModule.render(
    <reactQueryModule.QueryClientProvider client={queryClient}>
      <appContainerContextModule.AppContainerProvider container={container}>
        <professionalProfileFormModule.ProfessionalProfileForm />
      </appContainerContextModule.AppContainerProvider>
    </reactQueryModule.QueryClientProvider>
  );
  return { ...result, container, queryClient, updateSpy };
}

async function expandCard(title: RegExp): Promise<void> {
  const toggle = await testingLibraryReactModule.screen.findByRole("button", { name: title });
  await testingLibraryReactModule.act(async () => {
    testingLibraryReactModule.fireEvent.click(toggle);
  });
}

vitestModule.describe("ProfessionalProfileForm", () => {
  vitestModule.beforeEach(() => {
    // Reset persisted collapse state so each test starts with cards collapsed.
    window.localStorage.clear();
    serverModule.server.use(
      mswModule.http.get("*/v1/agent/professional-profile", () => {
        return mswModule.HttpResponse.json(EMPTY_PROFILE);
      })
    );
  });

  vitestModule.afterEach(() => {
    testingLibraryReactModule.cleanup();
  });

  vitestModule.it("renders section cards without crashing (empty profile)", async () => {
    renderForm(EMPTY_PROFILE);
    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText("Identidad del asistente"))
        .toBeTruthy();
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText("Servicios y práctica"))
        .toBeTruthy();
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText("Medios de pago"))
        .toBeTruthy();
    });
  });

  vitestModule.it("renders pre-filled data from full profile", async () => {
    renderForm(FULL_PROFILE);
    // Wait until the form has loaded the profile (sub-cards are present in collapsed state).
    await testingLibraryReactModule.screen.findByRole("button", {
      name: /Identidad del asistente/i
    });

    // Cards default to collapsed; expand the ones whose data we want to assert on.
    await expandCard(/Identidad del asistente/i);
    await expandCard(/Servicios y práctica/i);
    await expandCard(/Medios de pago/i);

    // Now expand the inner item cards (services and payment methods are also
    // collapsible cards in the new UX; the inner button label is the item
    // summary text).
    await expandCard(/Consulta Individual/i);
    await expandCard(/Nequi/i);

    await testingLibraryReactModule.waitFor(() => {
      const assistantNameInput = testingLibraryReactModule.screen.getByDisplayValue("Claudia");
      vitestModule.expect(assistantNameInput).toBeTruthy();
      vitestModule.expect(testingLibraryReactModule.screen.getByText("español")).toBeTruthy();
      vitestModule
        .expect(testingLibraryReactModule.screen.getByDisplayValue("Consulta Individual"))
        .toBeTruthy();
      vitestModule.expect(testingLibraryReactModule.screen.getByDisplayValue("Nequi")).toBeTruthy();
    });
  });

  vitestModule.it("Guardar button is disabled when form is not dirty", async () => {
    renderForm(EMPTY_PROFILE);
    await testingLibraryReactModule.waitFor(() => {
      const saveButton = testingLibraryReactModule.screen.getByRole("button", {
        name: "Guardar"
      });
      vitestModule.expect(saveButton).toBeDisabled();
    });
  });

  vitestModule.it("Guardar button enables after user edits a field", async () => {
    renderForm(EMPTY_PROFILE);

    // Cards start collapsed; expand "Identidad del asistente" to access the input.
    await expandCard(/Identidad del asistente/i);

    // Wait for the form to fully load (input is present and not disabled)
    await testingLibraryReactModule.waitFor(() => {
      const input = testingLibraryReactModule.screen.getByPlaceholderText("Ej. Claudia");
      vitestModule.expect(input).not.toBeDisabled();
    });

    // Fire the change
    const assistantNameInput = testingLibraryReactModule.screen.getByPlaceholderText("Ej. Claudia");
    await testingLibraryReactModule.act(async () => {
      testingLibraryReactModule.fireEvent.change(assistantNameInput, {
        target: { value: "Nuevo nombre" }
      });
    });

    // Button should now be enabled
    await testingLibraryReactModule.waitFor(() => {
      const saveButton = testingLibraryReactModule.screen.getByRole("button", {
        name: "Guardar"
      });
      vitestModule.expect(saveButton).not.toBeDisabled();
    });
  });

  vitestModule.it("calls updateProfessionalProfile when Guardar is clicked", async () => {
    const { updateSpy } = renderForm(EMPTY_PROFILE);

    // Expand identity card to reach the input.
    await expandCard(/Identidad del asistente/i);

    // Wait for the form to fully load
    await testingLibraryReactModule.waitFor(() => {
      const input = testingLibraryReactModule.screen.getByPlaceholderText("Ej. Claudia");
      vitestModule.expect(input).not.toBeDisabled();
    });

    // Make form dirty
    const assistantNameInput = testingLibraryReactModule.screen.getByPlaceholderText("Ej. Claudia");
    await testingLibraryReactModule.act(async () => {
      testingLibraryReactModule.fireEvent.change(assistantNameInput, {
        target: { value: "Nuevo asistente" }
      });
    });

    // Wait for button to become enabled
    await testingLibraryReactModule.waitFor(() => {
      const btn = testingLibraryReactModule.screen.getByRole("button", { name: "Guardar" });
      vitestModule.expect(btn).not.toBeDisabled();
    });

    // Click save
    await testingLibraryReactModule.act(async () => {
      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getByRole("button", { name: "Guardar" })
      );
    });

    await testingLibraryReactModule.waitFor(() => {
      vitestModule.expect(updateSpy).toHaveBeenCalledTimes(1);
    });
  });
});

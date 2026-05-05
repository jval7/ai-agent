import * as reactQueryModule from "@tanstack/react-query";
import * as testingLibraryReactModule from "@testing-library/react";
import * as reactRouterDomModule from "react-router-dom";
import * as vitestModule from "vitest";

import type * as containerModule from "@infrastructure/di/container";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as apiErrorModule from "@shared/http/api_error";

import * as adminHomePageModule from "./AdminHomePage";

const fakeMetrics = {
  tenantsCount: 5,
  tenantsActive: 4,
  totalPatients: 120,
  totalConversations: 800,
  activeConversationsToday: 15,
  totalReminders: 60,
  pendingReminders: 10,
  totalRevenueCopThisMonth: 500000,
  controlModeDistribution: { ai: 70, human: 30 },
  topTenantsByConversations: []
};

const fakeTenant = {
  tenantId: "t-1",
  tenantName: "Consultorio Dr. García",
  professionalName: "Dr. García",
  patientCount: 20,
  conversationCount: 100,
  activeConversationsToday: 3,
  manualAppointmentCountUpcoming: 5,
  pendingReminderCount: 2,
  totalRevenueCopThisMonth: 100000,
  lastActivityAt: "2026-05-01T10:00:00Z",
  ownerEmail: "garcia@example.com",
  ownerIsActive: true
};

function buildContainer(overrides: Record<string, unknown> = {}): containerModule.AppContainer {
  return {
    api: {
      adminGetGlobalMetrics: vitestModule.vi.fn(async () => fakeMetrics),
      adminListTenants: vitestModule.vi.fn(async () => [fakeTenant]),
      ...overrides
    }
  } as unknown as containerModule.AppContainer;
}

function renderPage(container: containerModule.AppContainer) {
  const queryClient = new reactQueryModule.QueryClient({
    defaultOptions: { queries: { retry: false } }
  });

  return testingLibraryReactModule.render(
    <reactQueryModule.QueryClientProvider client={queryClient}>
      <appContainerContextModule.AppContainerProvider container={container}>
        <reactRouterDomModule.MemoryRouter initialEntries={["/admin"]}>
          <reactRouterDomModule.Routes>
            <reactRouterDomModule.Route
              element={<adminHomePageModule.AdminHomePage />}
              path="/admin"
            />
          </reactRouterDomModule.Routes>
        </reactRouterDomModule.MemoryRouter>
      </appContainerContextModule.AppContainerProvider>
    </reactQueryModule.QueryClientProvider>
  );
}

vitestModule.describe("AdminHomePage", () => {
  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
  });

  vitestModule.it("renders KPI cards and tenant row after data loads", async () => {
    const container = buildContainer();
    renderPage(container);

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Total Tenants")).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.getByText("Dr. García")).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.getByText("garcia@example.com")).toBeInTheDocument();
    });
  });

  vitestModule.it("shows error banner when metrics query fails", async () => {
    const container = buildContainer({
      adminGetGlobalMetrics: vitestModule.vi.fn(async () => {
        throw new apiErrorModule.ApiError(500, "Error del servidor");
      })
    });
    renderPage(container);

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Error del servidor")).toBeInTheDocument();
    });
  });
});

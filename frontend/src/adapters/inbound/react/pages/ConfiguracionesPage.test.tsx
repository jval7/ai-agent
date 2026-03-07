import * as reactQueryModule from "@tanstack/react-query";
import * as testingLibraryReactModule from "@testing-library/react";
import * as reactRouterDomModule from "react-router-dom";
import * as vitestModule from "vitest";

import type * as containerModule from "@infrastructure/di/container";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";

import * as configuracionesPageModule from "./ConfiguracionesPage";

function renderConfiguracionesPage(container: unknown, path = "/configuraciones") {
  const queryClient = new reactQueryModule.QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });

  return testingLibraryReactModule.render(
    <reactQueryModule.QueryClientProvider client={queryClient}>
      <appContainerContextModule.AppContainerProvider
        container={container as containerModule.AppContainer}
      >
        <reactRouterDomModule.MemoryRouter initialEntries={[path]}>
          <reactRouterDomModule.Routes>
            <reactRouterDomModule.Route
              element={<configuracionesPageModule.ConfiguracionesPage />}
              path="/configuraciones"
            />
          </reactRouterDomModule.Routes>
        </reactRouterDomModule.MemoryRouter>
      </appContainerContextModule.AppContainerProvider>
    </reactQueryModule.QueryClientProvider>
  );
}

function buildContainer() {
  return {
    onboardingUseCase: {
      getWhatsappConnectionStatus: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        status: "CONNECTED",
        phoneNumberId: "phone-1",
        businessAccountId: "business-1"
      })),
      getGoogleCalendarConnectionStatus: vitestModule.vi.fn(async () => ({
        tenantId: "tenant-1",
        status: "DISCONNECTED",
        calendarId: null,
        professionalTimezone: null,
        connectedAt: null
      })),
      getOnboardingStatus: vitestModule.vi.fn(async () => ({
        whatsappConnected: true,
        googleCalendarConnected: false,
        ready: false
      })),
      createWhatsappSession: vitestModule.vi.fn(async () => ({
        state: "meta-state",
        connectUrl: "https://meta.test/oauth"
      })),
      createGoogleSession: vitestModule.vi.fn(async () => ({
        state: "google-state",
        connectUrl: "https://google.test/oauth"
      }))
    },
    agentUseCase: {
      getSystemPrompt: vitestModule.vi.fn(async () => ({
        systemPrompt: "You are a helpful assistant"
      })),
      updateSystemPrompt: vitestModule.vi.fn(async () => undefined),
      getAgentSettings: vitestModule.vi.fn(async () => ({
        messageDebounceDelaySeconds: 5
      })),
      updateAgentSettings: vitestModule.vi.fn(async () => undefined)
    }
  };
}

vitestModule.describe("ConfiguracionesPage", () => {
  vitestModule.beforeEach(() => {
    vitestModule.vi.spyOn(appShellModule, "AppShell").mockImplementation((props) => {
      return <div>{props.children}</div>;
    });
  });

  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
    vitestModule.vi.unstubAllGlobals();
  });

  vitestModule.it("redirects to google connect URL when connect button is clicked", async () => {
    const assignSpy = vitestModule.vi.fn();
    vitestModule.vi.stubGlobal("location", {
      assign: assignSpy
    });
    const container = buildContainer();

    renderConfiguracionesPage(container);

    const googleButton = await testingLibraryReactModule.screen.findByRole("button", {
      name: "Conectar Google Calendar"
    });
    testingLibraryReactModule.fireEvent.click(googleButton);

    await testingLibraryReactModule.waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith("https://google.test/oauth");
    });
  });

  vitestModule.it("shows oauth callback error banner from query params", async () => {
    const container = buildContainer();

    renderConfiguracionesPage(
      container,
      "/configuraciones?google_oauth=error&status=502&reason=boom"
    );

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByText(/Error en callback OAuth/)
      ).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.getByText(/status=502/)).toBeInTheDocument();
    });
  });
});

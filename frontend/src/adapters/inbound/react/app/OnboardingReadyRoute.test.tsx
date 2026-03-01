import * as reactQueryModule from "@tanstack/react-query";
import * as testingLibraryReactModule from "@testing-library/react";
import * as reactRouterDomModule from "react-router-dom";
import * as vitestModule from "vitest";

import type * as containerModule from "@infrastructure/di/container";

import * as appContainerContextModule from "./AppContainerContext";
import * as onboardingReadyRouteModule from "./OnboardingReadyRoute";

function renderWithContainer(container: unknown, initialPath: string) {
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
        <reactRouterDomModule.MemoryRouter initialEntries={[initialPath]}>
          <reactRouterDomModule.Routes>
            <reactRouterDomModule.Route
              element={
                <onboardingReadyRouteModule.OnboardingReadyRoute>
                  <div>Inbox habilitado</div>
                </onboardingReadyRouteModule.OnboardingReadyRoute>
              }
              path="/inbox"
            />
            <reactRouterDomModule.Route
              element={<div>Onboarding requerido</div>}
              path="/onboarding"
            />
          </reactRouterDomModule.Routes>
        </reactRouterDomModule.MemoryRouter>
      </appContainerContextModule.AppContainerProvider>
    </reactQueryModule.QueryClientProvider>
  );
}

vitestModule.describe("OnboardingReadyRoute", () => {
  vitestModule.it("redirects to onboarding when ready=false", async () => {
    const container = {
      onboardingUseCase: {
        getOnboardingStatus: vitestModule.vi.fn(async () => ({
          whatsappConnected: true,
          googleCalendarConnected: false,
          ready: false
        }))
      }
    };

    renderWithContainer(container, "/inbox");

    await testingLibraryReactModule.waitFor(() => {
      expect(
        testingLibraryReactModule.screen.getByText("Onboarding requerido")
      ).toBeInTheDocument();
    });
  });

  vitestModule.it("renders children when ready=true", async () => {
    const container = {
      onboardingUseCase: {
        getOnboardingStatus: vitestModule.vi.fn(async () => ({
          whatsappConnected: true,
          googleCalendarConnected: true,
          ready: true
        }))
      }
    };

    renderWithContainer(container, "/inbox");

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Inbox habilitado")).toBeInTheDocument();
    });
  });
});

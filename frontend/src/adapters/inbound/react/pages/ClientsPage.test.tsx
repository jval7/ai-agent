import * as reactQueryModule from "@tanstack/react-query";
import * as testingLibraryReactModule from "@testing-library/react";
import * as reactRouterDomModule from "react-router-dom";
import * as vitestModule from "vitest";

import type * as containerModule from "@infrastructure/di/container";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";

import * as clientsPageModule from "./ClientsPage";

function renderClientsPage(container: unknown) {
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
        <reactRouterDomModule.MemoryRouter initialEntries={["/clientes"]}>
          <reactRouterDomModule.Routes>
            <reactRouterDomModule.Route
              element={<clientsPageModule.ClientsPage />}
              path="/clientes"
            />
          </reactRouterDomModule.Routes>
        </reactRouterDomModule.MemoryRouter>
      </appContainerContextModule.AppContainerProvider>
    </reactQueryModule.QueryClientProvider>
  );
}

vitestModule.describe("ClientsPage", () => {
  vitestModule.beforeEach(() => {
    vitestModule.vi.spyOn(appShellModule, "AppShell").mockImplementation((props) => {
      return <div>{props.children}</div>;
    });
  });

  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
  });

  vitestModule.it("renders patient list and detail panel", async () => {
    const getPatientMock = vitestModule.vi.fn(async (whatsappUserId: string) => {
      if (whatsappUserId === "wa-2") {
        return {
          tenantId: "tenant-1",
          whatsappUserId: "wa-2",
          firstName: "John",
          lastName: "Smith",
          email: "john@example.com",
          age: 34,
          consultationReason: "Insomnio",
          location: "Medellin",
          phone: "573001445566",
          createdAt: "2026-03-02T10:00:00Z"
        };
      }
      return {
        tenantId: "tenant-1",
        whatsappUserId: "wa-1",
        firstName: "Jane",
        lastName: "Doe",
        email: "jane@example.com",
        age: 29,
        consultationReason: "Ansiedad",
        location: "Bogota",
        phone: "573001112233",
        createdAt: "2026-03-01T10:00:00Z"
      };
    });
    const container = {
      patientUseCase: {
        listPatients: vitestModule.vi.fn(async () => [
          {
            tenantId: "tenant-1",
            whatsappUserId: "wa-1",
            firstName: "Jane",
            lastName: "Doe",
            email: "jane@example.com",
            age: 29,
            consultationReason: "Ansiedad",
            location: "Bogota",
            phone: "573001112233",
            createdAt: "2026-03-01T10:00:00Z"
          },
          {
            tenantId: "tenant-1",
            whatsappUserId: "wa-2",
            firstName: "John",
            lastName: "Smith",
            email: "john@example.com",
            age: 34,
            consultationReason: "Insomnio",
            location: "Medellin",
            phone: "573001445566",
            createdAt: "2026-03-02T10:00:00Z"
          }
        ]),
        getPatient: getPatientMock
      }
    };

    renderClientsPage(container);

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Jane Doe")).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.getByText("John Smith")).toBeInTheDocument();
    });

    const johnButton = testingLibraryReactModule.screen.getByRole("button", {
      name: /John Smith/
    });
    testingLibraryReactModule.fireEvent.click(johnButton);

    await testingLibraryReactModule.waitFor(() => {
      expect(testingLibraryReactModule.screen.getByText("Insomnio")).toBeInTheDocument();
      expect(testingLibraryReactModule.screen.getByText("Medellin")).toBeInTheDocument();
    });
    expect(getPatientMock).toHaveBeenCalledWith("wa-2");
  });
});

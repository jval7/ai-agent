import * as reactRouterDomModule from "react-router-dom";
import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import * as authContextModule from "@adapters/inbound/react/app/AuthContext";

import * as acceptInvitePageModule from "./AcceptInvitePage";

function renderAcceptInvitePage(path = "/accept-invite?token=abc123") {
  return testingLibraryReactModule.render(
    <reactRouterDomModule.MemoryRouter initialEntries={[path]}>
      <reactRouterDomModule.Routes>
        <reactRouterDomModule.Route
          element={<acceptInvitePageModule.AcceptInvitePage />}
          path="/accept-invite"
        />
        <reactRouterDomModule.Route
          element={<div data-testid="configuraciones-page">Configuraciones</div>}
          path="/configuraciones"
        />
      </reactRouterDomModule.Routes>
    </reactRouterDomModule.MemoryRouter>
  );
}

function buildAuthContext(
  overrides: Partial<authContextModule.AuthContextValue> = {}
): authContextModule.AuthContextValue {
  return {
    status: "anonymous",
    userProfile: null,
    login: vitestModule.vi.fn(async () => undefined),
    logout: vitestModule.vi.fn(async () => undefined),
    acceptInvitation: vitestModule.vi.fn(async () => undefined),
    requestPasswordReset: vitestModule.vi.fn(async () => undefined),
    confirmPasswordReset: vitestModule.vi.fn(async () => undefined),
    ...overrides
  };
}

vitestModule.describe("AcceptInvitePage", () => {
  vitestModule.beforeEach(() => {
    vitestModule.vi.spyOn(authContextModule, "useAuth").mockReturnValue(buildAuthContext());
  });

  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
  });

  vitestModule.it("renders form when token is present in URL", () => {
    renderAcceptInvitePage("/accept-invite?token=abc123");

    vitestModule
      .expect(testingLibraryReactModule.screen.getByLabelText("Nueva contraseña"))
      .toBeInTheDocument();
    vitestModule
      .expect(testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña"))
      .toBeInTheDocument();
    vitestModule
      .expect(testingLibraryReactModule.screen.getByRole("button", { name: "Crear cuenta" }))
      .toBeInTheDocument();
  });

  vitestModule.it("renders error and no form when token is absent", () => {
    renderAcceptInvitePage("/accept-invite");

    vitestModule
      .expect(testingLibraryReactModule.screen.getByText("Link inválido o expirado"))
      .toBeInTheDocument();
    vitestModule
      .expect(testingLibraryReactModule.screen.queryByLabelText("Nueva contraseña"))
      .toBeNull();
    vitestModule
      .expect(testingLibraryReactModule.screen.queryByLabelText("Confirmar contraseña"))
      .toBeNull();
  });

  vitestModule.it("shows error when passwords do not match", async () => {
    renderAcceptInvitePage("/accept-invite?token=abc123");

    const newPasswordInput = testingLibraryReactModule.screen.getByLabelText("Nueva contraseña");
    const confirmPasswordInput =
      testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña");
    const submitButton = testingLibraryReactModule.screen.getByRole("button", {
      name: "Crear cuenta"
    });

    testingLibraryReactModule.fireEvent.change(newPasswordInput, {
      target: { value: "password123" }
    });
    testingLibraryReactModule.fireEvent.change(confirmPasswordInput, {
      target: { value: "different456" }
    });
    testingLibraryReactModule.fireEvent.click(submitButton);

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText("Las contraseñas no coinciden"))
        .toBeInTheDocument();
    });
  });

  vitestModule.it("does not call acceptInvitation when passwords do not match", async () => {
    const acceptInvitationMock = vitestModule.vi.fn(async () => undefined);
    vitestModule.vi
      .spyOn(authContextModule, "useAuth")
      .mockReturnValue(buildAuthContext({ acceptInvitation: acceptInvitationMock }));

    renderAcceptInvitePage("/accept-invite?token=abc123");

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Nueva contraseña"),
      { target: { value: "password123" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña"),
      { target: { value: "different456" } }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Crear cuenta" })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule.expect(acceptInvitationMock).not.toHaveBeenCalled();
    });
  });

  vitestModule.it("calls acceptInvitation with token and password on submit", async () => {
    const acceptInvitationMock = vitestModule.vi.fn(async () => undefined);
    vitestModule.vi
      .spyOn(authContextModule, "useAuth")
      .mockReturnValue(buildAuthContext({ acceptInvitation: acceptInvitationMock }));

    renderAcceptInvitePage("/accept-invite?token=abc123");

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Nueva contraseña"),
      { target: { value: "secretpass" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña"),
      { target: { value: "secretpass" } }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Crear cuenta" })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule.expect(acceptInvitationMock).toHaveBeenCalledWith({
        token: "abc123",
        password: "secretpass"
      });
    });
  });

  vitestModule.it("navigates to /configuraciones after successful submission", async () => {
    const acceptInvitationMock = vitestModule.vi.fn(async () => undefined);
    vitestModule.vi
      .spyOn(authContextModule, "useAuth")
      .mockReturnValue(buildAuthContext({ acceptInvitation: acceptInvitationMock }));

    renderAcceptInvitePage("/accept-invite?token=abc123");

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Nueva contraseña"),
      { target: { value: "secretpass" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña"),
      { target: { value: "secretpass" } }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Crear cuenta" })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByTestId("configuraciones-page"))
        .toBeInTheDocument();
    });
  });

  vitestModule.it("shows API error message on failure", async () => {
    // Construct an ApiError so that resolveUiErrorMessage returns a message.
    const { ApiError } = await import("@shared/http/api_error");
    const structuredApiError = new ApiError(400, "Token inválido o ya utilizado", "req-1");
    const acceptInvitationWithApiError = vitestModule.vi.fn(async () => {
      throw structuredApiError;
    });

    vitestModule.vi
      .spyOn(authContextModule, "useAuth")
      .mockReturnValue(buildAuthContext({ acceptInvitation: acceptInvitationWithApiError }));

    renderAcceptInvitePage("/accept-invite?token=abc123");

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Nueva contraseña"),
      { target: { value: "secretpass" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña"),
      { target: { value: "secretpass" } }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Crear cuenta" })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText(/Token inválido o ya utilizado/))
        .toBeInTheDocument();
    });
  });
});

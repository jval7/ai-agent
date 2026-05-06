import * as reactRouterDomModule from "react-router-dom";
import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import * as authContextModule from "@adapters/inbound/react/app/AuthContext";

import * as resetPasswordPageModule from "./ResetPasswordPage";

function LoginRouteProbe() {
  const location = reactRouterDomModule.useLocation();
  return (
    <div data-testid="login-page" data-search={location.search}>
      Login
    </div>
  );
}

function renderResetPasswordPage(path = "/reset-password?token=abc123") {
  return testingLibraryReactModule.render(
    <reactRouterDomModule.MemoryRouter initialEntries={[path]}>
      <reactRouterDomModule.Routes>
        <reactRouterDomModule.Route
          element={<resetPasswordPageModule.ResetPasswordPage />}
          path="/reset-password"
        />
        <reactRouterDomModule.Route element={<LoginRouteProbe />} path="/login" />
        <reactRouterDomModule.Route
          element={<div data-testid="forgot-page">Forgot</div>}
          path="/forgot-password"
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

vitestModule.describe("ResetPasswordPage", () => {
  vitestModule.beforeEach(() => {
    vitestModule.vi.spyOn(authContextModule, "useAuth").mockReturnValue(buildAuthContext());
  });

  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
  });

  vitestModule.it("renders form when token is present", () => {
    renderResetPasswordPage("/reset-password?token=abc123");

    vitestModule
      .expect(testingLibraryReactModule.screen.getByLabelText("Nueva contraseña"))
      .toBeInTheDocument();
    vitestModule
      .expect(testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña"))
      .toBeInTheDocument();
    vitestModule
      .expect(testingLibraryReactModule.screen.getByRole("button", { name: "Guardar contraseña" }))
      .toBeInTheDocument();
  });

  vitestModule.it("renders error and no form when token is absent", () => {
    renderResetPasswordPage("/reset-password");

    vitestModule
      .expect(testingLibraryReactModule.screen.getByText("Link inválido o expirado"))
      .toBeInTheDocument();
    vitestModule
      .expect(testingLibraryReactModule.screen.queryByLabelText("Nueva contraseña"))
      .toBeNull();
  });

  vitestModule.it("shows error when passwords do not match", async () => {
    renderResetPasswordPage();

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Nueva contraseña"),
      { target: { value: "password123" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña"),
      { target: { value: "different456" } }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Guardar contraseña" })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText("Las contraseñas no coinciden"))
        .toBeInTheDocument();
    });
  });

  vitestModule.it("calls confirmPasswordReset with token and password on submit", async () => {
    const confirmPasswordResetMock = vitestModule.vi.fn(async () => undefined);
    vitestModule.vi
      .spyOn(authContextModule, "useAuth")
      .mockReturnValue(buildAuthContext({ confirmPasswordReset: confirmPasswordResetMock }));

    renderResetPasswordPage();

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Nueva contraseña"),
      { target: { value: "secretpass" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña"),
      { target: { value: "secretpass" } }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Guardar contraseña" })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule.expect(confirmPasswordResetMock).toHaveBeenCalledWith({
        token: "abc123",
        password: "secretpass"
      });
    });
  });

  vitestModule.it(
    "navigates to /login with reset=success after successful submission",
    async () => {
      const confirmPasswordResetMock = vitestModule.vi.fn(async () => undefined);
      vitestModule.vi
        .spyOn(authContextModule, "useAuth")
        .mockReturnValue(buildAuthContext({ confirmPasswordReset: confirmPasswordResetMock }));

      renderResetPasswordPage();

      testingLibraryReactModule.fireEvent.change(
        testingLibraryReactModule.screen.getByLabelText("Nueva contraseña"),
        { target: { value: "secretpass" } }
      );
      testingLibraryReactModule.fireEvent.change(
        testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña"),
        { target: { value: "secretpass" } }
      );
      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getByRole("button", { name: "Guardar contraseña" })
      );

      await testingLibraryReactModule.waitFor(() => {
        const loginPage = testingLibraryReactModule.screen.getByTestId("login-page");
        vitestModule.expect(loginPage).toBeInTheDocument();
        vitestModule.expect(loginPage.getAttribute("data-search")).toBe("?reset=success");
      });
    }
  );

  vitestModule.it("shows API error message on failure", async () => {
    const { ApiError } = await import("@shared/http/api_error");
    const expiredTokenError = new ApiError(401, "Token expirado", "req-1");
    const failingMock = vitestModule.vi.fn(async () => {
      throw expiredTokenError;
    });

    vitestModule.vi
      .spyOn(authContextModule, "useAuth")
      .mockReturnValue(buildAuthContext({ confirmPasswordReset: failingMock }));

    renderResetPasswordPage();

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Nueva contraseña"),
      { target: { value: "secretpass" } }
    );
    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Confirmar contraseña"),
      { target: { value: "secretpass" } }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Guardar contraseña" })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText(/Token expirado/))
        .toBeInTheDocument();
    });
  });
});

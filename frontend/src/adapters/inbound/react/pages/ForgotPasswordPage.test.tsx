import * as reactRouterDomModule from "react-router-dom";
import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import * as authContextModule from "@adapters/inbound/react/app/AuthContext";

import * as forgotPasswordPageModule from "./ForgotPasswordPage";

function renderForgotPasswordPage() {
  return testingLibraryReactModule.render(
    <reactRouterDomModule.MemoryRouter initialEntries={["/forgot-password"]}>
      <reactRouterDomModule.Routes>
        <reactRouterDomModule.Route
          element={<forgotPasswordPageModule.ForgotPasswordPage />}
          path="/forgot-password"
        />
        <reactRouterDomModule.Route
          element={<div data-testid="login-page">Login</div>}
          path="/login"
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

vitestModule.describe("ForgotPasswordPage", () => {
  vitestModule.beforeEach(() => {
    vitestModule.vi.spyOn(authContextModule, "useAuth").mockReturnValue(buildAuthContext());
  });

  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
  });

  vitestModule.it("renders email form by default", () => {
    renderForgotPasswordPage();

    vitestModule
      .expect(testingLibraryReactModule.screen.getByLabelText("Correo electrónico"))
      .toBeInTheDocument();
    vitestModule
      .expect(testingLibraryReactModule.screen.getByRole("button", { name: "Enviar link" }))
      .toBeInTheDocument();
  });

  vitestModule.it("calls requestPasswordReset with trimmed email on submit", async () => {
    const requestPasswordResetMock = vitestModule.vi.fn(async () => undefined);
    vitestModule.vi
      .spyOn(authContextModule, "useAuth")
      .mockReturnValue(buildAuthContext({ requestPasswordReset: requestPasswordResetMock }));

    renderForgotPasswordPage();

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Correo electrónico"),
      { target: { value: "  user@example.com  " } }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Enviar link" })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule.expect(requestPasswordResetMock).toHaveBeenCalledWith({
        email: "user@example.com"
      });
    });
  });

  vitestModule.it("renders confirmation card after successful submission", async () => {
    const requestPasswordResetMock = vitestModule.vi.fn(async () => undefined);
    vitestModule.vi
      .spyOn(authContextModule, "useAuth")
      .mockReturnValue(buildAuthContext({ requestPasswordReset: requestPasswordResetMock }));

    renderForgotPasswordPage();

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Correo electrónico"),
      { target: { value: "user@example.com" } }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Enviar link" })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText(/Si la cuenta existe/))
        .toBeInTheDocument();
    });

    vitestModule
      .expect(testingLibraryReactModule.screen.queryByLabelText("Correo electrónico"))
      .toBeNull();
  });

  vitestModule.it("shows API error message on failure", async () => {
    const { ApiError } = await import("@shared/http/api_error");
    const rateLimitError = new ApiError(429, "Demasiados intentos", "req-1");
    const failingMock = vitestModule.vi.fn(async () => {
      throw rateLimitError;
    });

    vitestModule.vi
      .spyOn(authContextModule, "useAuth")
      .mockReturnValue(buildAuthContext({ requestPasswordReset: failingMock }));

    renderForgotPasswordPage();

    testingLibraryReactModule.fireEvent.change(
      testingLibraryReactModule.screen.getByLabelText("Correo electrónico"),
      { target: { value: "user@example.com" } }
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Enviar link" })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText(/Demasiados intentos/))
        .toBeInTheDocument();
    });
  });
});

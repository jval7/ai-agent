import * as reactQueryModule from "@tanstack/react-query";
import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import type * as containerModule from "@infrastructure/di/container";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as apiErrorModule from "@shared/http/api_error";

import * as billingPreflightModalModule from "./BillingPreflightModal";

interface RenderProps {
  defaultPhoneNumber?: string;
  onSuccess?: (phone: string) => void;
  onCancel?: () => void;
  runPreflight?: vitestModule.Mock;
}

function renderModal(props: RenderProps = {}) {
  const onSuccess = props.onSuccess ?? vitestModule.vi.fn();
  const onCancel = props.onCancel ?? vitestModule.vi.fn();
  const runPreflight =
    props.runPreflight ??
    vitestModule.vi.fn(async (phone: string) => ({
      ok: true,
      recipientPhoneNumber: phone
    }));

  const fakeContainer = {
    whatsappBillingUseCase: {
      runPreflight
    }
  };

  const queryClient = new reactQueryModule.QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });

  const utils = testingLibraryReactModule.render(
    <reactQueryModule.QueryClientProvider client={queryClient}>
      <appContainerContextModule.AppContainerProvider
        container={fakeContainer as unknown as containerModule.AppContainer}
      >
        <billingPreflightModalModule.BillingPreflightModal
          defaultPhoneNumber={props.defaultPhoneNumber ?? ""}
          isOpen
          onCancel={onCancel}
          onSuccess={onSuccess}
        />
      </appContainerContextModule.AppContainerProvider>
    </reactQueryModule.QueryClientProvider>
  );
  return { ...utils, onSuccess, onCancel, runPreflight };
}

vitestModule.describe("BillingPreflightModal", () => {
  vitestModule.afterEach(() => {
    testingLibraryReactModule.cleanup();
  });

  vitestModule.it("disables verify button when phone is invalid", () => {
    renderModal({ defaultPhoneNumber: "12345" });
    const button = testingLibraryReactModule.screen.getByRole("button", {
      name: /Verificar/i
    });
    vitestModule.expect(button.hasAttribute("disabled")).toBe(true);
  });

  vitestModule.it("calls onSuccess after a successful preflight", async () => {
    const { runPreflight, onSuccess } = renderModal({ defaultPhoneNumber: "+573001234567" });
    const button = testingLibraryReactModule.screen.getByRole("button", { name: /Verificar/i });
    testingLibraryReactModule.fireEvent.click(button);
    await testingLibraryReactModule.waitFor(() => {
      vitestModule.expect(onSuccess).toHaveBeenCalledWith("+573001234567");
    });
    vitestModule.expect(runPreflight).toHaveBeenCalledWith("+573001234567");
  });

  vitestModule.it(
    "renders the billing-not-configured message and code 131042 on 402 error",
    async () => {
      const error = new apiErrorModule.ApiError(402, "no payment method", "req-1", {
        code: "WHATSAPP_BILLING_NOT_CONFIGURED",
        meta_error_code: 131042,
        message: "no payment method"
      });
      const runPreflight = vitestModule.vi.fn(async () => {
        throw error;
      });
      renderModal({ defaultPhoneNumber: "+573001234567", runPreflight });

      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getByRole("button", { name: /Verificar/i })
      );

      await testingLibraryReactModule.waitFor(() => {
        vitestModule
          .expect(
            testingLibraryReactModule.screen.getByText(
              /Aún no detectamos un método de pago activo/i
            )
          )
          .toBeTruthy();
      });
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText(/Código Meta: 131042/i))
        .toBeTruthy();
      const link = testingLibraryReactModule.screen.getByRole("link", {
        name: /Abrir Meta Business Manager/i
      });
      vitestModule
        .expect(link.getAttribute("href"))
        .toContain("business.facebook.com/billing_hub/payment_settings");
    }
  );

  vitestModule.it("renders generic error and meta code on a non-billing failure", async () => {
    const error = new apiErrorModule.ApiError(502, "rate limited", "req-2", {
      code: "WHATSAPP_PREFLIGHT_FAILED",
      meta_error_code: 80007,
      message: "rate limited"
    });
    const runPreflight = vitestModule.vi.fn(async () => {
      throw error;
    });
    renderModal({ defaultPhoneNumber: "+573001234567", runPreflight });

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Verificar/i })
    );

    await testingLibraryReactModule.waitFor(() => {
      vitestModule
        .expect(testingLibraryReactModule.screen.getByText(/No pudimos verificar la facturación/i))
        .toBeTruthy();
    });
    vitestModule
      .expect(testingLibraryReactModule.screen.getByText(/Código Meta: 80007/i))
      .toBeTruthy();
  });
});

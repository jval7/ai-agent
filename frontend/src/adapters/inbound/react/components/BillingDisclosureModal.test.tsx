import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import * as billingDisclosureModalModule from "./BillingDisclosureModal";

function renderModal(
  overrides: Partial<{
    isOpen: boolean;
    onContinue: () => void;
    onCancel: () => void;
  }> = {}
) {
  const onContinue = overrides.onContinue ?? vitestModule.vi.fn();
  const onCancel = overrides.onCancel ?? vitestModule.vi.fn();
  const isOpen = overrides.isOpen ?? true;
  const utils = testingLibraryReactModule.render(
    <billingDisclosureModalModule.BillingDisclosureModal
      isOpen={isOpen}
      onCancel={onCancel}
      onContinue={onContinue}
    />
  );
  return { ...utils, onContinue, onCancel };
}

vitestModule.describe("BillingDisclosureModal", () => {
  vitestModule.afterEach(() => {
    testingLibraryReactModule.cleanup();
  });

  vitestModule.it("renders nothing when isOpen is false", () => {
    renderModal({ isOpen: false });
    vitestModule
      .expect(testingLibraryReactModule.screen.queryByText(/Antes de activar los recordatorios/i))
      .toBeNull();
  });

  vitestModule.it("renders cost copy and Meta Business Manager link", () => {
    renderModal();
    vitestModule
      .expect(testingLibraryReactModule.screen.getByText(/Antes de activar los recordatorios/i))
      .toBeTruthy();
    vitestModule
      .expect(testingLibraryReactModule.screen.getByText(/Meta cobra cada mensaje/i))
      .toBeTruthy();
    const link = testingLibraryReactModule.screen.getByRole("link", {
      name: /Abrir Meta Business Manager/i
    });
    vitestModule
      .expect(link.getAttribute("href"))
      .toContain("business.facebook.com/billing_hub/payment_settings");
    vitestModule.expect(link.getAttribute("target")).toBe("_blank");
    vitestModule.expect(link.getAttribute("rel")).toContain("noopener");
  });

  vitestModule.it("invokes onContinue when continue button clicked", () => {
    const onContinue = vitestModule.vi.fn();
    renderModal({ onContinue });
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", {
        name: /Ya configuré el método de pago/i
      })
    );
    vitestModule.expect(onContinue).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("invokes onCancel when cancel button clicked", () => {
    const onCancel = vitestModule.vi.fn();
    renderModal({ onCancel });
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Cancelar/i })
    );
    vitestModule.expect(onCancel).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("invokes onCancel when Escape pressed", () => {
    const onCancel = vitestModule.vi.fn();
    renderModal({ onCancel });
    testingLibraryReactModule.fireEvent.keyDown(document, { key: "Escape" });
    vitestModule.expect(onCancel).toHaveBeenCalledTimes(1);
  });
});

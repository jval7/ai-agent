import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import type * as whatsappTemplateModel from "@domain/models/whatsapp_template";

import * as officialTemplateCardModule from "./OfficialTemplateCard";

function resolveOfficialName(kind: whatsappTemplateModel.OfficialReminderKind): string {
  if (kind === "PAYMENT") {
    return "appointment_reminder_payment";
  }
  return "appointment_reminder_attendance";
}

function buildStatus(
  kind: whatsappTemplateModel.OfficialReminderKind,
  metaStatus: whatsappTemplateModel.OfficialTemplateMetaStatus,
  rejectionReason: string | null = null
): whatsappTemplateModel.OfficialTemplateStatus {
  return { kind, name: resolveOfficialName(kind), metaStatus, rejectionReason };
}

function renderCard(
  kind: whatsappTemplateModel.OfficialReminderKind,
  metaStatus: whatsappTemplateModel.OfficialTemplateMetaStatus,
  opts: {
    onActivate?: () => void;
    onDeactivate?: () => void;
    isMutating?: boolean;
    rejectionReason?: string | null;
  } = {}
) {
  const onActivate = opts.onActivate ?? vitestModule.vi.fn();
  const onDeactivate = opts.onDeactivate ?? vitestModule.vi.fn();
  const isMutating = opts.isMutating ?? false;
  const rejectionReason = opts.rejectionReason ?? null;

  return testingLibraryReactModule.render(
    <officialTemplateCardModule.OfficialTemplateCard
      isMutating={isMutating}
      kind={kind}
      onActivate={onActivate}
      onDeactivate={onDeactivate}
      status={buildStatus(kind, metaStatus, rejectionReason)}
    />
  );
}

vitestModule.describe("OfficialTemplateCard", () => {
  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
  });

  vitestModule.describe("ATTENDANCE kind", () => {
    vitestModule.it("renders the humanized kind label", () => {
      renderCard("ATTENDANCE", "NOT_CREATED");
      expect(
        testingLibraryReactModule.screen.getByText("Recordatorio de asistencia")
      ).toBeInTheDocument();
    });

    vitestModule.it("renders the ATTENDANCE body preview", () => {
      renderCard("ATTENDANCE", "NOT_CREATED");
      expect(testingLibraryReactModule.screen.getByText(/Te esperamos/)).toBeInTheDocument();
    });
  });

  vitestModule.describe("PAYMENT kind", () => {
    vitestModule.it("renders the humanized kind label", () => {
      renderCard("PAYMENT", "NOT_CREATED");
      expect(
        testingLibraryReactModule.screen.getByText("Recordatorio de pago + cita")
      ).toBeInTheDocument();
    });

    vitestModule.it("renders the PAYMENT body preview", () => {
      renderCard("PAYMENT", "NOT_CREATED");
      expect(
        testingLibraryReactModule.screen.getByText(/Aún no hemos recibido tu pago/)
      ).toBeInTheDocument();
    });
  });

  vitestModule.describe("badge per metaStatus", () => {
    vitestModule.it("NOT_CREATED shows 'No activada' badge", () => {
      renderCard("ATTENDANCE", "NOT_CREATED");
      expect(testingLibraryReactModule.screen.getByText("No activada")).toBeInTheDocument();
    });

    vitestModule.it("PENDING shows 'Pendiente de review' badge", () => {
      renderCard("ATTENDANCE", "PENDING");
      expect(testingLibraryReactModule.screen.getByText("Pendiente de review")).toBeInTheDocument();
    });

    vitestModule.it("APPROVED shows 'Activa' badge", () => {
      renderCard("ATTENDANCE", "APPROVED");
      expect(testingLibraryReactModule.screen.getByText("Activa")).toBeInTheDocument();
    });

    vitestModule.it("REJECTED shows 'Rechazada' badge", () => {
      renderCard("ATTENDANCE", "REJECTED");
      expect(testingLibraryReactModule.screen.getByText("Rechazada")).toBeInTheDocument();
    });

    vitestModule.it("DISABLED shows 'Deshabilitada en Meta' badge", () => {
      renderCard("ATTENDANCE", "DISABLED");
      expect(
        testingLibraryReactModule.screen.getByText("Deshabilitada en Meta")
      ).toBeInTheDocument();
    });
  });

  vitestModule.describe("button logic", () => {
    vitestModule.it("shows Activar button when NOT_CREATED", () => {
      renderCard("ATTENDANCE", "NOT_CREATED");
      expect(
        testingLibraryReactModule.screen.getByRole("button", { name: "Activar" })
      ).toBeInTheDocument();
    });

    vitestModule.it("shows Desactivar button when APPROVED", () => {
      renderCard("ATTENDANCE", "APPROVED");
      expect(
        testingLibraryReactModule.screen.getByRole("button", { name: "Desactivar" })
      ).toBeInTheDocument();
    });

    vitestModule.it("shows Desactivar button when PENDING", () => {
      renderCard("ATTENDANCE", "PENDING");
      expect(
        testingLibraryReactModule.screen.getByRole("button", { name: "Desactivar" })
      ).toBeInTheDocument();
    });

    vitestModule.it("shows Desactivar button when REJECTED", () => {
      renderCard("ATTENDANCE", "REJECTED");
      expect(
        testingLibraryReactModule.screen.getByRole("button", { name: "Desactivar" })
      ).toBeInTheDocument();
    });

    vitestModule.it("shows Desactivar button when DISABLED", () => {
      renderCard("ATTENDANCE", "DISABLED");
      expect(
        testingLibraryReactModule.screen.getByRole("button", { name: "Desactivar" })
      ).toBeInTheDocument();
    });

    vitestModule.it("clicking Activar triggers onActivate", async () => {
      const onActivate = vitestModule.vi.fn();
      renderCard("ATTENDANCE", "NOT_CREATED", { onActivate });
      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getByRole("button", { name: "Activar" })
      );
      expect(onActivate).toHaveBeenCalledOnce();
    });

    vitestModule.it("clicking Desactivar triggers onDeactivate", async () => {
      const onDeactivate = vitestModule.vi.fn();
      renderCard("ATTENDANCE", "APPROVED", { onDeactivate });
      testingLibraryReactModule.fireEvent.click(
        testingLibraryReactModule.screen.getByRole("button", { name: "Desactivar" })
      );
      expect(onDeactivate).toHaveBeenCalledOnce();
    });

    vitestModule.it("button is disabled while isMutating=true", () => {
      renderCard("ATTENDANCE", "NOT_CREATED", { isMutating: true });
      expect(
        testingLibraryReactModule.screen.getByRole("button", { name: "Procesando..." })
      ).toBeDisabled();
    });
  });

  vitestModule.describe("rejection reason", () => {
    vitestModule.it("shows rejection reason text when present", () => {
      renderCard("ATTENDANCE", "REJECTED", { rejectionReason: "Contenido inapropiado" });
      expect(
        testingLibraryReactModule.screen.getByText(/Contenido inapropiado/)
      ).toBeInTheDocument();
    });

    vitestModule.it("does not show rejection reason section when null", () => {
      renderCard("ATTENDANCE", "APPROVED", { rejectionReason: null });
      expect(
        testingLibraryReactModule.screen.queryByText(/Motivo de rechazo/)
      ).not.toBeInTheDocument();
    });
  });
});

import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import * as appointmentDetailCardModule from "./AppointmentDetailCard";

function renderCard(
  overrides: Partial<appointmentDetailCardModule.AppointmentDetailCardProps> = {}
) {
  const defaultProps: appointmentDetailCardModule.AppointmentDetailCardProps = {
    origin: "CHATBOT",
    modality: "VIRTUAL",
    patientFullName: "Juan Perez",
    summary: "Ansiedad leve",
    startAt: "2026-03-12T11:00:00Z",
    endAt: "2026-03-12T12:00:00Z",
    timezone: "UTC",
    durationMinutes: 60,
    payment: { status: "PENDING", amountCop: null, category: null },
    paymentDraft: { amountCop: "", category: "CASH" },
    onPaymentDraftChange: vitestModule.vi.fn(),
    isSavingPayment: false,
    onSavePayment: vitestModule.vi.fn(),
    onReschedule: vitestModule.vi.fn(),
    onCancel: vitestModule.vi.fn(),
    errorMessage: null,
    successMessage: null,
    ...overrides
  };
  return testingLibraryReactModule.render(
    <appointmentDetailCardModule.AppointmentDetailCard {...defaultProps} />
  );
}

vitestModule.describe("AppointmentDetailCard", () => {
  vitestModule.it("renders patient name and kicker for chatbot origin", () => {
    renderCard();
    expect(testingLibraryReactModule.screen.getByText("Juan Perez")).toBeInTheDocument();
    expect(testingLibraryReactModule.screen.getByText("Cita chatbot")).toBeInTheDocument();
    expect(testingLibraryReactModule.screen.getByText("Google Meet")).toBeInTheDocument();
  });

  vitestModule.it("renders kicker for manual origin", () => {
    renderCard({ origin: "MANUAL", modality: "PRESENCIAL" });
    expect(testingLibraryReactModule.screen.getByText("Cita manual")).toBeInTheDocument();
    expect(testingLibraryReactModule.screen.getByText("Presencial")).toBeInTheDocument();
  });

  vitestModule.it("renders summary when provided", () => {
    renderCard({ summary: "Episodio de ansiedad" });
    expect(testingLibraryReactModule.screen.getByText("Episodio de ansiedad")).toBeInTheDocument();
  });

  vitestModule.it("renders 'Sin motivo' when summary is null", () => {
    renderCard({ summary: null });
    expect(testingLibraryReactModule.screen.getByText("Sin motivo")).toBeInTheDocument();
  });

  vitestModule.it("renders payment form when payment status is PENDING", () => {
    renderCard();
    expect(
      testingLibraryReactModule.screen.getByRole("spinbutton", { name: /Valor \(COP\)/i })
    ).toBeInTheDocument();
    expect(
      testingLibraryReactModule.screen.getByRole("button", { name: "Registrar pago" })
    ).toBeInTheDocument();
  });

  vitestModule.it("renders paid status read-only when payment is PAID", () => {
    renderCard({
      payment: { status: "PAID", amountCop: 150000, category: "TRANSFER" }
    });
    expect(testingLibraryReactModule.screen.getByText("Pagado")).toBeInTheDocument();
    expect(
      testingLibraryReactModule.screen.queryByRole("button", { name: "Registrar pago" })
    ).toBeNull();
  });

  vitestModule.it("renders action buttons in ACCIONES section", () => {
    renderCard();
    expect(
      testingLibraryReactModule.screen.getByRole("button", { name: /Reprogramar cita/i })
    ).toBeInTheDocument();
    expect(
      testingLibraryReactModule.screen.getByRole("button", { name: /Cancelar cita/i })
    ).toBeInTheDocument();
  });

  vitestModule.it("calls onSavePayment when Registrar pago is clicked", async () => {
    const onSavePayment = vitestModule.vi.fn();
    renderCard({ onSavePayment });
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Registrar pago" })
    );
    expect(onSavePayment).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("calls onReschedule when Reprogramar cita is clicked", () => {
    const onReschedule = vitestModule.vi.fn();
    renderCard({ onReschedule });
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Reprogramar cita/i })
    );
    expect(onReschedule).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("calls onCancel when Cancelar cita is clicked", () => {
    const onCancel = vitestModule.vi.fn();
    renderCard({ onCancel });
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Cancelar cita/i })
    );
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("renders error message when provided", () => {
    renderCard({ errorMessage: "Algo salió mal" });
    expect(testingLibraryReactModule.screen.getByText("Algo salió mal")).toBeInTheDocument();
  });

  vitestModule.it("renders success message when provided", () => {
    renderCard({ successMessage: "Cita actualizada correctamente" });
    expect(
      testingLibraryReactModule.screen.getByText("Cita actualizada correctamente")
    ).toBeInTheDocument();
  });

  vitestModule.it("renders duration minutes in metadata grid", () => {
    renderCard({ durationMinutes: 45 });
    expect(testingLibraryReactModule.screen.getByText("45 min")).toBeInTheDocument();
  });

  vitestModule.it(
    'renders "Cambiar a virtual" when modality is PRESENCIAL and onChangeModality is provided',
    () => {
      const onChangeModality = vitestModule.vi.fn();
      renderCard({ modality: "PRESENCIAL", onChangeModality });
      expect(
        testingLibraryReactModule.screen.getByRole("button", { name: /Cambiar a virtual/i })
      ).toBeInTheDocument();
    }
  );

  vitestModule.it(
    'renders "Cambiar a presencial" when modality is VIRTUAL and onChangeModality is provided',
    () => {
      const onChangeModality = vitestModule.vi.fn();
      renderCard({ modality: "VIRTUAL", onChangeModality });
      expect(
        testingLibraryReactModule.screen.getByRole("button", { name: /Cambiar a presencial/i })
      ).toBeInTheDocument();
    }
  );

  vitestModule.it(
    "does not render change-modality button when onChangeModality is not provided",
    () => {
      renderCard({ modality: "PRESENCIAL" });
      expect(
        testingLibraryReactModule.screen.queryByRole("button", { name: /Cambiar a virtual/i })
      ).toBeNull();
    }
  );

  vitestModule.it("calls onChangeModality when change-modality button is clicked", () => {
    const onChangeModality = vitestModule.vi.fn();
    renderCard({ modality: "PRESENCIAL", onChangeModality });
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Cambiar a virtual/i })
    );
    expect(onChangeModality).toHaveBeenCalledTimes(1);
  });
});

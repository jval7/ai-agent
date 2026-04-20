import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import * as appointmentDrawerModule from "./AppointmentDrawer";

vitestModule.describe("AppointmentDrawer", () => {
  vitestModule.it("renders nothing when isOpen is false", () => {
    const onClose = vitestModule.vi.fn();
    testingLibraryReactModule.render(
      <appointmentDrawerModule.AppointmentDrawer isOpen={false} onClose={onClose}>
        <p>Contenido del drawer</p>
      </appointmentDrawerModule.AppointmentDrawer>
    );
    expect(testingLibraryReactModule.screen.queryByText("Contenido del drawer")).toBeNull();
  });

  vitestModule.it("renders children when isOpen is true", () => {
    const onClose = vitestModule.vi.fn();
    testingLibraryReactModule.render(
      <appointmentDrawerModule.AppointmentDrawer isOpen onClose={onClose}>
        <p>Contenido del drawer</p>
      </appointmentDrawerModule.AppointmentDrawer>
    );
    expect(testingLibraryReactModule.screen.getByText("Contenido del drawer")).toBeInTheDocument();
  });

  vitestModule.it("calls onClose when the close button is clicked", () => {
    const onClose = vitestModule.vi.fn();
    testingLibraryReactModule.render(
      <appointmentDrawerModule.AppointmentDrawer isOpen onClose={onClose}>
        <p>Contenido</p>
      </appointmentDrawerModule.AppointmentDrawer>
    );
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "Cerrar" })
    );
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("calls onClose when the backdrop is clicked", () => {
    const onClose = vitestModule.vi.fn();
    const { container } = testingLibraryReactModule.render(
      <appointmentDrawerModule.AppointmentDrawer isOpen onClose={onClose}>
        <p>Contenido</p>
      </appointmentDrawerModule.AppointmentDrawer>
    );
    // The backdrop is the second child of the fixed inset-0 div
    const backdrop = container.querySelector(".absolute.inset-0")!;
    testingLibraryReactModule.fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("calls onClose when Escape key is pressed", () => {
    const onClose = vitestModule.vi.fn();
    testingLibraryReactModule.render(
      <appointmentDrawerModule.AppointmentDrawer isOpen onClose={onClose}>
        <p>Contenido</p>
      </appointmentDrawerModule.AppointmentDrawer>
    );
    testingLibraryReactModule.fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

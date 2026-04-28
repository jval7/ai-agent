import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import * as chipListModule from "./ChipList";

vitestModule.describe("ChipList", () => {
  vitestModule.afterEach(() => {
    testingLibraryReactModule.cleanup();
  });

  vitestModule.it("renders existing items as chips", () => {
    const onChange = vitestModule.vi.fn();
    testingLibraryReactModule.render(
      <chipListModule.ChipList disabled={false} items={["ansiedad", "duelo"]} onChange={onChange} />
    );
    vitestModule.expect(testingLibraryReactModule.screen.getByText("ansiedad")).toBeTruthy();
    vitestModule.expect(testingLibraryReactModule.screen.getByText("duelo")).toBeTruthy();
  });

  vitestModule.it("adds a new item on Enter key", () => {
    const onChange = vitestModule.vi.fn();
    testingLibraryReactModule.render(
      <chipListModule.ChipList disabled={false} items={[]} onChange={onChange} />
    );
    const input = testingLibraryReactModule.screen.getByRole("textbox");
    testingLibraryReactModule.fireEvent.change(input, { target: { value: "burnout" } });
    testingLibraryReactModule.fireEvent.keyDown(input, { key: "Enter" });
    vitestModule.expect(onChange).toHaveBeenCalledWith(["burnout"]);
  });

  vitestModule.it("adds a new item when comma is typed", () => {
    const onChange = vitestModule.vi.fn();
    testingLibraryReactModule.render(
      <chipListModule.ChipList disabled={false} items={[]} onChange={onChange} />
    );
    const input = testingLibraryReactModule.screen.getByRole("textbox");
    testingLibraryReactModule.fireEvent.change(input, { target: { value: "burnout," } });
    vitestModule.expect(onChange).toHaveBeenCalledWith(["burnout"]);
  });

  vitestModule.it("does not add duplicate (case-insensitive)", () => {
    const onChange = vitestModule.vi.fn();
    testingLibraryReactModule.render(
      <chipListModule.ChipList disabled={false} items={["Ansiedad"]} onChange={onChange} />
    );
    const input = testingLibraryReactModule.screen.getByRole("textbox");
    testingLibraryReactModule.fireEvent.change(input, { target: { value: "ansiedad" } });
    testingLibraryReactModule.fireEvent.keyDown(input, { key: "Enter" });
    vitestModule.expect(onChange).not.toHaveBeenCalled();
  });

  vitestModule.it("removes item when × button is clicked", () => {
    const onChange = vitestModule.vi.fn();
    testingLibraryReactModule.render(
      <chipListModule.ChipList disabled={false} items={["ansiedad", "duelo"]} onChange={onChange} />
    );
    const removeButton = testingLibraryReactModule.screen.getByLabelText("Eliminar ansiedad");
    testingLibraryReactModule.fireEvent.click(removeButton);
    vitestModule.expect(onChange).toHaveBeenCalledWith(["duelo"]);
  });

  vitestModule.it("does not render remove buttons when disabled", () => {
    const onChange = vitestModule.vi.fn();
    testingLibraryReactModule.render(
      <chipListModule.ChipList disabled={true} items={["ansiedad"]} onChange={onChange} />
    );
    vitestModule
      .expect(testingLibraryReactModule.screen.queryByLabelText("Eliminar ansiedad"))
      .toBeNull();
  });
});

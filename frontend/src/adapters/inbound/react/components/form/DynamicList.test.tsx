import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import * as dynamicListModule from "./DynamicList";

interface TestItem {
  label: string;
}

function newItem(): TestItem {
  return { label: "" };
}

function renderList(items: TestItem[], onChange: (next: TestItem[]) => void) {
  return testingLibraryReactModule.render(
    <dynamicListModule.DynamicList
      addLabel="Agregar"
      emptyMessage="Lista vacía"
      items={items}
      newItemFactory={newItem}
      onChange={onChange}
      renderItem={(item, index, onItemChange) => (
        <div key={index}>
          <span>{item.label || `item-${index}`}</span>
          <button
            onClick={() => {
              onItemChange({ label: "edited" });
            }}
            type="button"
          >
            editar
          </button>
        </div>
      )}
    />
  );
}

vitestModule.describe("DynamicList", () => {
  vitestModule.afterEach(() => {
    testingLibraryReactModule.cleanup();
  });

  vitestModule.it("shows empty message when list is empty", () => {
    const onChange = vitestModule.vi.fn();
    renderList([], onChange);
    vitestModule.expect(testingLibraryReactModule.screen.getByText("Lista vacía")).toBeTruthy();
  });

  vitestModule.it("renders each item", () => {
    const onChange = vitestModule.vi.fn();
    renderList([{ label: "primero" }, { label: "segundo" }], onChange);
    vitestModule.expect(testingLibraryReactModule.screen.getByText("primero")).toBeTruthy();
    vitestModule.expect(testingLibraryReactModule.screen.getByText("segundo")).toBeTruthy();
  });

  vitestModule.it("calls onChange with new item when add button is clicked", () => {
    const onChange = vitestModule.vi.fn();
    renderList([], onChange);
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: /Agregar/i })
    );
    vitestModule.expect(onChange).toHaveBeenCalledWith([{ label: "" }]);
  });

  vitestModule.it("removes item when × button is clicked", () => {
    const onChange = vitestModule.vi.fn();
    renderList([{ label: "a" }, { label: "b" }], onChange);
    const removeButtons = testingLibraryReactModule.screen.getAllByLabelText("Eliminar");
    const firstButton = removeButtons[0];
    if (firstButton === undefined) throw new Error("Expected at least one remove button");
    testingLibraryReactModule.fireEvent.click(firstButton);
    vitestModule.expect(onChange).toHaveBeenCalledWith([{ label: "b" }]);
  });

  vitestModule.it("calls onChange with updated item via onItemChange", () => {
    const onChange = vitestModule.vi.fn();
    renderList([{ label: "original" }], onChange);
    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByRole("button", { name: "editar" })
    );
    vitestModule.expect(onChange).toHaveBeenCalledWith([{ label: "edited" }]);
  });
});

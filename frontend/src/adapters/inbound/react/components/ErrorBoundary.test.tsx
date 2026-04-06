import * as testingLibraryReactModule from "@testing-library/react";
import * as vitestModule from "vitest";

import * as errorBoundaryModule from "./ErrorBoundary";

function ThrowingChild(props: { shouldThrow: boolean }) {
  if (props.shouldThrow) {
    throw new Error("test render error");
  }
  return <p>child ok</p>;
}

vitestModule.describe("ErrorBoundary", () => {
  vitestModule.beforeEach(() => {
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    vitestModule.vi.spyOn(console, "error").mockImplementation(() => {});
  });

  vitestModule.afterEach(() => {
    vitestModule.vi.restoreAllMocks();
  });

  vitestModule.it("renders children when no error", () => {
    testingLibraryReactModule.render(
      <errorBoundaryModule.ErrorBoundary>
        <p>hello</p>
      </errorBoundaryModule.ErrorBoundary>
    );
    vitestModule.expect(testingLibraryReactModule.screen.getByText("hello")).toBeDefined();
  });

  vitestModule.it("renders fallback when child throws", () => {
    testingLibraryReactModule.render(
      <errorBoundaryModule.ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </errorBoundaryModule.ErrorBoundary>
    );
    vitestModule.expect(testingLibraryReactModule.screen.getByText("Algo salió mal")).toBeDefined();
    vitestModule
      .expect(testingLibraryReactModule.screen.getByText("test render error"))
      .toBeDefined();
  });

  vitestModule.it("calls onReset via custom fallback when Reintentar is clicked", () => {
    const onResetSpy = vitestModule.vi.fn();

    function SpyFallback(props: { error: Error; onReset: () => void }) {
      return (
        <button
          onClick={() => {
            onResetSpy();
            props.onReset();
          }}
        >
          Reintentar
        </button>
      );
    }

    testingLibraryReactModule.render(
      <errorBoundaryModule.ErrorBoundary fallback={SpyFallback}>
        <ThrowingChild shouldThrow={true} />
      </errorBoundaryModule.ErrorBoundary>
    );

    testingLibraryReactModule.fireEvent.click(
      testingLibraryReactModule.screen.getByText("Reintentar")
    );

    vitestModule.expect(onResetSpy).toHaveBeenCalledTimes(1);
  });

  vitestModule.it("uses custom fallback when provided", () => {
    function CustomFallback(props: { error: Error; onReset: () => void }) {
      return <p>custom: {props.error.message}</p>;
    }

    testingLibraryReactModule.render(
      <errorBoundaryModule.ErrorBoundary fallback={CustomFallback}>
        <ThrowingChild shouldThrow={true} />
      </errorBoundaryModule.ErrorBoundary>
    );

    vitestModule
      .expect(testingLibraryReactModule.screen.getByText("custom: test render error"))
      .toBeDefined();
  });
});

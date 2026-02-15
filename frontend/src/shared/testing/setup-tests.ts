import "@testing-library/jest-dom/vitest";

import * as vitestModule from "vitest";

import * as serverModule from "./msw/server";

vitestModule.beforeAll(() => {
  serverModule.server.listen({ onUnhandledRequest: "error" });
});

vitestModule.afterEach(() => {
  serverModule.server.resetHandlers();
});

vitestModule.afterAll(() => {
  serverModule.server.close();
});

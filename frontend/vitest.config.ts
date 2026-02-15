import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/shared/testing/setup-tests.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.{ts,tsx}"]
    }
  },
  resolve: {
    alias: {
      "@domain": path.resolve(__dirname, "src/domain"),
      "@application": path.resolve(__dirname, "src/application"),
      "@ports": path.resolve(__dirname, "src/ports"),
      "@adapters": path.resolve(__dirname, "src/adapters"),
      "@infrastructure": path.resolve(__dirname, "src/infrastructure"),
      "@shared": path.resolve(__dirname, "src/shared")
    }
  }
});

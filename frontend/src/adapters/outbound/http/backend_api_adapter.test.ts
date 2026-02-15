import * as mswModule from "msw";
import * as vitestModule from "vitest";

import * as serverModule from "@shared/testing/msw/server";

import * as backendApiAdapterModule from "./backend_api_adapter";

class InMemoryTokenSession {
  private accessToken: string | null;
  private refreshToken: string | null;

  constructor(accessToken: string | null, refreshToken: string | null) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  setAccessToken(token: string): void {
    this.accessToken = token;
  }

  clearAccessToken(): void {
    this.accessToken = null;
  }

  getRefreshToken(): string | null {
    return this.refreshToken;
  }

  setRefreshToken(token: string): void {
    this.refreshToken = token;
  }

  clearRefreshToken(): void {
    this.refreshToken = null;
  }

  clearAll(): void {
    this.clearAccessToken();
    this.clearRefreshToken();
  }
}

vitestModule.describe("BackendApiAdapter", () => {
  vitestModule.it("maps login response to domain tokens", async () => {
    serverModule.server.use(
      mswModule.http.post("http://api.test/v1/auth/login", () =>
        mswModule.HttpResponse.json({
          access_token: "access-1",
          refresh_token: "refresh-1",
          token_type: "bearer",
          expires_in_seconds: 1800
        })
      )
    );

    const tokenSession = new InMemoryTokenSession(null, null);
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const tokens = await adapter.login({ email: "owner@acme.com", password: "supersecret" });

    vitestModule.expect(tokens.accessToken).toBe("access-1");
    vitestModule.expect(tokens.refreshToken).toBe("refresh-1");
    vitestModule.expect(tokens.expiresInSeconds).toBe(1800);
  });

  vitestModule.it("refreshes access token on 401 and retries original request", async () => {
    let getPromptCalls = 0;

    serverModule.server.use(
      mswModule.http.get("http://api.test/v1/agent/system-prompt", ({ request }) => {
        getPromptCalls += 1;
        const authHeader = request.headers.get("authorization");

        if (authHeader === "Bearer stale-access") {
          return new mswModule.HttpResponse(null, { status: 401 });
        }

        if (authHeader === "Bearer fresh-access") {
          return mswModule.HttpResponse.json({
            tenant_id: "tenant-1",
            system_prompt: "Hola"
          });
        }

        return new mswModule.HttpResponse(null, { status: 403 });
      }),
      mswModule.http.post("http://api.test/v1/auth/refresh", async ({ request }) => {
        const body = (await request.json()) as { refresh_token: string };
        vitestModule.expect(body.refresh_token).toBe("refresh-1");

        return mswModule.HttpResponse.json({
          access_token: "fresh-access",
          refresh_token: "refresh-2",
          token_type: "bearer",
          expires_in_seconds: 1800
        });
      })
    );

    const tokenSession = new InMemoryTokenSession("stale-access", "refresh-1");
    const adapter = new backendApiAdapterModule.BackendApiAdapter("http://api.test", tokenSession);

    const prompt = await adapter.getSystemPrompt();

    vitestModule.expect(prompt.systemPrompt).toBe("Hola");
    vitestModule.expect(prompt.tenantId).toBe("tenant-1");
    vitestModule.expect(getPromptCalls).toBe(2);
    vitestModule.expect(tokenSession.getAccessToken()).toBe("fresh-access");
    vitestModule.expect(tokenSession.getRefreshToken()).toBe("refresh-2");
  });
});

import * as fetchEventSourceModule from "@microsoft/fetch-event-source";

import type * as eventStreamPortModule from "@ports/event_stream_port";
import type * as tokenSessionPortModule from "@ports/token_session_port";

const EVENTS_PATH = "/v1/events";

export class BackendEventStreamAdapter implements eventStreamPortModule.EventStreamPort {
  constructor(
    private readonly baseUrl: string,
    private readonly tokenSession: tokenSessionPortModule.TokenSessionPort
  ) {}

  connect(
    onEvent: (event: eventStreamPortModule.AppEvent) => void
  ): eventStreamPortModule.EventStreamDisconnect {
    const controller = new AbortController();
    const url = this.baseUrl.replace(/\/+$/, "") + EVENTS_PATH;

    const tokenSession = this.tokenSession;
    const fatalAuthError = new Error("event stream auth failed");

    void fetchEventSourceModule.fetchEventSource(url, {
      signal: controller.signal,
      openWhenHidden: true,
      headers: buildHeaders(tokenSession),
      onopen: (response) => {
        if (response.ok) {
          return Promise.resolve();
        }
        if (response.status === 401 || response.status === 403) {
          return Promise.reject(fatalAuthError);
        }
        return Promise.reject(new Error(`event stream unexpected status: ${response.status}`));
      },
      onmessage: (message) => {
        const parsed = parseEvent(message.event, message.data);
        if (parsed !== null) {
          onEvent(parsed);
        }
      },
      onerror: (error) => {
        if (error === fatalAuthError) {
          controller.abort();
          throw error;
        }
        return undefined;
      }
    });

    return () => {
      controller.abort();
    };
  }
}

function buildHeaders(
  tokenSession: tokenSessionPortModule.TokenSessionPort
): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "text/event-stream"
  };
  const accessToken = tokenSession.getAccessToken();
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  return headers;
}

function parseEvent(eventType: string, data: string): eventStreamPortModule.AppEvent | null {
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(data) as Record<string, unknown>;
  } catch {
    return null;
  }

  switch (eventType) {
    case "connected": {
      const tenantId = payload["tenant_id"];
      if (typeof tenantId !== "string") {
        return null;
      }
      return { type: "connected", tenantId };
    }
    case "conversation.updated":
    case "scheduling_request.updated":
    case "reminder.updated": {
      const id = payload["id"];
      if (typeof id !== "string") {
        return null;
      }
      return { type: eventType, id };
    }
    default:
      return null;
  }
}

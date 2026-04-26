import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "../app/AppContainerContext";
import * as authContextModule from "../app/AuthContext";
import type * as eventStreamPortModule from "@ports/event_stream_port";

export function useEventStream(): void {
  const appContainer = appContainerContextModule.useAppContainer();
  const { status } = authContextModule.useAuth();
  const queryClient = reactQueryModule.useQueryClient();

  reactModule.useEffect(() => {
    if (status !== "authenticated") {
      return;
    }
    const disconnect = appContainer.eventStream.connect((event) => {
      dispatch(event, queryClient);
    });
    return () => {
      disconnect();
    };
  }, [appContainer.eventStream, queryClient, status]);
}

function dispatch(
  event: eventStreamPortModule.AppEvent,
  queryClient: reactQueryModule.QueryClient
): void {
  switch (event.type) {
    case "connected":
      return;
    case "conversation.updated":
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      void queryClient.invalidateQueries({ queryKey: ["conversation-messages", event.id] });
      return;
    case "scheduling_request.updated":
      void queryClient.invalidateQueries({ queryKey: ["scheduling-requests"] });
      return;
    case "reminder.updated":
      void queryClient.invalidateQueries({ queryKey: ["reminders"] });
      return;
  }
}

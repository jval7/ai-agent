import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";
import * as containerModule from "@infrastructure/di/container";

import * as useEventStreamModule from "../hooks/useEventStream";
import * as appContainerContextModule from "./AppContainerContext";
import * as authContextModule from "./AuthContext";

const queryClient = new reactQueryModule.QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
      refetchOnMount: "always"
    }
  }
});

function EventStreamBridge(props: { children: reactModule.ReactNode }) {
  useEventStreamModule.useEventStream();
  return <>{props.children}</>;
}

export function AppProviders(props: { children: reactModule.ReactNode }) {
  const appContainer = reactModule.useMemo(() => containerModule.createAppContainer(), []);

  return (
    <appContainerContextModule.AppContainerProvider container={appContainer}>
      <authContextModule.AuthProvider>
        <reactQueryModule.QueryClientProvider client={queryClient}>
          <EventStreamBridge>{props.children}</EventStreamBridge>
        </reactQueryModule.QueryClientProvider>
      </authContextModule.AuthProvider>
    </appContainerContextModule.AppContainerProvider>
  );
}

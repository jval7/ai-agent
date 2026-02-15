import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";
import * as containerModule from "@infrastructure/di/container";

import * as appContainerContextModule from "./AppContainerContext";
import * as authContextModule from "./AuthContext";

const queryClient = new reactQueryModule.QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false
    }
  }
});

export function AppProviders(props: { children: reactModule.ReactNode }) {
  const appContainer = reactModule.useMemo(() => containerModule.createAppContainer(), []);

  return (
    <appContainerContextModule.AppContainerProvider container={appContainer}>
      <authContextModule.AuthProvider>
        <reactQueryModule.QueryClientProvider client={queryClient}>
          {props.children}
        </reactQueryModule.QueryClientProvider>
      </authContextModule.AuthProvider>
    </appContainerContextModule.AppContainerProvider>
  );
}

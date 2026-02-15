import * as reactModule from "react";

import type * as containerModule from "@infrastructure/di/container";

const AppContainerContext = reactModule.createContext<containerModule.AppContainer | null>(null);

export function AppContainerProvider(props: {
  children: reactModule.ReactNode;
  container: containerModule.AppContainer;
}) {
  return (
    <AppContainerContext.Provider value={props.container}>
      {props.children}
    </AppContainerContext.Provider>
  );
}

export function useAppContainer(): containerModule.AppContainer {
  const container = reactModule.useContext(AppContainerContext);
  if (container === null) {
    throw new Error("AppContainerProvider is required");
  }
  return container;
}

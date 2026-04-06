import * as errorBoundaryModule from "../components/ErrorBoundary";
import * as providersModule from "./Providers";
import * as routerModule from "./Router";

export function App() {
  return (
    <providersModule.AppProviders>
      <errorBoundaryModule.ErrorBoundary>
        <routerModule.AppRouter />
      </errorBoundaryModule.ErrorBoundary>
    </providersModule.AppProviders>
  );
}

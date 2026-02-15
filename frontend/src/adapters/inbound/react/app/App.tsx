import * as providersModule from "./Providers";
import * as routerModule from "./Router";

export function App() {
  return (
    <providersModule.AppProviders>
      <routerModule.AppRouter />
    </providersModule.AppProviders>
  );
}

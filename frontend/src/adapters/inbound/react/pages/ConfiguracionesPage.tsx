import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import { ConfiguracionesView } from "@adapters/inbound/react/pages/views/ConfiguracionesView";

export function ConfiguracionesPage() {
  return (
    <appShellModule.AppShell>
      <ConfiguracionesView />
    </appShellModule.AppShell>
  );
}

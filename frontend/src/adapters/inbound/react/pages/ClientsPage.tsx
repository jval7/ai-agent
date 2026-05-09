import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import { ClientsView } from "@adapters/inbound/react/pages/views/ClientsView";

export function ClientsPage() {
  return (
    <appShellModule.AppShell>
      <ClientsView />
    </appShellModule.AppShell>
  );
}

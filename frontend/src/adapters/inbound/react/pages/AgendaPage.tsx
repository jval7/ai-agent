import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as agendaViewModule from "@adapters/inbound/react/pages/views/AgendaView";

export function AgendaPage() {
  return (
    <appShellModule.AppShell>
      <agendaViewModule.AgendaView />
    </appShellModule.AppShell>
  );
}

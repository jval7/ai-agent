import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import { RecordatoriosView } from "@adapters/inbound/react/pages/views/RecordatoriosView";

export function RecordatoriosPage() {
  return (
    <appShellModule.AppShell>
      <RecordatoriosView />
    </appShellModule.AppShell>
  );
}

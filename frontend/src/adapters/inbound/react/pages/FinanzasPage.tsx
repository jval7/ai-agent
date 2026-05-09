import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import { FinanzasView } from "@adapters/inbound/react/pages/views/FinanzasView";

export function FinanzasPage() {
  return (
    <appShellModule.AppShell>
      <FinanzasView />
    </appShellModule.AppShell>
  );
}

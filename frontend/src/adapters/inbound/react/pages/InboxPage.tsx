import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as inboxViewModule from "@adapters/inbound/react/pages/views/InboxView";

export function InboxPage() {
  return (
    <appShellModule.AppShell>
      <inboxViewModule.InboxView />
    </appShellModule.AppShell>
  );
}

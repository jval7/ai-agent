import type * as backendApiPort from "@ports/backend_api_port";
import type * as scheduledReminderModel from "@domain/models/scheduled_reminder";

export class ReminderUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  listReminders(status?: string): Promise<scheduledReminderModel.ScheduledReminderList> {
    return this.api.listReminders(status);
  }
}

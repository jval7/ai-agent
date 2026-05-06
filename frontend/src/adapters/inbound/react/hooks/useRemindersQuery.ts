import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as scheduledReminderModel from "@domain/models/scheduled_reminder";

export function useRemindersQuery(
  statusFilter?: string,
  tenantId?: string
): reactQueryModule.UseQueryResult<scheduledReminderModel.ScheduledReminderList> {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey:
      tenantId !== undefined
        ? ["admin", tenantId, "reminders", statusFilter]
        : ["reminders", statusFilter],
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListReminders(tenantId, statusFilter)
        : appContainer.reminderUseCase.listReminders(statusFilter)
  });
}

export function useSendReminderNowMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (reminderId: string) =>
      tenantId !== undefined
        ? appContainer.api.adminSendReminderNow(tenantId, reminderId)
        : appContainer.reminderUseCase.sendReminderNow(reminderId),
    onSuccess: async () => {
      if (tenantId !== undefined) {
        await queryClient.invalidateQueries({ queryKey: ["admin", tenantId, "reminders"] });
      } else {
        await queryClient.invalidateQueries({ queryKey: ["reminders"] });
      }
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "Error al enviar el recordatorio";
      window.alert(message);
      if (tenantId !== undefined) {
        void queryClient.invalidateQueries({ queryKey: ["admin", tenantId, "reminders"] });
      } else {
        void queryClient.invalidateQueries({ queryKey: ["reminders"] });
      }
    }
  });
}

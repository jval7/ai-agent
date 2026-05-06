import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";

export const schedulingRequestsQueryKey = ["scheduling-requests"] as const;
export const googleCalendarConnectionQueryKey = ["google-calendar-connection"] as const;
export const patientsQueryKey = ["patients"] as const;
export const manualAppointmentsQueryKey = ["manual-appointments"] as const;

export function useAgendaData() {
  const appContainer = appContainerContextModule.useAppContainer();

  const requestsQuery = reactQueryModule.useQuery({
    queryKey: schedulingRequestsQueryKey,
    queryFn: () => appContainer.schedulingUseCase.listRequests(),
    refetchInterval: 60_000
  });

  const googleCalendarConnectionQuery = reactQueryModule.useQuery({
    queryKey: googleCalendarConnectionQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getGoogleCalendarConnectionStatus()
  });

  const patientsQuery = reactQueryModule.useQuery({
    queryKey: patientsQueryKey,
    queryFn: () => appContainer.patientUseCase.listPatients()
  });

  const manualAppointmentsQuery = reactQueryModule.useQuery({
    queryKey: manualAppointmentsQueryKey,
    queryFn: () => appContainer.manualAppointmentUseCase.listAppointments()
  });

  return {
    requestsQuery,
    googleCalendarConnectionQuery,
    patientsQuery,
    manualAppointmentsQuery
  };
}

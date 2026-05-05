import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as patientModel from "@domain/models/patient";
import type * as schedulingModel from "@domain/models/scheduling";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";

export function useSchedulingRequestsQuery(
  tenantId?: string
): reactQueryModule.UseQueryResult<schedulingModel.SchedulingRequestSummary[]> {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey:
      tenantId !== undefined ? ["admin", tenantId, "scheduling-requests"] : ["scheduling-requests"],
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListSchedulingRequests(tenantId)
        : appContainer.schedulingUseCase.listRequests(),
    refetchInterval: 60_000
  });
}

export function useManualAppointmentsQuery(
  tenantId?: string,
  status?: manualAppointmentModel.ManualAppointmentStatus
): reactQueryModule.UseQueryResult<manualAppointmentModel.ManualAppointment[]> {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey:
      tenantId !== undefined ? ["admin", tenantId, "manual-appointments"] : ["manual-appointments"],
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListManualAppointments(tenantId, status)
        : appContainer.manualAppointmentUseCase.listAppointments(status)
  });
}

export function usePatientsForFinanzasQuery(
  tenantId?: string
): reactQueryModule.UseQueryResult<patientModel.Patient[]> {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey: tenantId !== undefined ? ["admin", tenantId, "patients"] : ["patients"],
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListPatients(tenantId)
        : appContainer.patientUseCase.listPatients()
  });
}

import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import type * as patientModel from "@domain/models/patient";

export function usePatientsQuery(
  search?: string,
  tenantId?: string
): reactQueryModule.UseQueryResult<patientModel.Patient[]> {
  const appContainer = appContainerContextModule.useAppContainer();
  const trimmedSearch = search?.trim();
  const searchParam =
    trimmedSearch !== "" && trimmedSearch !== undefined ? trimmedSearch : undefined;
  return reactQueryModule.useQuery({
    queryKey:
      tenantId !== undefined ? ["admin", tenantId, "patients", search] : ["patients", search],
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminListPatients(
            tenantId,
            searchParam !== undefined ? { search: searchParam } : undefined
          )
        : appContainer.patientUseCase.listPatients(
            searchParam !== undefined ? { search: searchParam } : undefined
          )
  });
}

export function useGetPatientQuery(
  whatsappUserId: string | null,
  tenantId?: string
): reactQueryModule.UseQueryResult<patientModel.Patient> {
  const appContainer = appContainerContextModule.useAppContainer();
  return reactQueryModule.useQuery({
    queryKey:
      tenantId !== undefined
        ? ["admin", tenantId, "patient-detail", whatsappUserId]
        : ["patient-detail", whatsappUserId],
    enabled: whatsappUserId !== null,
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminGetPatient(tenantId, whatsappUserId ?? "")
        : appContainer.patientUseCase.getPatient(whatsappUserId ?? "")
  });
}

export function useCreatePatientMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (input: patientModel.CreatePatientInput) =>
      tenantId !== undefined
        ? appContainer.api.adminCreatePatient(tenantId, input)
        : appContainer.patientUseCase.createPatient(input),
    onSuccess: async () => {
      if (tenantId !== undefined) {
        await queryClient.invalidateQueries({ queryKey: ["admin", tenantId, "patients"] });
      } else {
        await queryClient.invalidateQueries({ queryKey: ["patients"] });
      }
    }
  });
}

export function useUpdatePatientMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: ({
      whatsappUserId,
      input
    }: {
      whatsappUserId: string;
      input: patientModel.UpdatePatientInput;
    }) =>
      tenantId !== undefined
        ? appContainer.api.adminUpdatePatient(tenantId, whatsappUserId, input)
        : appContainer.patientUseCase.updatePatient(whatsappUserId, input),
    onSuccess: async (_data, { whatsappUserId }) => {
      if (tenantId !== undefined) {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["admin", tenantId, "patients"] }),
          queryClient.invalidateQueries({
            queryKey: ["admin", tenantId, "patient-detail", whatsappUserId]
          })
        ]);
      } else {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["patients"] }),
          queryClient.invalidateQueries({ queryKey: ["patient-detail", whatsappUserId] })
        ]);
      }
    }
  });
}

export function useRemovePatientMutation(tenantId?: string) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  return reactQueryModule.useMutation({
    mutationFn: (whatsappUserId: string) =>
      tenantId !== undefined
        ? appContainer.api.adminRemovePatient(tenantId, whatsappUserId)
        : appContainer.patientUseCase.removePatient(whatsappUserId),
    onSuccess: async (_data, whatsappUserId) => {
      if (tenantId !== undefined) {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["admin", tenantId, "patients"] }),
          queryClient.invalidateQueries({
            queryKey: ["admin", tenantId, "patient-detail", whatsappUserId]
          })
        ]);
      } else {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["patients"] }),
          queryClient.invalidateQueries({ queryKey: ["patient-detail", whatsappUserId] })
        ]);
      }
    }
  });
}

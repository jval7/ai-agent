import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as uiErrorModule from "@shared/http/ui_error";
import * as dateUtilsModule from "@shared/utils/date";

const patientsQueryKey = ["patients"] as const;

export function ClientsPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  const patientsQuery = reactQueryModule.useQuery({
    queryKey: patientsQueryKey,
    queryFn: () => appContainer.patientUseCase.listPatients()
  });
  const [selectedWhatsappUserId, setSelectedWhatsappUserId] = reactModule.useState<string | null>(
    null
  );

  reactModule.useEffect(() => {
    if (patientsQuery.data === undefined || patientsQuery.data.length === 0) {
      setSelectedWhatsappUserId(null);
      return;
    }
    const selectedExists = patientsQuery.data.some(
      (patient) => patient.whatsappUserId === selectedWhatsappUserId
    );
    if (!selectedExists) {
      setSelectedWhatsappUserId(patientsQuery.data[0]?.whatsappUserId ?? null);
    }
  }, [patientsQuery.data, selectedWhatsappUserId]);

  const patientDetailQuery = reactQueryModule.useQuery({
    queryKey: ["patient-detail", selectedWhatsappUserId],
    enabled: selectedWhatsappUserId !== null,
    queryFn: () => appContainer.patientUseCase.getPatient(selectedWhatsappUserId ?? "")
  });

  const removePatientMutation = reactQueryModule.useMutation({
    mutationFn: (whatsappUserId: string) =>
      appContainer.patientUseCase.removePatient(whatsappUserId),
    onSuccess: async (_data, whatsappUserId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: patientsQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["patient-detail", whatsappUserId] })
      ]);
    }
  });

  const errorMessage = uiErrorModule.resolveUiErrorMessage([
    patientsQuery.error,
    patientDetailQuery.error,
    removePatientMutation.error
  ]);

  return (
    <appShellModule.AppShell>
      <section className="space-y-3">
        <div>
          <h2 className="text-xl font-semibold text-brand-ink">Clientes</h2>
          <p className="text-sm text-slate-600">
            Historial de pacientes identificados por su numero de WhatsApp.
          </p>
        </div>

        {errorMessage !== null ? <errorBannerModule.ErrorBanner message={errorMessage} /> : null}

        <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
          <article className="rounded-xl border border-slate-200 bg-white">
            <header className="border-b border-slate-200 p-4">
              <h3 className="text-base font-semibold">Pacientes</h3>
            </header>
            <div className="max-h-[70vh] overflow-auto p-2">
              {patientsQuery.isLoading ? (
                <p className="p-3 text-sm text-slate-500">Cargando pacientes...</p>
              ) : null}
              {patientsQuery.data?.length === 0 ? (
                <p className="p-3 text-sm text-slate-500">Aun no hay pacientes registrados.</p>
              ) : null}
              {patientsQuery.data?.map((patient) => {
                const isSelected = patient.whatsappUserId === selectedWhatsappUserId;
                return (
                  <button
                    className={[
                      "mb-2 w-full rounded-lg border p-3 text-left",
                      isSelected
                        ? "border-brand-teal bg-teal-50"
                        : "border-slate-200 bg-white hover:border-slate-300"
                    ].join(" ")}
                    key={patient.whatsappUserId}
                    onClick={() => {
                      setSelectedWhatsappUserId(patient.whatsappUserId);
                    }}
                    type="button"
                  >
                    <p className="truncate text-sm font-semibold text-brand-ink">
                      {patient.firstName} {patient.lastName}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      WhatsApp: {patient.whatsappUserId}
                    </p>
                    <p className="text-xs text-slate-600">Telefono: {patient.phone}</p>
                    <p className="text-xs text-slate-600">Ubicacion: {patient.location}</p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Creado: {dateUtilsModule.formatDateTime(patient.createdAt)}
                    </p>
                  </button>
                );
              })}
            </div>
          </article>

          <article className="rounded-xl border border-slate-200 bg-white">
            <header className="border-b border-slate-200 p-4">
              <h3 className="text-base font-semibold">Detalle del cliente</h3>
            </header>
            <div className="space-y-3 p-4 text-sm text-slate-700">
              {selectedWhatsappUserId === null ? (
                <p className="text-slate-500">Selecciona un cliente para ver su detalle.</p>
              ) : null}
              {patientDetailQuery.isLoading ? (
                <p className="text-slate-500">Cargando detalle...</p>
              ) : null}
              {patientDetailQuery.data !== undefined ? (
                <>
                  <p>
                    <strong>Nombre:</strong> {patientDetailQuery.data.firstName}{" "}
                    {patientDetailQuery.data.lastName}
                  </p>
                  <p>
                    <strong>WhatsApp ID:</strong> {patientDetailQuery.data.whatsappUserId}
                  </p>
                  <p>
                    <strong>Telefono:</strong> {patientDetailQuery.data.phone}
                  </p>
                  <p>
                    <strong>Email:</strong> {patientDetailQuery.data.email}
                  </p>
                  <p>
                    <strong>Edad:</strong> {patientDetailQuery.data.age}
                  </p>
                  <p>
                    <strong>Motivo de consulta:</strong>{" "}
                    {patientDetailQuery.data.consultationReason}
                  </p>
                  <p>
                    <strong>Ubicacion:</strong> {patientDetailQuery.data.location}
                  </p>
                  <p>
                    <strong>Tenant:</strong> {patientDetailQuery.data.tenantId}
                  </p>
                  <p>
                    <strong>Creado:</strong>{" "}
                    {dateUtilsModule.formatDateTime(patientDetailQuery.data.createdAt)}
                  </p>
                  <button
                    className="mt-2 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={removePatientMutation.isPending}
                    onClick={() => {
                      const currentWhatsappUserId = patientDetailQuery.data?.whatsappUserId;
                      if (currentWhatsappUserId === undefined) {
                        return;
                      }
                      const isConfirmed = window.confirm(
                        "¿Seguro que quieres eliminar este paciente? Esta accion no se puede deshacer."
                      );
                      if (!isConfirmed) {
                        return;
                      }
                      removePatientMutation.mutate(currentWhatsappUserId);
                    }}
                    type="button"
                  >
                    {removePatientMutation.isPending ? "Eliminando..." : "Eliminar cliente"}
                  </button>
                </>
              ) : null}
            </div>
          </article>
        </div>
      </section>
    </appShellModule.AppShell>
  );
}

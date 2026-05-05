import * as reactModule from "react";

import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import { NewPatientModal } from "@adapters/inbound/react/components/NewPatientModal";
import * as usePatientsQueryModule from "@adapters/inbound/react/hooks/usePatientsQuery";
import type * as patientModel from "@domain/models/patient";
import * as uiErrorModule from "@shared/http/ui_error";
import * as dateUtilsModule from "@shared/utils/date";

const DEBOUNCE_MS = 300;

function useDebounce(value: string, delay: number): string {
  const [debounced, setDebounced] = reactModule.useState(value);
  reactModule.useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced(value);
    }, delay);
    return () => {
      window.clearTimeout(timer);
    };
  }, [value, delay]);
  return debounced;
}

export function ClientsView({ tenantId }: { tenantId?: string }) {
  const [search, setSearch] = reactModule.useState("");
  const debouncedSearch = useDebounce(search, DEBOUNCE_MS);

  const patientsQuery = usePatientsQueryModule.usePatientsQuery(debouncedSearch, tenantId);

  const [selectedWhatsappUserId, setSelectedWhatsappUserId] = reactModule.useState<string | null>(
    null
  );
  const [isDetailMobileOpen, setIsDetailMobileOpen] = reactModule.useState(false);
  const [isNewPatientOpen, setIsNewPatientOpen] = reactModule.useState(false);
  const [isEditPatientOpen, setIsEditPatientOpen] = reactModule.useState(false);

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

  const patientDetailQuery = usePatientsQueryModule.useGetPatientQuery(
    selectedWhatsappUserId,
    tenantId
  );

  const removePatientMutation = usePatientsQueryModule.useRemovePatientMutation(tenantId);
  const createPatientMutation = usePatientsQueryModule.useCreatePatientMutation(tenantId);
  const updatePatientMutation = usePatientsQueryModule.useUpdatePatientMutation(tenantId);

  const errorMessage = uiErrorModule.resolveUiErrorMessage([
    patientsQuery.error,
    patientDetailQuery.error,
    removePatientMutation.error,
    createPatientMutation.error,
    updatePatientMutation.error
  ]);

  const selectedPatient = patientDetailQuery.data ?? null;

  const patientList = (
    <div className="max-h-[calc(100vh-16rem)] overflow-auto p-2">
      {patientsQuery.isLoading ? (
        <p className="p-3 text-sm text-slate-500">Cargando pacientes...</p>
      ) : null}
      {patientsQuery.data?.length === 0 ? (
        <p className="p-3 text-sm text-slate-500">
          {debouncedSearch !== ""
            ? "Sin resultados para la búsqueda."
            : "Aun no hay pacientes registrados."}
        </p>
      ) : null}
      {patientsQuery.data?.map((patient) => {
        const isSelected = patient.whatsappUserId === selectedWhatsappUserId;
        return (
          <button
            className={[
              "mb-2 w-full rounded-lg border p-3 text-left",
              isSelected
                ? "border-brand-teal bg-brand-accent-light"
                : "border-slate-200 bg-white hover:border-slate-300"
            ].join(" ")}
            key={patient.whatsappUserId}
            onClick={() => {
              setSelectedWhatsappUserId(patient.whatsappUserId);
              setIsDetailMobileOpen(true);
            }}
            type="button"
          >
            <p className="truncate text-sm font-semibold text-brand-ink">
              {patient.firstName} {patient.lastName}
            </p>
            <p className="mt-1 text-xs text-slate-600">WhatsApp: {patient.whatsappUserId}</p>
            <p className="text-xs text-slate-600">
              Telefono:{" "}
              {patient.phonePrefix !== null && patient.phonePrefix !== ""
                ? `${patient.phonePrefix} ${patient.phone}`
                : patient.phone}
            </p>
            <p className="text-xs text-slate-600">Ubicacion: {patient.location}</p>
            <p className="mt-1 text-[11px] text-slate-500">
              Creado: {dateUtilsModule.formatDateTime(patient.createdAt)}
            </p>
          </button>
        );
      })}
    </div>
  );

  const detailPanel = (
    <div className="space-y-3 p-4 text-sm text-slate-700">
      {selectedWhatsappUserId === null ? (
        <p className="text-slate-500">Selecciona un cliente para ver su detalle.</p>
      ) : null}
      {patientDetailQuery.isLoading ? <p className="text-slate-500">Cargando detalle...</p> : null}
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
            <strong>Telefono:</strong>{" "}
            {patientDetailQuery.data.phonePrefix !== null &&
            patientDetailQuery.data.phonePrefix !== ""
              ? `${patientDetailQuery.data.phonePrefix} ${patientDetailQuery.data.phone}`
              : patientDetailQuery.data.phone}
          </p>
          <p>
            <strong>Email:</strong> {patientDetailQuery.data.email}
          </p>
          <p>
            <strong>Edad:</strong> {patientDetailQuery.data.age}
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
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={() => {
                setIsEditPatientOpen(true);
              }}
              type="button"
            >
              <span className="flex items-center gap-1.5">
                <svg
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125"
                  />
                </svg>
                Editar
              </span>
            </button>
            <button
              className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
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
          </div>
        </>
      ) : null}
    </div>
  );

  return (
    <section className="space-y-3">
      {tenantId === undefined ? (
        <div>
          <h2 className="text-xl font-semibold text-brand-ink">Clientes</h2>
          <p className="text-sm text-slate-600">
            Historial de pacientes identificados por su numero de WhatsApp.
          </p>
        </div>
      ) : null}

      {errorMessage !== null ? <errorBannerModule.ErrorBanner message={errorMessage} /> : null}

      <div className="grid max-w-6xl gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <article className="rounded-xl border border-border-subtle bg-white shadow-card">
          <header className="border-b border-border-subtle px-5 py-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold">Pacientes</h3>
              <button
                className="rounded-lg bg-brand-teal px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover"
                onClick={() => {
                  setIsNewPatientOpen(true);
                }}
                type="button"
              >
                + Nuevo paciente
              </button>
            </div>
            <div className="relative mt-3">
              <svg
                className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"
                />
              </svg>
              <input
                className="w-full rounded-xl border border-slate-200 py-2 pl-9 pr-3 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                onChange={(e) => {
                  setSearch(e.target.value);
                }}
                placeholder="Buscar por nombre o teléfono"
                type="search"
                value={search}
              />
            </div>
          </header>
          {patientList}
        </article>

        <article className="rounded-xl border border-border-subtle bg-white shadow-card">
          <header className="border-b border-border-subtle px-5 py-4">
            <h3 className="text-base font-semibold">Detalle del cliente</h3>
          </header>
          {detailPanel}
        </article>
      </div>

      {isDetailMobileOpen && selectedWhatsappUserId !== null ? (
        <div className="fixed inset-0 z-40 flex flex-col bg-brand-surface lg:hidden">
          <div className="flex items-center justify-between border-b border-border-subtle bg-white px-4 py-3">
            <h3 className="text-base font-semibold">Detalle del cliente</h3>
            <button
              className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              onClick={() => {
                setIsDetailMobileOpen(false);
              }}
              type="button"
            >
              <svg
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="overflow-y-auto bg-white">{detailPanel}</div>
        </div>
      ) : null}

      <NewPatientModal
        isOpen={isNewPatientOpen}
        isSubmitting={createPatientMutation.isPending}
        onClose={() => {
          setIsNewPatientOpen(false);
        }}
        onCreated={(whatsappUserId) => {
          setSelectedWhatsappUserId(whatsappUserId);
        }}
        onSubmit={async (input: patientModel.CreatePatientInput) => {
          await createPatientMutation.mutateAsync(input);
        }}
      />

      {selectedPatient !== null ? (
        <NewPatientModal
          isOpen={isEditPatientOpen}
          isSubmitting={updatePatientMutation.isPending}
          onClose={() => {
            setIsEditPatientOpen(false);
          }}
          onUpdated={() => {
            setIsEditPatientOpen(false);
          }}
          onSubmit={async (input: patientModel.UpdatePatientInput) => {
            return updatePatientMutation.mutateAsync({
              whatsappUserId: selectedPatient.whatsappUserId,
              input
            });
          }}
          patient={selectedPatient}
        />
      ) : null}
    </section>
  );
}

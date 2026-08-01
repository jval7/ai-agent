import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import type * as adminModel from "@domain/models/admin";
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

function formatCop(amount: number): string {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0
  }).format(amount);
}

function Avatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0] ?? "")
    .join("")
    .toUpperCase();
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-teal text-xs font-bold text-white">
      {initials}
    </div>
  );
}

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border-subtle bg-white p-5 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-brand-ink">{value}</p>
    </div>
  );
}

function TenantRow({ tenant }: { tenant: adminModel.TenantSummary }) {
  const navigate = reactRouterDomModule.useNavigate();
  return (
    <tr
      className="cursor-pointer transition-colors hover:bg-slate-50"
      onClick={() => {
        void navigate(`/admin/tenants/${tenant.tenantId}`);
      }}
    >
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <Avatar name={tenant.professionalName} />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-brand-ink">
              {tenant.professionalName}
            </p>
            <p className="truncate text-xs text-slate-500">{tenant.ownerEmail}</p>
          </div>
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">{tenant.patientCount}</td>
      <td className="px-4 py-3 text-sm text-slate-700">{tenant.conversationCount}</td>
      <td className="px-4 py-3 text-sm text-slate-700">{tenant.manualAppointmentCountUpcoming}</td>
      <td className="px-4 py-3 text-sm text-slate-700">
        {formatCop(tenant.totalRevenueCopThisMonth)}
      </td>
      <td className="px-4 py-3 text-xs text-slate-500">
        {tenant.lastActivityAt !== null
          ? dateUtilsModule.formatDateTime(tenant.lastActivityAt)
          : "—"}
      </td>
      <td className="px-4 py-3">
        <statusBadgeModule.StatusBadge
          label={tenant.ownerIsActive ? "Activo" : "Inactivo"}
          tone={tenant.ownerIsActive ? "success" : "neutral"}
        />
      </td>
      <td className="px-4 py-3">
        <reactRouterDomModule.Link
          className="rounded-md bg-brand-teal px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover"
          onClick={(e) => e.stopPropagation()}
          to={`/admin/tenants/${tenant.tenantId}`}
        >
          Ver
        </reactRouterDomModule.Link>
      </td>
    </tr>
  );
}

export function AdminHomePage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const [search, setSearch] = reactModule.useState("");
  const debouncedSearch = useDebounce(search, DEBOUNCE_MS);

  const metricsQuery = reactQueryModule.useQuery({
    queryKey: ["admin", "global-metrics"],
    queryFn: () => appContainer.api.adminGetGlobalMetrics()
  });

  const tenantsQuery = reactQueryModule.useQuery({
    queryKey: ["admin", "tenants", debouncedSearch],
    queryFn: () =>
      appContainer.api.adminListTenants(
        debouncedSearch.trim() !== "" ? debouncedSearch.trim() : undefined
      )
  });

  const errorMessage = uiErrorModule.resolveUiErrorMessage([
    metricsQuery.error,
    tenantsQuery.error
  ]);

  const metrics = metricsQuery.data;

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-brand-ink">Panel de Administración</h1>
        <p className="text-sm text-slate-500">Vista global de todos los tenants en Agendachat.</p>
      </div>

      {errorMessage !== null ? <errorBannerModule.ErrorBanner message={errorMessage} /> : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total Tenants" value={metrics?.tenantsCount ?? "—"} />
        <KpiCard label="Pacientes" value={metrics?.totalPatients ?? "—"} />
        <KpiCard label="Conversaciones hoy" value={metrics?.activeConversationsToday ?? "—"} />
        <KpiCard
          label="Ingresos mes (COP)"
          value={metrics !== undefined ? formatCop(metrics.totalRevenueCopThisMonth) : "—"}
        />
      </div>

      <div className="rounded-xl border border-border-subtle bg-white shadow-card">
        <header className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <h2 className="text-base font-semibold">Profesionales</h2>
          <div className="relative w-64">
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
              className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar tenant..."
              type="search"
              value={search}
            />
          </div>
        </header>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border-subtle bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3">Profesional</th>
                <th className="px-4 py-3">Pacientes</th>
                <th className="px-4 py-3">Conversaciones</th>
                <th className="px-4 py-3">Citas próx.</th>
                <th className="px-4 py-3">Pagos mes</th>
                <th className="px-4 py-3">Última actividad</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {tenantsQuery.isError ? (
                <tr>
                  <td className="px-4 py-6 text-sm text-slate-500" colSpan={8}>
                    No fue posible cargar los tenants.
                  </td>
                </tr>
              ) : tenantsQuery.isLoading ? (
                <tr>
                  <td className="px-4 py-6 text-sm text-slate-500" colSpan={8}>
                    Cargando tenants...
                  </td>
                </tr>
              ) : (tenantsQuery.data?.length ?? 0) === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-sm text-slate-500" colSpan={8}>
                    {debouncedSearch !== ""
                      ? "Sin resultados para la búsqueda."
                      : "No hay tenants registrados."}
                  </td>
                </tr>
              ) : null}
              {tenantsQuery.data?.map((tenant) => (
                <TenantRow key={tenant.tenantId} tenant={tenant} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

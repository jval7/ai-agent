import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import type * as adminModel from "@domain/models/admin";
import * as uiErrorModule from "@shared/http/ui_error";

function formatCop(amount: number): string {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0
  }).format(amount);
}

function MetricCard({
  label,
  value,
  sub
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-border-subtle bg-white p-5 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-brand-ink">{value}</p>
      {sub !== undefined ? <p className="mt-0.5 text-xs text-slate-500">{sub}</p> : null}
    </div>
  );
}

function ControlModeBar({ ai, human }: { ai: number; human: number }) {
  const total = ai + human;
  const aiPct = total > 0 ? Math.round((ai / total) * 100) : 0;
  const humanPct = 100 - aiPct;
  return (
    <div className="rounded-xl border border-border-subtle bg-white p-5 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
        Distribución control
      </p>
      <div className="mt-3 flex h-5 overflow-hidden rounded-full">
        <div
          className="bg-emerald-500 transition-all"
          style={{ width: `${aiPct.toString()}%` }}
          title={`AI: ${ai.toString()}`}
        />
        <div
          className="bg-amber-400 transition-all"
          style={{ width: `${humanPct.toString()}%` }}
          title={`Human: ${human.toString()}`}
        />
      </div>
      <div className="mt-2 flex justify-between text-xs text-slate-600">
        <span>
          AI: {ai} ({aiPct}%)
        </span>
        <span>
          Human: {human} ({humanPct}%)
        </span>
      </div>
    </div>
  );
}

function TopTenantsList({ tenants }: { tenants: adminModel.TenantSummary[] }) {
  if (tenants.length === 0) {
    return <p className="text-sm text-slate-500">Sin datos.</p>;
  }
  const max = tenants[0]?.conversationCount ?? 1;
  return (
    <div className="space-y-3">
      {tenants.map((t) => {
        const pct = max > 0 ? (t.conversationCount / max) * 100 : 0;
        return (
          <div key={t.tenantId}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <reactRouterDomModule.Link
                className="truncate font-medium text-brand-teal hover:underline"
                to={`/admin/tenants/${t.tenantId}`}
              >
                {t.professionalName}
              </reactRouterDomModule.Link>
              <span className="ml-4 shrink-0 text-slate-600">{t.conversationCount}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-2 rounded-full bg-brand-teal"
                style={{ width: `${pct.toString()}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function AdminGlobalDashboardPage() {
  const appContainer = appContainerContextModule.useAppContainer();

  const metricsQuery = reactQueryModule.useQuery({
    queryKey: ["admin", "global-metrics"],
    queryFn: () => appContainer.api.adminGetGlobalMetrics()
  });

  const errorMessage = uiErrorModule.resolveUiErrorMessage([metricsQuery.error]);
  const m = metricsQuery.data;

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-brand-ink">Dashboard Global</h1>
        <p className="text-sm text-slate-500">Métricas consolidadas de todos los tenants.</p>
      </div>

      {errorMessage !== null ? <errorBannerModule.ErrorBanner message={errorMessage} /> : null}

      {metricsQuery.isLoading ? (
        <p className="text-sm text-slate-500">Cargando métricas...</p>
      ) : null}

      {m !== undefined ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Tenants totales"
              value={m.tenantsCount}
              sub={`Activos: ${m.tenantsActive.toString()}`}
            />
            <MetricCard label="Pacientes" value={m.totalPatients} />
            <MetricCard
              label="Conversaciones"
              value={m.totalConversations}
              sub={`Hoy activas: ${m.activeConversationsToday.toString()}`}
            />
            <MetricCard label="Ingresos mes (COP)" value={formatCop(m.totalRevenueCopThisMonth)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-4">
              <MetricCard
                label="Recordatorios"
                value={m.totalReminders}
                sub={`Pendientes: ${m.pendingReminders.toString()}`}
              />
              <ControlModeBar
                ai={m.controlModeDistribution.ai}
                human={m.controlModeDistribution.human}
              />
            </div>

            <div className="rounded-xl border border-border-subtle bg-white p-5 shadow-card">
              <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Top tenants por conversaciones
              </p>
              <TopTenantsList tenants={m.topTenantsByConversations} />
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

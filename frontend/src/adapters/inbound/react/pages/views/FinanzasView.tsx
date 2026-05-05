import * as reactModule from "react";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import * as useFinanzasQueryModule from "@adapters/inbound/react/hooks/useFinanzasQuery";
import * as reactQueryModule from "@tanstack/react-query";
import type * as patientModel from "@domain/models/patient";
import type * as schedulingModel from "@domain/models/scheduling";

const colombiaTimezone = "America/Bogota";

type FinancePaymentStatusFilter = "ALL" | "PENDING" | "PAID";
type FinancePaymentMethodFilter = "ALL" | "CASH" | "TRANSFER";
type FinanceSourceFilter = "ALL" | "CHATBOT" | "MANUAL";
type FinanceCurrencyFilter = "ALL" | "COP" | "USD";
type FinancePaymentCurrency = "COP" | "USD";

interface FinanceAppointmentItem {
  itemKey: string;
  source: "CHATBOT" | "MANUAL";
  patientDisplayName: string;
  whatsappUserId: string;
  startAt: string;
  endAt: string;
  timezone: string;
  paymentAmount: number | null;
  paymentCurrency: FinancePaymentCurrency;
  paymentMethod: "CASH" | "TRANSFER" | null;
  paymentStatus: "PENDING" | "PAID";
  paymentUpdatedAt: string | null;
}

function formatPaymentAmount(value: number, currency: FinancePaymentCurrency): string {
  if (currency === "USD") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2
    }).format(value);
  }
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0
  }).format(value);
}

function buildPatientInitials(displayName: string): string {
  const parts = displayName
    .trim()
    .split(/\s+/)
    .filter((part) => part.length > 0);
  if (parts.length === 0) {
    return "·";
  }
  if (parts.length === 1) {
    return parts[0]!.slice(0, 2).toUpperCase();
  }
  return `${parts[0]![0] ?? ""}${parts[1]![0] ?? ""}`.toUpperCase();
}

function resolvePatientDisplayName(
  request: schedulingModel.SchedulingRequestSummary,
  patientMap?: Map<string, patientModel.Patient>
): string {
  const names = [request.patientFirstName, request.patientLastName]
    .map((value) => value?.trim() ?? "")
    .filter((value) => value !== "");
  if (names.length > 0) {
    return names.join(" ");
  }
  if (patientMap !== undefined) {
    const patient = patientMap.get(request.whatsappUserId);
    if (patient !== undefined) {
      const patientName = `${patient.firstName} ${patient.lastName}`.trim();
      if (patientName !== "") {
        return patientName;
      }
    }
  }
  return request.whatsappUserId;
}

function resolveBookedSlot(
  request: schedulingModel.SchedulingRequestSummary
): schedulingModel.SchedulingSlot | null {
  if (request.selectedSlotId !== null) {
    const selectedSlot = request.slots.find((slot) => slot.slotId === request.selectedSlotId);
    if (selectedSlot !== undefined) {
      return selectedSlot;
    }
  }
  const bookedSlot = request.slots.find((slot) => slot.status === "BOOKED");
  if (bookedSlot !== undefined) {
    return bookedSlot;
  }
  return null;
}

export function FinanzasView({ tenantId }: { tenantId?: string }) {
  const appContainer = appContainerContextModule.useAppContainer();

  const requestsQuery = useFinanzasQueryModule.useSchedulingRequestsQuery(tenantId);
  const patientsQuery = useFinanzasQueryModule.usePatientsForFinanzasQuery(tenantId);
  const manualAppointmentsQuery = useFinanzasQueryModule.useManualAppointmentsQuery(tenantId);

  const googleCalendarConnectionQuery = reactQueryModule.useQuery({
    queryKey: ["google-calendar-connection"],
    queryFn: () => appContainer.onboardingUseCase.getGoogleCalendarConnectionStatus(),
    enabled: tenantId === undefined
  });

  const allRequests = requestsQuery.data ?? [];
  const allPatients = patientsQuery.data ?? [];
  const allManualAppointments = manualAppointmentsQuery.data ?? [];
  const timezone =
    tenantId !== undefined
      ? Intl.DateTimeFormat().resolvedOptions().timeZone
      : (googleCalendarConnectionQuery.data?.professionalTimezone ?? "UTC");

  const [financeFromDate, setFinanceFromDate] = reactModule.useState<string>("");
  const [financeToDate, setFinanceToDate] = reactModule.useState<string>("");
  const [financePaymentStatusFilter, setFinancePaymentStatusFilter] =
    reactModule.useState<FinancePaymentStatusFilter>("ALL");
  const [financePaymentMethodFilter, setFinancePaymentMethodFilter] =
    reactModule.useState<FinancePaymentMethodFilter>("ALL");
  const [financeSourceFilter, setFinanceSourceFilter] =
    reactModule.useState<FinanceSourceFilter>("ALL");
  const [financeCurrencyFilter, setFinanceCurrencyFilter] =
    reactModule.useState<FinanceCurrencyFilter>("ALL");
  const [financeSearchTerm, setFinanceSearchTerm] = reactModule.useState<string>("");
  const [areFinanceFiltersOpen, setAreFinanceFiltersOpen] = reactModule.useState<boolean>(false);

  const patientsByWhatsappUserId = reactModule.useMemo(() => {
    const map = new Map<string, patientModel.Patient>();
    allPatients.forEach((patient) => {
      map.set(patient.whatsappUserId, patient);
    });
    return map;
  }, [allPatients]);

  const financeAppointments = reactModule.useMemo<FinanceAppointmentItem[]>(() => {
    const items: FinanceAppointmentItem[] = [];
    allRequests
      .filter((request) => request.status === "BOOKED" || request.status === "SESSION_CLOSED")
      .forEach((request) => {
        const bookedSlot = resolveBookedSlot(request);
        if (bookedSlot === null) {
          return;
        }
        items.push({
          itemKey: `finance-bot:${request.requestId}`,
          source: "CHATBOT",
          patientDisplayName: resolvePatientDisplayName(request, patientsByWhatsappUserId),
          whatsappUserId: request.whatsappUserId,
          startAt: bookedSlot.startAt,
          endAt: bookedSlot.endAt,
          timezone: bookedSlot.timezone.trim() === "" ? timezone : bookedSlot.timezone,
          paymentAmount: request.paymentAmountCop ?? null,
          paymentCurrency: request.paymentCurrency ?? "COP",
          paymentMethod: request.paymentMethod ?? null,
          paymentStatus: request.paymentStatus ?? "PENDING",
          paymentUpdatedAt: request.paymentUpdatedAt ?? null
        });
      });

    allManualAppointments
      .filter((appointment) => appointment.status === "SCHEDULED")
      .forEach((appointment) => {
        const patient = patientsByWhatsappUserId.get(appointment.patientWhatsappUserId);
        items.push({
          itemKey: `finance-manual:${appointment.appointmentId}`,
          source: "MANUAL",
          patientDisplayName:
            patient === undefined
              ? appointment.patientWhatsappUserId
              : `${patient.firstName} ${patient.lastName}`,
          whatsappUserId: appointment.patientWhatsappUserId,
          startAt: appointment.startAt,
          endAt: appointment.endAt,
          timezone: appointment.timezone.trim() === "" ? colombiaTimezone : appointment.timezone,
          paymentAmount: appointment.paymentAmountCop ?? null,
          paymentCurrency: appointment.paymentCurrency ?? "COP",
          paymentMethod: appointment.paymentMethod ?? null,
          paymentStatus: appointment.paymentStatus ?? "PENDING",
          paymentUpdatedAt: appointment.paymentUpdatedAt ?? null
        });
      });

    return items.sort((left, right) => left.startAt.localeCompare(right.startAt));
  }, [allManualAppointments, allRequests, patientsByWhatsappUserId, timezone]);

  const filteredFinanceAppointments = reactModule.useMemo(() => {
    const normalizedSearchTerm = financeSearchTerm.trim().toLowerCase();
    return financeAppointments.filter((appointment) => {
      const startDate = luxonModule.DateTime.fromISO(appointment.startAt, {
        zone: appointment.timezone
      }).toISODate();
      if (startDate === null) {
        return false;
      }
      if (financeFromDate !== "" && startDate < financeFromDate) {
        return false;
      }
      if (financeToDate !== "" && startDate > financeToDate) {
        return false;
      }
      if (
        financePaymentStatusFilter !== "ALL" &&
        appointment.paymentStatus !== financePaymentStatusFilter
      ) {
        return false;
      }
      if (
        financePaymentMethodFilter !== "ALL" &&
        appointment.paymentMethod !== financePaymentMethodFilter
      ) {
        return false;
      }
      if (financeSourceFilter !== "ALL" && appointment.source !== financeSourceFilter) {
        return false;
      }
      if (
        financeCurrencyFilter !== "ALL" &&
        appointment.paymentCurrency !== financeCurrencyFilter
      ) {
        return false;
      }
      if (normalizedSearchTerm === "") {
        return true;
      }
      const patientName = appointment.patientDisplayName.toLowerCase();
      const whatsappUserId = appointment.whatsappUserId.toLowerCase();
      return (
        patientName.includes(normalizedSearchTerm) || whatsappUserId.includes(normalizedSearchTerm)
      );
    });
  }, [
    financeAppointments,
    financeCurrencyFilter,
    financeFromDate,
    financePaymentMethodFilter,
    financePaymentStatusFilter,
    financeSearchTerm,
    financeSourceFilter,
    financeToDate
  ]);

  const financeMetrics = reactModule.useMemo(() => {
    const totalAppointments = filteredFinanceAppointments.length;
    const pendingAppointments = filteredFinanceAppointments.filter(
      (appointment) => appointment.paymentStatus === "PENDING"
    ).length;
    const paidAppointments = filteredFinanceAppointments.filter(
      (appointment) => appointment.paymentStatus === "PAID"
    ).length;
    const byCurrency: Record<
      FinancePaymentCurrency,
      { totalPaid: number; paidCount: number; pendingCount: number }
    > = {
      COP: { totalPaid: 0, paidCount: 0, pendingCount: 0 },
      USD: { totalPaid: 0, paidCount: 0, pendingCount: 0 }
    };
    filteredFinanceAppointments.forEach((appointment) => {
      const bucket = byCurrency[appointment.paymentCurrency];
      if (appointment.paymentStatus === "PAID") {
        bucket.paidCount += 1;
        if (appointment.paymentAmount !== null) {
          bucket.totalPaid += appointment.paymentAmount;
        }
      } else {
        bucket.pendingCount += 1;
      }
    });
    return {
      totalAppointments,
      pendingAppointments,
      paidAppointments,
      byCurrency
    };
  }, [filteredFinanceAppointments]);

  const financeActiveFilterCount = reactModule.useMemo(() => {
    let count = 0;
    if (financeFromDate !== "") count += 1;
    if (financeToDate !== "") count += 1;
    if (financePaymentStatusFilter !== "ALL") count += 1;
    if (financePaymentMethodFilter !== "ALL") count += 1;
    if (financeSourceFilter !== "ALL") count += 1;
    if (financeCurrencyFilter !== "ALL") count += 1;
    if (financeSearchTerm.trim() !== "") count += 1;
    return count;
  }, [
    financeCurrencyFilter,
    financeFromDate,
    financePaymentMethodFilter,
    financePaymentStatusFilter,
    financeSearchTerm,
    financeSourceFilter,
    financeToDate
  ]);

  return (
    <section className="mt-4 space-y-4 sm:mt-6">
      <article className="rounded-xl border border-border-subtle bg-white p-3 shadow-card sm:p-4">
        <header className="mb-4">
          <h3 className="text-base font-semibold text-brand-ink sm:text-lg">Finanzas</h3>
          <p className="text-[11px] text-slate-500 sm:text-xs">
            Seguimiento de pagos por moneda — citas del chatbot y manuales.
          </p>
        </header>

        <section aria-label="Resumen por moneda" className="grid gap-3 sm:grid-cols-2">
          {[
            { currency: "COP" as const, bucket: financeMetrics.byCurrency.COP },
            { currency: "USD" as const, bucket: financeMetrics.byCurrency.USD }
          ].map(({ currency, bucket }) => {
            const isCop = currency === "COP";
            const flag = isCop ? "🇨🇴" : "🇺🇸";
            const label = isCop ? "Total COP" : "Total USD";
            const cardTone = isCop
              ? "border-emerald-200 bg-emerald-50"
              : "border-sky-200 bg-sky-50";
            const accentTone = isCop ? "text-emerald-800" : "text-sky-800";
            const subtleTone = isCop ? "text-emerald-700/80" : "text-sky-700/80";
            return (
              <article className={`rounded-2xl border p-4 sm:p-5 ${cardTone}`} key={currency}>
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`text-[11px] font-semibold uppercase tracking-wider ${subtleTone}`}
                  >
                    {label}
                  </span>
                  <span aria-hidden="true" className="text-xl leading-none">
                    {flag}
                  </span>
                </div>
                <p className={`mt-2 text-2xl font-bold tracking-tight sm:text-3xl ${accentTone}`}>
                  {formatPaymentAmount(bucket.totalPaid, currency)}
                </p>
                <dl className={`mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs ${subtleTone}`}>
                  <div className="flex items-center gap-1">
                    <dt className="font-semibold uppercase tracking-wide">Pagadas</dt>
                    <dd className={`font-bold ${accentTone}`}>{bucket.paidCount}</dd>
                  </div>
                  <div className="flex items-center gap-1">
                    <dt className="font-semibold uppercase tracking-wide">Pendientes</dt>
                    <dd className={`font-bold ${accentTone}`}>{bucket.pendingCount}</dd>
                  </div>
                </dl>
              </article>
            );
          })}
        </section>

        <section
          aria-label="Indicadores generales"
          className="mt-3 grid grid-cols-3 gap-2 sm:gap-3"
        >
          <article className="rounded-xl border border-border-subtle bg-slate-50 p-3 text-center">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Citas
            </p>
            <p className="mt-1 text-lg font-bold text-brand-ink sm:text-xl">
              {financeMetrics.totalAppointments}
            </p>
          </article>
          <article className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-center">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-700">
              Pendientes
            </p>
            <p className="mt-1 text-lg font-bold text-amber-800 sm:text-xl">
              {financeMetrics.pendingAppointments}
            </p>
          </article>
          <article className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-center">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
              Pagadas
            </p>
            <p className="mt-1 text-lg font-bold text-emerald-800 sm:text-xl">
              {financeMetrics.paidAppointments}
            </p>
          </article>
        </section>

        <section className="mt-4 rounded-xl border border-border-subtle bg-slate-50/60">
          <button
            aria-expanded={areFinanceFiltersOpen}
            className="flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-brand-ink transition-colors hover:bg-slate-100/80"
            onClick={() => setAreFinanceFiltersOpen((current) => !current)}
            type="button"
          >
            <span className="flex items-center gap-2">
              <span aria-hidden="true">🔍</span>
              <span>Filtros</span>
              {financeActiveFilterCount > 0 ? (
                <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-teal px-1.5 text-[11px] font-bold text-white">
                  {financeActiveFilterCount}
                </span>
              ) : null}
            </span>
            <span
              aria-hidden="true"
              className={`text-xs text-slate-500 transition-transform ${areFinanceFiltersOpen ? "rotate-180" : ""}`}
            >
              ▾
            </span>
          </button>
          {areFinanceFiltersOpen ? (
            <div className="space-y-3 border-t border-border-subtle px-3 py-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Desde
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle bg-white px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => setFinanceFromDate(event.target.value)}
                    type="date"
                    value={financeFromDate}
                  />
                </label>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Hasta
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle bg-white px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => setFinanceToDate(event.target.value)}
                    type="date"
                    value={financeToDate}
                  />
                </label>
              </div>

              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Moneda
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {(
                    [
                      { value: "ALL", label: "Todas" },
                      { value: "COP", label: "🇨🇴 COP" },
                      { value: "USD", label: "🇺🇸 USD" }
                    ] as const
                  ).map((option) => {
                    const isActive = financeCurrencyFilter === option.value;
                    return (
                      <button
                        className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                          isActive
                            ? "bg-brand-teal text-white shadow-sm"
                            : "border border-border-subtle bg-white text-slate-600 hover:bg-slate-100"
                        }`}
                        key={option.value}
                        onClick={() =>
                          setFinanceCurrencyFilter(option.value as FinanceCurrencyFilter)
                        }
                        type="button"
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Estado
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {(
                    [
                      { value: "ALL", label: "Todos" },
                      { value: "PAID", label: "Pagadas" },
                      { value: "PENDING", label: "Pendientes" }
                    ] as const
                  ).map((option) => {
                    const isActive = financePaymentStatusFilter === option.value;
                    return (
                      <button
                        className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                          isActive
                            ? "bg-brand-teal text-white shadow-sm"
                            : "border border-border-subtle bg-white text-slate-600 hover:bg-slate-100"
                        }`}
                        key={option.value}
                        onClick={() =>
                          setFinancePaymentStatusFilter(option.value as FinancePaymentStatusFilter)
                        }
                        type="button"
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Origen
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {(
                    [
                      { value: "ALL", label: "Todos" },
                      { value: "CHATBOT", label: "Chatbot" },
                      { value: "MANUAL", label: "Manual" }
                    ] as const
                  ).map((option) => {
                    const isActive = financeSourceFilter === option.value;
                    return (
                      <button
                        className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                          isActive
                            ? "bg-brand-teal text-white shadow-sm"
                            : "border border-border-subtle bg-white text-slate-600 hover:bg-slate-100"
                        }`}
                        key={option.value}
                        onClick={() => setFinanceSourceFilter(option.value as FinanceSourceFilter)}
                        type="button"
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Método de pago
                <select
                  className="mt-1 w-full rounded-lg border border-border-subtle bg-white px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                  onChange={(event) =>
                    setFinancePaymentMethodFilter(event.target.value as FinancePaymentMethodFilter)
                  }
                  value={financePaymentMethodFilter}
                >
                  <option value="ALL">Todos</option>
                  <option value="CASH">Efectivo</option>
                  <option value="TRANSFER">Transferencia</option>
                </select>
              </label>

              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Buscar paciente
                <input
                  className="mt-1 w-full rounded-lg border border-border-subtle bg-white px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                  onChange={(event) => setFinanceSearchTerm(event.target.value)}
                  placeholder="Nombre o WhatsApp"
                  type="text"
                  value={financeSearchTerm}
                />
              </label>

              {financeActiveFilterCount > 0 ? (
                <button
                  className="text-xs font-semibold text-brand-teal hover:underline"
                  onClick={() => {
                    setFinanceFromDate("");
                    setFinanceToDate("");
                    setFinancePaymentStatusFilter("ALL");
                    setFinancePaymentMethodFilter("ALL");
                    setFinanceSourceFilter("ALL");
                    setFinanceCurrencyFilter("ALL");
                    setFinanceSearchTerm("");
                  }}
                  type="button"
                >
                  Limpiar filtros
                </button>
              ) : null}
            </div>
          ) : null}
        </section>

        <section className="mt-4">
          <div className="mb-2 flex items-baseline justify-between">
            <h4 className="text-sm font-semibold text-brand-ink">Detalle de citas</h4>
            <span className="text-[11px] text-slate-500">
              {filteredFinanceAppointments.length}{" "}
              {filteredFinanceAppointments.length === 1 ? "registro" : "registros"}
            </span>
          </div>
          {filteredFinanceAppointments.length === 0 ? (
            <p className="rounded-xl border border-dashed border-border-subtle bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
              No hay citas que coincidan con los filtros seleccionados.
            </p>
          ) : (
            <div className="space-y-2">
              {filteredFinanceAppointments.map((appointment) => {
                const startAt = luxonModule.DateTime.fromISO(appointment.startAt, {
                  zone: appointment.timezone
                });
                const endAt = luxonModule.DateTime.fromISO(appointment.endAt, {
                  zone: appointment.timezone
                });
                const dateText =
                  !startAt.isValid || !endAt.isValid
                    ? "—"
                    : `${startAt.toFormat("dd LLL yyyy")} · ${startAt.toFormat("HH:mm")}–${endAt.toFormat("HH:mm")}`;
                const paymentMethodLabel =
                  appointment.paymentMethod === "CASH"
                    ? "Efectivo"
                    : appointment.paymentMethod === "TRANSFER"
                      ? "Transferencia"
                      : "—";
                const paymentStatusLabel =
                  appointment.paymentStatus === "PAID" ? "Pagada" : "Pendiente";
                const amountText =
                  appointment.paymentAmount === null
                    ? "—"
                    : formatPaymentAmount(appointment.paymentAmount, appointment.paymentCurrency);
                const sourceTone =
                  appointment.source === "CHATBOT"
                    ? "bg-brand-accent-light text-brand-teal"
                    : "bg-slate-100 text-slate-600";
                const currencyTone =
                  appointment.paymentCurrency === "COP"
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-sky-50 text-sky-700";
                return (
                  <article
                    className="rounded-2xl border border-border-subtle bg-white p-3 shadow-sm transition-shadow hover:shadow-md sm:p-4"
                    key={appointment.itemKey}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-accent-light text-xs font-bold text-brand-teal">
                        {buildPatientInitials(appointment.patientDisplayName)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-brand-ink">
                              {appointment.patientDisplayName}
                            </p>
                            <p className="truncate text-[11px] text-slate-500">
                              {appointment.whatsappUserId}
                            </p>
                          </div>
                          <statusBadgeModule.StatusBadge
                            label={paymentStatusLabel}
                            tone={appointment.paymentStatus === "PAID" ? "success" : "warning"}
                          />
                        </div>
                        <p className="mt-2 text-xs text-slate-600">
                          <span aria-hidden="true">📅 </span>
                          {dateText}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-wrap gap-1.5">
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${sourceTone}`}
                            >
                              {appointment.source === "CHATBOT" ? "Chatbot" : "Manual"}
                            </span>
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${currencyTone}`}
                            >
                              {appointment.paymentCurrency}
                            </span>
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                              {paymentMethodLabel}
                            </span>
                          </div>
                          <p className="text-sm font-bold text-brand-ink">{amountText}</p>
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </article>
    </section>
  );
}

import * as luxonModule from "luxon";

export interface AppointmentDetailCardPayment {
  status: "PAID" | "PENDING" | null;
  amountCop: number | null;
  currency?: "COP" | "USD" | null;
  category: string | null;
}

export interface AppointmentDetailCardPaymentDraft {
  amountCop: string;
  category: string;
}

export interface AppointmentDetailCardProps {
  origin: "MANUAL" | "CHATBOT";
  modality: "VIRTUAL" | "PRESENCIAL";
  patientFullName: string;
  summary: string | null;
  startAt: string;
  endAt: string;
  timezone: string;
  durationMinutes: number;
  payment: AppointmentDetailCardPayment;
  paymentDraft: AppointmentDetailCardPaymentDraft;
  onPaymentDraftChange: (draft: AppointmentDetailCardPaymentDraft) => void;
  isSavingPayment: boolean;
  onSavePayment: () => void;
  onReschedule: () => void;
  onCancel: () => void;
  errorMessage: string | null;
  successMessage: string | null;
}

function formatCopAmount(value: number): string {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0
  }).format(value);
}

function formatDateSpanish(isoDate: string, tz: string): string {
  const dt = luxonModule.DateTime.fromISO(isoDate, { setZone: true }).setZone(tz);
  if (!dt.isValid) {
    return "-";
  }
  return dt.setLocale("es").toFormat("EEE dd LLL yyyy");
}

function formatTimeRange(startIso: string, endIso: string, tz: string): string {
  const start = luxonModule.DateTime.fromISO(startIso, { setZone: true }).setZone(tz);
  const end = luxonModule.DateTime.fromISO(endIso, { setZone: true }).setZone(tz);
  if (!start.isValid || !end.isValid) {
    return "-";
  }
  const tzAbbrev = start.toFormat("ZZZZ");
  return `${start.toFormat("HH:mm")} \u2013 ${end.toFormat("HH:mm")} (${tzAbbrev})`;
}

export function AppointmentDetailCard({
  origin,
  modality,
  patientFullName,
  summary,
  startAt,
  endAt,
  timezone,
  durationMinutes,
  payment,
  paymentDraft,
  onPaymentDraftChange,
  isSavingPayment,
  onSavePayment,
  onReschedule,
  onCancel,
  errorMessage,
  successMessage
}: AppointmentDetailCardProps) {
  const isVirtual = modality === "VIRTUAL";
  const isPaid = payment.status === "PAID";

  return (
    <div className="space-y-5 px-5 py-5">
      {/* Kicker row */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-bold uppercase tracking-widest text-brand-teal">
          {origin === "MANUAL" ? "Cita manual" : "Cita chatbot"}
        </span>
        <span
          className={[
            "rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
            isVirtual ? "bg-brand-accent-light text-brand-teal" : "bg-slate-100 text-slate-600"
          ].join(" ")}
        >
          {isVirtual ? "Google Meet" : "Presencial"}
        </span>
      </div>

      {/* Patient name */}
      <div>
        <h2 className="font-display text-[22px] font-semibold leading-snug text-brand-ink">
          {patientFullName}
        </h2>
        <p className="mt-0.5 text-sm text-slate-500">{summary ?? "Sin motivo"}</p>
      </div>

      <hr className="border-border-subtle" />

      {/* Metadata grid */}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Fecha</dt>
          <dd className="mt-0.5 text-sm font-medium capitalize text-brand-ink">
            {formatDateSpanish(startAt, timezone)}
          </dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Hora</dt>
          <dd className="mt-0.5 text-sm font-medium text-brand-ink">
            {formatTimeRange(startAt, endAt, timezone)}
          </dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
            Duración
          </dt>
          <dd className="mt-0.5 text-sm font-medium text-brand-ink">{durationMinutes} min</dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Origen</dt>
          <dd className="mt-0.5 text-sm font-medium text-brand-ink">
            {origin === "MANUAL" ? "Agendamiento manual" : "Chatbot"}
          </dd>
        </div>
      </dl>

      <hr className="border-border-subtle" />

      {/* Pago section */}
      <section>
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Pago</p>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-600">Estado</span>
          <span
            className={[
              "rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
              isPaid ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
            ].join(" ")}
          >
            {isPaid ? "Pagado" : "Pendiente por pago"}
          </span>
        </div>
        {isPaid ? (
          <div className="mt-3 space-y-1 text-sm text-slate-700">
            {payment.amountCop !== null ? (
              <p>
                <span className="font-semibold">Valor:</span> {formatCopAmount(payment.amountCop)}{" "}
                {payment.currency ?? "COP"}
              </p>
            ) : null}
            {payment.category !== null ? (
              <p>
                <span className="font-semibold">Categoría:</span> {payment.category}
              </p>
            ) : null}
          </div>
        ) : (
          <div className="mt-3 space-y-3">
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Valor (COP)
              <input
                aria-label="Valor (COP)"
                className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                min={1}
                onChange={(event) => {
                  onPaymentDraftChange({ ...paymentDraft, amountCop: event.target.value });
                }}
                type="number"
                value={paymentDraft.amountCop}
              />
            </label>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Categoría
              <select
                aria-label="Categoría de pago"
                className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                onChange={(event) => {
                  onPaymentDraftChange({ ...paymentDraft, category: event.target.value });
                }}
                value={paymentDraft.category}
              >
                <option value="CASH">Efectivo</option>
                <option value="TRANSFER">Transferencia</option>
                <option value="CARD">Tarjeta</option>
                <option value="OTHER">Otro</option>
              </select>
            </label>
            <div className="flex justify-end">
              <button
                className="rounded-lg bg-brand-teal px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isSavingPayment}
                onClick={onSavePayment}
                type="button"
              >
                {isSavingPayment ? "Registrando..." : "Registrar pago"}
              </button>
            </div>
          </div>
        )}
      </section>

      <hr className="border-border-subtle" />

      {/* Acciones section */}
      <section className="space-y-2">
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Acciones</p>

        {errorMessage !== null ? (
          <div className="rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </div>
        ) : null}
        {successMessage !== null ? (
          <div className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {successMessage}
          </div>
        ) : null}

        <button
          className="flex w-full items-center gap-2 rounded-lg border border-brand-teal px-4 py-2.5 text-sm font-semibold text-brand-teal transition-colors hover:bg-brand-accent-light"
          onClick={onReschedule}
          type="button"
        >
          <svg
            className="h-4 w-4 shrink-0"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
            />
          </svg>
          Reprogramar cita
        </button>

        <button
          className="flex w-full items-center gap-2 rounded-lg border border-rose-500 px-4 py-2.5 text-sm font-semibold text-rose-600 transition-colors hover:bg-rose-50"
          onClick={onCancel}
          type="button"
        >
          <svg
            className="h-4 w-4 shrink-0"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
          Cancelar cita
        </button>
      </section>
    </div>
  );
}

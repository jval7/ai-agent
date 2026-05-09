import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as patientComboboxModule from "@adapters/inbound/react/components/PatientCombobox";
import * as slotPickerModule from "@adapters/inbound/react/components/SlotPicker";
import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import * as calendarUtilsModule from "@shared/utils/calendar";

const colombiaTimezone = "America/Bogota";
const manualAppointmentsQueryKey = ["manual-appointments"] as const;

type PaymentCurrency = "COP" | "USD";
type PaymentStatus = "PENDING" | "PAID";
type PaymentMethod = "CASH" | "TRANSFER";

interface ModalFormState {
  patientWhatsappUserId: string;
  selectedSlots: { slotId: string; startAt: string; endAt: string; timezone: string }[];
  summary: string;
  isVirtual: boolean;
  paymentAmountRaw: string;
  paymentCurrency: PaymentCurrency;
  paymentStatus: PaymentStatus;
  paymentMethod: PaymentMethod | "";
}

function emptyForm(): ModalFormState {
  return {
    patientWhatsappUserId: "",
    selectedSlots: [],
    summary: "",
    isVirtual: true,
    paymentAmountRaw: "",
    paymentCurrency: "COP",
    paymentStatus: "PENDING",
    paymentMethod: ""
  };
}

export interface NewManualAppointmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
  tenantId?: string;
}

const inputClass =
  "mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20";
const sectionLabelClass = "text-[10px] font-bold uppercase tracking-widest text-brand-teal";
const fieldLabelClass = "text-xs font-semibold uppercase tracking-wide text-slate-500";
const dividerClass = "border-t border-border-subtle";

export function NewManualAppointmentModal({
  isOpen,
  onClose,
  onCreated,
  tenantId
}: NewManualAppointmentModalProps) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const [formState, setFormState] = reactModule.useState<ModalFormState>(emptyForm());
  const [errorMessage, setErrorMessage] = reactModule.useState<string | null>(null);
  const [successMessage, setSuccessMessage] = reactModule.useState<string | null>(null);
  const [paymentAmountError, setPaymentAmountError] = reactModule.useState<string | null>(null);
  const [paymentMethodError, setPaymentMethodError] = reactModule.useState<string | null>(null);
  const [slotPickerMonth, setSlotPickerMonth] = reactModule.useState<{
    year: number;
    month: number;
  }>(() => {
    const now = luxonModule.DateTime.now().setZone(colombiaTimezone);
    return { year: now.year, month: now.month };
  });

  const slotPickerMonthStart = luxonModule.DateTime.fromObject(
    { year: slotPickerMonth.year, month: slotPickerMonth.month, day: 1 },
    { zone: colombiaTimezone }
  );
  const slotPickerMonthEnd = slotPickerMonthStart.plus({ months: 1 });
  const slotPickerMonthFromIso = slotPickerMonthStart.toISO();
  const slotPickerMonthToIso = slotPickerMonthEnd.toISO();

  const availabilityQueryKey =
    tenantId !== undefined
      ? [
          "admin",
          tenantId,
          "google-calendar-availability",
          "modal-manual",
          slotPickerMonthFromIso,
          slotPickerMonthToIso
        ]
      : [
          "google-calendar-availability",
          "modal-manual",
          slotPickerMonthFromIso,
          slotPickerMonthToIso
        ];

  const availabilityQuery = reactQueryModule.useQuery({
    queryKey: availabilityQueryKey,
    enabled: isOpen && slotPickerMonthFromIso !== null && slotPickerMonthToIso !== null,
    queryFn: () =>
      tenantId !== undefined
        ? appContainer.api.adminGetGoogleCalendarAvailability(
            tenantId,
            slotPickerMonthFromIso!,
            slotPickerMonthToIso!
          )
        : appContainer.schedulingUseCase.getAvailability(
            slotPickerMonthFromIso!,
            slotPickerMonthToIso!
          )
  });

  const busyIntervals = reactModule.useMemo<calendarUtilsModule.BusyIntervalRange[]>(() => {
    if (availabilityQuery.data === undefined) {
      return [];
    }
    return calendarUtilsModule.parseBusyIntervals(
      availabilityQuery.data.busyIntervals,
      colombiaTimezone
    );
  }, [availabilityQuery.data]);

  const manualAppointmentsKey =
    tenantId !== undefined
      ? ["admin", tenantId, "manual-appointments"]
      : manualAppointmentsQueryKey;

  const createAppointmentMutation = reactQueryModule.useMutation({
    mutationFn: (input: manualAppointmentModel.CreateManualAppointmentInput) =>
      tenantId !== undefined
        ? appContainer.api.adminCreateManualAppointment(tenantId, input)
        : appContainer.manualAppointmentUseCase.createAppointment(input),
    onSuccess: async () => {
      setSuccessMessage("Cita creada correctamente.");
      setErrorMessage(null);
      await queryClient.invalidateQueries({ queryKey: manualAppointmentsKey });
      onCreated();
      handleClose();
    },
    onError: () => {
      setErrorMessage("Error al crear la cita. Intenta de nuevo.");
    }
  });

  const handleClose = reactModule.useCallback(() => {
    setFormState(emptyForm());
    setErrorMessage(null);
    setSuccessMessage(null);
    setPaymentAmountError(null);
    setPaymentMethodError(null);
    onClose();
  }, [onClose]);

  reactModule.useEffect(() => {
    if (!isOpen) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        handleClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, handleClose]);

  const handleBackdropClick = (event: reactModule.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  };

  const handleSubmit = () => {
    setPaymentAmountError(null);
    setPaymentMethodError(null);
    setErrorMessage(null);

    const slot = formState.selectedSlots[formState.selectedSlots.length - 1];
    if (formState.patientWhatsappUserId === "") {
      setErrorMessage("Debes seleccionar un paciente.");
      return;
    }
    if (slot === undefined) {
      setErrorMessage("Debes seleccionar un horario.");
      return;
    }
    const parsedAmount = Number.parseInt(formState.paymentAmountRaw.replace(/\D/g, ""), 10);
    if (Number.isNaN(parsedAmount) || parsedAmount <= 0) {
      setPaymentAmountError("El valor de la consulta debe ser mayor a cero.");
      return;
    }
    if (formState.paymentStatus === "PAID" && formState.paymentMethod === "") {
      setPaymentMethodError("Debes seleccionar una categoría de pago.");
      return;
    }

    createAppointmentMutation.mutate({
      patientWhatsappUserId: formState.patientWhatsappUserId,
      startAt: slot.startAt,
      endAt: slot.endAt,
      timezone: slot.timezone,
      summary: formState.summary.trim() === "" ? null : formState.summary.trim(),
      isVirtual: formState.isVirtual,
      paymentAmountCop: parsedAmount,
      paymentCurrency: formState.paymentCurrency,
      paymentStatus: formState.paymentStatus,
      paymentMethod:
        formState.paymentStatus === "PAID" && formState.paymentMethod !== ""
          ? formState.paymentMethod
          : null
    });
  };

  if (!isOpen) {
    return null;
  }

  const isPending = createAppointmentMutation.isPending;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-0 sm:px-4 sm:py-6"
      data-testid="new-manual-appointment-modal"
      onClick={handleBackdropClick}
    >
      <div className="flex h-full w-full max-h-full flex-col overflow-hidden bg-white sm:h-auto sm:max-h-[90vh] sm:w-full sm:max-w-2xl sm:rounded-xl sm:border sm:border-border-subtle sm:shadow-xl">
        {/* Header */}
        <div className="flex shrink-0 items-start justify-between border-b border-border-subtle px-5 py-4">
          <div>
            <h2 className="font-display text-base font-semibold text-brand-ink">
              Nueva cita manual
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Selecciona un paciente, el horario y el pago de la consulta.
            </p>
          </div>
          <button
            className="ml-4 shrink-0 rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
            onClick={handleClose}
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

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Sección Paciente */}
          <section className="space-y-3">
            <p className={sectionLabelClass}>Paciente</p>
            <label className={`${fieldLabelClass} block`}>
              Seleccionar paciente
              <div className="mt-1">
                <patientComboboxModule.PatientCombobox
                  onChange={(patient) => {
                    setFormState((current) => ({
                      ...current,
                      patientWhatsappUserId: patient?.whatsappUserId ?? ""
                    }));
                  }}
                  placeholder="Buscar por nombre o teléfono..."
                  value={
                    formState.patientWhatsappUserId === "" ? null : formState.patientWhatsappUserId
                  }
                />
              </div>
            </label>
            <div className={dividerClass} />
          </section>

          {/* Sección Fecha y hora */}
          <section className="space-y-3">
            <p className={sectionLabelClass}>Fecha y hora</p>
            <slotPickerModule.SlotPicker
              busyIntervals={busyIntervals}
              isLoadingAvailability={availabilityQuery.isFetching}
              onMonthChange={setSlotPickerMonth}
              onSelectedSlotsChange={(slots) => {
                setFormState((current) => ({
                  ...current,
                  selectedSlots: slots.slice(-1)
                }));
              }}
              requestId="modal-manual"
              selectedSlots={formState.selectedSlots}
              timezone={colombiaTimezone}
            />
            <div className={dividerClass} />
          </section>

          {/* Sección Detalles */}
          <section className="space-y-3">
            <p className={sectionLabelClass}>Detalles</p>
            <label className={`${fieldLabelClass} block`} htmlFor="modal-summary">
              Motivo de consulta
              <textarea
                className={`${inputClass} min-h-20 resize-none`}
                id="modal-summary"
                onChange={(event) => {
                  setFormState((current) => ({ ...current, summary: event.target.value }));
                }}
                placeholder="Ej. Consulta de seguimiento"
                rows={3}
                value={formState.summary}
              />
            </label>
            <div className={dividerClass} />
          </section>

          {/* Sección Pago */}
          <section className="space-y-3">
            <p className={sectionLabelClass}>Pago</p>
            {/* Row A: amount + currency | payment status */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {/* Valor consulta + moneda */}
              <div>
                <p className={fieldLabelClass}>
                  Valor consulta <span className="text-red-500">*</span>
                </p>
                <div className="mt-1 flex gap-2">
                  <input
                    className={[
                      "flex-1 rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2",
                      paymentAmountError !== null
                        ? "border-rose-400 focus:border-rose-400 focus:ring-rose-200"
                        : "border-border-subtle focus:border-brand-teal focus:ring-brand-teal/20"
                    ].join(" ")}
                    min={1}
                    onChange={(event) => {
                      setFormState((current) => ({
                        ...current,
                        paymentAmountRaw: event.target.value
                      }));
                      setPaymentAmountError(null);
                    }}
                    placeholder="120000"
                    type="number"
                    value={formState.paymentAmountRaw}
                  />
                  {/* Currency segmented control */}
                  <div className="flex overflow-hidden rounded-lg border border-border-subtle text-xs font-semibold">
                    {(["COP", "USD"] as PaymentCurrency[]).map((curr) => (
                      <button
                        className={[
                          "px-3 py-2 transition-colors",
                          formState.paymentCurrency === curr
                            ? "bg-brand-teal text-white"
                            : "bg-white text-slate-600 hover:bg-slate-50"
                        ].join(" ")}
                        key={curr}
                        onClick={() => {
                          setFormState((current) => ({ ...current, paymentCurrency: curr }));
                        }}
                        type="button"
                      >
                        {curr}
                      </button>
                    ))}
                  </div>
                </div>
                {paymentAmountError !== null ? (
                  <p className="mt-1 text-[11px] text-rose-600">{paymentAmountError}</p>
                ) : null}
              </div>

              {/* Estado del pago */}
              <div>
                <p className={fieldLabelClass}>Estado del pago</p>
                <div className="mt-1 flex overflow-hidden rounded-lg border border-border-subtle text-sm font-semibold">
                  {(["PENDING", "PAID"] as PaymentStatus[]).map((status) => {
                    const label = status === "PENDING" ? "Pendiente" : "Pagado";
                    return (
                      <button
                        className={[
                          "flex-1 px-3 py-2 transition-colors",
                          formState.paymentStatus === status
                            ? "bg-brand-teal text-white"
                            : "bg-white text-slate-600 hover:bg-slate-50"
                        ].join(" ")}
                        key={status}
                        onClick={() => {
                          setFormState((current) => ({
                            ...current,
                            paymentStatus: status,
                            paymentMethod: ""
                          }));
                          setPaymentMethodError(null);
                        }}
                        type="button"
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Row B: payment method — only when PAID */}
            {formState.paymentStatus === "PAID" ? (
              <label className={`${fieldLabelClass} block`} htmlFor="modal-payment-method">
                Categoría de pago
                <select
                  className={[
                    inputClass,
                    paymentMethodError !== null
                      ? "border-rose-400 focus:border-rose-400 focus:ring-rose-200"
                      : ""
                  ].join(" ")}
                  id="modal-payment-method"
                  onChange={(event) => {
                    setFormState((current) => ({
                      ...current,
                      paymentMethod: event.target.value as PaymentMethod | ""
                    }));
                    setPaymentMethodError(null);
                  }}
                  value={formState.paymentMethod}
                >
                  <option value="">-- Selecciona --</option>
                  <option value="CASH">Efectivo</option>
                  <option value="TRANSFER">Transferencia</option>
                </select>
                {paymentMethodError !== null ? (
                  <p className="mt-1 text-[11px] text-rose-600">{paymentMethodError}</p>
                ) : null}
              </label>
            ) : null}

            <div className={dividerClass} />
          </section>

          {/* Toggle Cita virtual */}
          <section>
            <button
              className="flex w-full items-center justify-between rounded-lg border border-border-subtle px-3 py-2.5 transition-colors hover:bg-slate-50"
              onClick={() => {
                setFormState((current) => ({ ...current, isVirtual: !current.isVirtual }));
              }}
              type="button"
            >
              <div className="text-left">
                <p className="text-sm font-semibold text-brand-ink">Cita virtual (Google Meet)</p>
                <p className="text-xs text-slate-500">Se generará un enlace automáticamente.</p>
              </div>
              <div
                className={[
                  "relative ml-4 h-6 w-11 shrink-0 rounded-full transition-colors",
                  formState.isVirtual ? "bg-brand-teal" : "bg-slate-300"
                ].join(" ")}
              >
                <span
                  className={[
                    "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
                    formState.isVirtual ? "left-5" : "left-0.5"
                  ].join(" ")}
                />
              </div>
            </button>
          </section>
        </div>

        {/* Footer */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-t border-border-subtle px-5 py-4">
          <button
            className="rounded-lg border border-border-subtle px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isPending}
            onClick={handleClose}
            type="button"
          >
            Cancelar
          </button>
          <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
            {errorMessage !== null ? (
              <div
                className="min-w-0 flex-1 truncate rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700"
                title={errorMessage}
              >
                {errorMessage}
              </div>
            ) : successMessage !== null ? (
              <div
                className="min-w-0 flex-1 truncate rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700"
                title={successMessage}
              >
                {successMessage}
              </div>
            ) : null}
            <button
              className="shrink-0 rounded-lg bg-brand-teal px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isPending}
              onClick={handleSubmit}
              type="button"
            >
              {isPending ? "Agendando..." : "Agendar cita"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

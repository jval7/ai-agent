import type * as reactModule from "react";

import * as slotPickerModule from "@adapters/inbound/react/components/SlotPicker";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import { approvalStatusLabels } from "@adapters/inbound/react/components/agenda/SchedulingRequestList";
import type { BookedAppointment } from "@adapters/inbound/react/hooks/useBookedAppointments";
import { resolvePatientDisplayName } from "@adapters/inbound/react/hooks/useBookedAppointments";
import type * as patientModel from "@domain/models/patient";
import type * as schedulingModel from "@domain/models/scheduling";
import type * as calendarUtilsModule from "@shared/utils/calendar";

const colombiaTimezone = "America/Bogota";

interface BookedPaymentFormState {
  paymentAmountCop: string;
  paymentMethod: "CASH" | "TRANSFER";
  paymentStatus: "PENDING" | "PAID";
}

interface SchedulingRequestDetailProps {
  selectedRequest: schedulingModel.SchedulingRequestSummary;
  patientsByWhatsappUserId: Map<string, patientModel.Patient>;
  selectedBookedAppointment: BookedAppointment | null;
  expandedBookedAction: "reschedule" | "cancel" | "payment" | "change-modality" | null;
  setExpandedBookedAction: reactModule.Dispatch<
    reactModule.SetStateAction<"reschedule" | "cancel" | "payment" | "change-modality" | null>
  >;
  bookedAppointmentFormState: { cancelReason: string };
  setBookedAppointmentFormState: reactModule.Dispatch<
    reactModule.SetStateAction<{ cancelReason: string }>
  >;
  bookedPaymentFormState: BookedPaymentFormState;
  setBookedPaymentFormState: reactModule.Dispatch<
    reactModule.SetStateAction<BookedPaymentFormState>
  >;
  // Reschedule
  rescheduleBusyIntervals: calendarUtilsModule.BusyIntervalRange[];
  rescheduleSelectedSlots: { slotId: string; startAt: string; endAt: string; timezone: string }[];
  setRescheduleSelectedSlots: reactModule.Dispatch<
    reactModule.SetStateAction<
      { slotId: string; startAt: string; endAt: string; timezone: string }[]
    >
  >;
  isLoadingAvailability: boolean;
  onRescheduleMonthChange: (month: { year: number; month: number }) => void;
  // Action handlers
  onRescheduleBookedSlot: (payload: {
    requestId: string;
    input: schedulingModel.RescheduleBookedSlotInput;
  }) => void;
  onCancelBookedSlot: (payload: {
    requestId: string;
    input: schedulingModel.CancelBookedSlotInput;
  }) => void;
  onUpdateBookedPayment: (payload: {
    requestId: string;
    input: schedulingModel.UpdateBookedSlotPaymentInput;
  }) => void;
  onResolvePaymentReview: (payload: {
    request: schedulingModel.SchedulingRequestSummary;
    decision: "APPROVE" | "SEND_REMINDER";
    professionalNote: string | null;
    paymentAmountCop: number | null;
    paymentCurrency: "COP" | "USD";
  }) => void;
  // Mutation pending states
  isReschedulingBotSlot: boolean;
  isCancellingBotSlot: boolean;
  isUpdatingBotPayment: boolean;
  isResolvingPaymentReview: boolean;
  // Feedback
  setLocalSubmitErrorMessage: reactModule.Dispatch<reactModule.SetStateAction<string | null>>;
  setSubmitSuccessMessage: reactModule.Dispatch<reactModule.SetStateAction<string | null>>;
}

export function SchedulingRequestDetail({
  selectedRequest,
  patientsByWhatsappUserId,
  selectedBookedAppointment,
  expandedBookedAction,
  setExpandedBookedAction,
  bookedAppointmentFormState,
  setBookedAppointmentFormState,
  bookedPaymentFormState,
  setBookedPaymentFormState,
  rescheduleBusyIntervals,
  rescheduleSelectedSlots,
  setRescheduleSelectedSlots,
  isLoadingAvailability,
  onRescheduleMonthChange,
  onRescheduleBookedSlot,
  onCancelBookedSlot,
  onUpdateBookedPayment,
  onResolvePaymentReview,
  isReschedulingBotSlot,
  isCancellingBotSlot,
  isUpdatingBotPayment,
  isResolvingPaymentReview,
  setLocalSubmitErrorMessage,
  setSubmitSuccessMessage
}: SchedulingRequestDetailProps) {
  const selectedBookedBotRequest =
    selectedBookedAppointment?.source === "BOT" ? selectedBookedAppointment.request : null;

  const isBookedOrClosed =
    selectedRequest.status === "BOOKED" || selectedRequest.status === "SESSION_CLOSED";

  return (
    <>
      {/* Patient info */}
      <section className="rounded-lg border border-border-subtle p-4">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold text-brand-ink">Información del paciente</h4>
          <statusBadgeModule.StatusBadge
            label={approvalStatusLabels[selectedRequest.status]?.label ?? selectedRequest.status}
            tone={approvalStatusLabels[selectedRequest.status]?.tone ?? "neutral"}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2 text-sm text-slate-700">
            <p>
              <span className="font-semibold text-slate-500">Nombre</span>
              <br />
              {resolvePatientDisplayName(selectedRequest, patientsByWhatsappUserId)}
            </p>
            <p>
              <span className="font-semibold text-slate-500">Motivo</span>
              <br />
              {selectedRequest.consultationReason ?? "-"}
            </p>
            {selectedRequest.consultationDetails !== null ? (
              <p>
                <span className="font-semibold text-slate-500">Detalles</span>
                <br />
                {selectedRequest.consultationDetails}
              </p>
            ) : null}
          </div>
          <div className="space-y-2 text-sm text-slate-700">
            <p>
              <span className="font-semibold text-slate-500">Teléfono</span>
              <br />
              {selectedRequest.whatsappUserId}
            </p>
            {selectedRequest.patientLocation !== null ? (
              <p>
                <span className="font-semibold text-slate-500">Ubicación</span>
                <br />
                {selectedRequest.patientLocation}
              </p>
            ) : null}
            {selectedRequest.appointmentModality !== null ? (
              <p>
                <span className="font-semibold text-slate-500">Modalidad</span>
                <br />
                {selectedRequest.appointmentModality}
              </p>
            ) : null}
          </div>
        </div>
        {selectedRequest.patientPreferenceNote !== null ? (
          <div className="mt-3 rounded-md bg-slate-50 p-3">
            <p className="text-xs font-semibold text-slate-500">Preferencias del paciente</p>
            <p className="mt-1 text-sm text-slate-700">{selectedRequest.patientPreferenceNote}</p>
          </div>
        ) : null}
        {selectedRequest.rejectionSummary !== null ? (
          <div className="mt-2 rounded-md bg-red-50 p-3">
            <p className="text-xs font-semibold text-red-600">Resumen rechazo</p>
            <p className="mt-1 text-sm text-red-700">{selectedRequest.rejectionSummary}</p>
          </div>
        ) : null}
        {selectedBookedAppointment !== null ? (
          <div className="mt-3 rounded-md bg-brand-accent-light p-3">
            <p className="text-xs font-semibold text-brand-teal">Cita agendada</p>
            <p className="mt-1 text-sm text-brand-ink">
              {selectedBookedAppointment.startAt.toFormat("dd LLL yyyy HH:mm")} -{" "}
              {selectedBookedAppointment.endAt.toFormat("HH:mm")}
            </p>
          </div>
        ) : null}
      </section>

      {/* Manage booked/closed bot slot */}
      {isBookedOrClosed ? (
        <section className="rounded-lg border border-border-subtle p-3">
          <h4 className="text-sm font-semibold text-brand-ink">Gestionar cita del chatbot</h4>
          <div className="mt-2 flex items-center gap-2">
            <span
              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ${selectedRequest.paymentStatus === "PAID" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}
            >
              {selectedRequest.paymentStatus === "PAID" ? "Pago confirmado" : "Pago pendiente"}
            </span>
            {selectedRequest.paymentAmountCop != null ? (
              <span className="text-xs text-slate-500">
                ${selectedRequest.paymentAmountCop.toLocaleString("es-CO")} COP
              </span>
            ) : null}
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${expandedBookedAction === "reschedule" ? "bg-brand-teal text-white" : "border border-brand-teal text-brand-teal hover:bg-brand-accent-light"}`}
              onClick={() =>
                setExpandedBookedAction(expandedBookedAction === "reschedule" ? null : "reschedule")
              }
              type="button"
            >
              Reprogramar
            </button>
            <button
              className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${expandedBookedAction === "cancel" ? "bg-rose-600 text-white" : "border border-rose-600 text-rose-600 hover:bg-rose-50"}`}
              onClick={() =>
                setExpandedBookedAction(expandedBookedAction === "cancel" ? null : "cancel")
              }
              type="button"
            >
              Cancelar
            </button>
            {selectedRequest.paymentStatus !== "PAID" ? (
              <button
                className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${expandedBookedAction === "payment" ? "bg-brand-teal text-white" : "border border-brand-teal text-brand-teal hover:bg-brand-accent-light"}`}
                onClick={() =>
                  setExpandedBookedAction(expandedBookedAction === "payment" ? null : "payment")
                }
                type="button"
              >
                Agregar pago
              </button>
            ) : null}
            {selectedRequest.paymentStatus !== "PAID" ? (
              <button
                className="rounded-md border border-amber-500 px-4 py-2 text-sm font-semibold text-amber-600 transition-colors hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isResolvingPaymentReview}
                onClick={() => {
                  if (selectedBookedBotRequest === null) {
                    return;
                  }
                  setLocalSubmitErrorMessage(null);
                  setSubmitSuccessMessage(null);
                  onResolvePaymentReview({
                    request: selectedRequest,
                    decision: "SEND_REMINDER",
                    professionalNote: null,
                    paymentAmountCop: null,
                    paymentCurrency: "COP"
                  });
                }}
                type="button"
              >
                {isResolvingPaymentReview ? "Enviando..." : "Recordatorio de pago"}
              </button>
            ) : null}
          </div>

          {expandedBookedAction === "reschedule" ? (
            <div
              className="mt-3 rounded-lg border border-border-subtle p-4 space-y-4"
              data-testid="reschedule-slotpicker-bot"
            >
              <div>
                <p className="text-sm font-semibold text-brand-ink">Reprogramar cita</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Selecciona un nuevo horario disponible.
                </p>
              </div>
              <slotPickerModule.SlotPicker
                timezone={colombiaTimezone}
                busyIntervals={rescheduleBusyIntervals}
                requestId={selectedBookedAppointment?.requestId ?? "reschedule"}
                selectedSlots={rescheduleSelectedSlots}
                onSelectedSlotsChange={(slots) => setRescheduleSelectedSlots(slots.slice(-1))}
                isLoadingAvailability={isLoadingAvailability}
                onMonthChange={onRescheduleMonthChange}
              />
              <div className="flex flex-wrap gap-2 pt-1">
                <button
                  className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={rescheduleSelectedSlots.length !== 1 || isReschedulingBotSlot}
                  onClick={() => {
                    const slot = rescheduleSelectedSlots[0];
                    if (slot === undefined || selectedBookedBotRequest === null) {
                      return;
                    }
                    const eventSummary =
                      selectedBookedAppointment?.patientDisplayName.trim() === ""
                        ? "Cita"
                        : `Cita - ${selectedBookedAppointment?.patientDisplayName ?? ""}`;
                    setLocalSubmitErrorMessage(null);
                    setSubmitSuccessMessage(null);
                    onRescheduleBookedSlot({
                      requestId: selectedBookedBotRequest.requestId,
                      input: {
                        startAt: slot.startAt,
                        endAt: slot.endAt,
                        timezone: slot.timezone,
                        eventSummary
                      }
                    });
                  }}
                  type="button"
                >
                  {isReschedulingBotSlot ? "Guardando..." : "Guardar reprogramación"}
                </button>
                <button
                  className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                  onClick={() => {
                    setExpandedBookedAction(null);
                    setRescheduleSelectedSlots([]);
                  }}
                  type="button"
                >
                  Cancelar
                </button>
              </div>
            </div>
          ) : null}

          {expandedBookedAction === "cancel" ? (
            <div className="mt-3 rounded-lg border border-border-subtle p-3">
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Motivo de cancelación (opcional)
                <textarea
                  className="mt-1 min-h-20 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 text-slate-700"
                  onChange={(event) => {
                    const nextValue = event.target.value;
                    setBookedAppointmentFormState((currentValue) => ({
                      ...currentValue,
                      cancelReason: nextValue
                    }));
                  }}
                  value={bookedAppointmentFormState.cancelReason}
                />
              </label>
              <div className="mt-3">
                <button
                  className="rounded-md bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={isCancellingBotSlot}
                  onClick={() => {
                    if (selectedBookedBotRequest === null) {
                      return;
                    }
                    const isConfirmed = window.confirm(
                      "¿Seguro que quieres cancelar esta cita del chatbot?"
                    );
                    if (!isConfirmed) {
                      return;
                    }
                    setLocalSubmitErrorMessage(null);
                    setSubmitSuccessMessage(null);
                    onCancelBookedSlot({
                      requestId: selectedBookedBotRequest.requestId,
                      input: {
                        reason:
                          bookedAppointmentFormState.cancelReason.trim() === ""
                            ? null
                            : bookedAppointmentFormState.cancelReason.trim()
                      }
                    });
                  }}
                  type="button"
                >
                  {isCancellingBotSlot ? "Cancelando..." : "Cancelar cita"}
                </button>
              </div>
            </div>
          ) : null}

          {expandedBookedAction === "payment" ? (
            <div className="mt-3 rounded-lg border border-border-subtle p-3">
              <div className="grid gap-3 md:grid-cols-3">
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Valor (COP)
                  <input
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    min={1}
                    onChange={(event) => {
                      setBookedPaymentFormState((currentValue) => ({
                        ...currentValue,
                        paymentAmountCop: event.target.value
                      }));
                    }}
                    type="number"
                    value={bookedPaymentFormState.paymentAmountCop}
                  />
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Categoría
                  <select
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      setBookedPaymentFormState((currentValue) => ({
                        ...currentValue,
                        paymentMethod: event.target.value as "CASH" | "TRANSFER"
                      }));
                    }}
                    value={bookedPaymentFormState.paymentMethod}
                  >
                    <option value="CASH">Efectivo</option>
                    <option value="TRANSFER">Transferencia</option>
                  </select>
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Estado
                  <select
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    onChange={(event) => {
                      setBookedPaymentFormState((currentValue) => ({
                        ...currentValue,
                        paymentStatus: event.target.value as "PENDING" | "PAID"
                      }));
                    }}
                    value={bookedPaymentFormState.paymentStatus}
                  >
                    <option value="PENDING">Pendiente por pago</option>
                    <option value="PAID">Pagada</option>
                  </select>
                </label>
              </div>
              <div className="mt-3">
                <button
                  className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={isUpdatingBotPayment}
                  onClick={() => {
                    if (selectedBookedBotRequest === null) {
                      return;
                    }
                    const paymentAmountCop = Number.parseInt(
                      bookedPaymentFormState.paymentAmountCop,
                      10
                    );
                    if (Number.isNaN(paymentAmountCop) || paymentAmountCop <= 0) {
                      setLocalSubmitErrorMessage("El valor del pago debe ser mayor a cero.");
                      return;
                    }
                    setLocalSubmitErrorMessage(null);
                    setSubmitSuccessMessage(null);
                    onUpdateBookedPayment({
                      requestId: selectedBookedBotRequest.requestId,
                      input: {
                        paymentAmountCop,
                        paymentCurrency: selectedBookedBotRequest.paymentCurrency ?? "COP",
                        paymentMethod: bookedPaymentFormState.paymentMethod,
                        paymentStatus: bookedPaymentFormState.paymentStatus
                      }
                    });
                  }}
                  type="button"
                >
                  {isUpdatingBotPayment ? "Guardando pago..." : "Guardar pago"}
                </button>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
    </>
  );
}

import * as luxonModule from "luxon";

import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import { AppointmentCalendar } from "@adapters/inbound/react/components/AppointmentCalendar";
import * as appointmentDetailCardModule from "@adapters/inbound/react/components/AppointmentDetailCard";
import * as appointmentDrawerModule from "@adapters/inbound/react/components/AppointmentDrawer";
import { ChangeModalityPanel } from "@adapters/inbound/react/components/ChangeModalityPanel";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import { NewManualAppointmentModal } from "@adapters/inbound/react/components/NewManualAppointmentModal";
import { ReschedulePanel } from "@adapters/inbound/react/components/ReschedulePanel";
import { SchedulingRequestList } from "@adapters/inbound/react/components/SchedulingRequestList";
import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import { useAgendaActions } from "@adapters/inbound/react/hooks/useAgendaActions";
import {
  useBookedAppointments,
  manualAppointmentsQueryKey,
  schedulingRequestsQueryKey,
  googleCalendarConnectionQueryKey,
  patientsQueryKey,
  resolvePatientDisplayName
} from "@adapters/inbound/react/hooks/useBookedAppointments";
import {
  useSchedulingRequests,
  agendaStatuses,
  approvalStatusLabels
} from "@adapters/inbound/react/hooks/useSchedulingRequests";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import type * as schedulingModel from "@domain/models/scheduling";
import * as uiErrorModule from "@shared/http/ui_error";

export function AgendaPage() {
  const queryClient = reactQueryModule.useQueryClient();
  const nowDate = luxonModule.DateTime.now();

  // ── Shared selection state (needed by both hooks) ─────────────────────────
  const [selectedRequestId, setSelectedRequestId] = reactModule.useState<string | null>(null);
  const [activeTab, setActiveTab] =
    reactModule.useState<schedulingModel.SchedulingRequestStatus>("BOOKED");
  const isBookedTab = activeTab === "BOOKED";

  // ── Booked appointments data + calendar state ─────────────────────────────
  const booked = useBookedAppointments({
    isBookedTab,
    selectedRequestId,
    setSelectedRequestId
  });

  // ── Scheduling request state (uses allRequests from booked hook) ──────────
  const requests = useSchedulingRequests(booked.allRequests, {
    externalSelectedRequestId: selectedRequestId,
    externalSetSelectedRequestId: setSelectedRequestId
  });

  // ── Actions + mutations ──────────────────────────────────────────────────
  const actions = useAgendaActions({
    selectedBookedAppointment: booked.selectedBookedAppointment,
    timezone: booked.timezone
  });

  const [isNewManualModalOpen, setIsNewManualModalOpen] = reactModule.useState(false);
  const [desktopDrawerOpen, setDesktopDrawerOpen] = reactModule.useState(false);

  const { filteredRequests, requestCountByStatus, selectedRequest } = requests;

  const loadingErrorMessage = uiErrorModule.resolveUiErrorMessage([
    booked.requestsQuery.error,
    booked.googleCalendarConnectionQuery.error,
    booked.patientsQuery.error,
    booked.manualAppointmentsQuery.error
  ]);

  // Day grid for calendar
  const firstWeekdayOffset = booked.visibleMonthStart.weekday % 7;
  const monthDays = booked.visibleMonthStart.daysInMonth ?? 0;
  const dayGrid: (luxonModule.DateTime | null)[] = [];
  for (let index = 0; index < firstWeekdayOffset; index += 1) {
    dayGrid.push(null);
  }
  for (let day = 1; day <= monthDays; day += 1) {
    dayGrid.push(booked.visibleMonthStart.set({ day }));
  }

  // Derived: current modality for change-modality panel
  const selectedBookedAppointment = booked.selectedBookedAppointment;
  const currentModality =
    selectedBookedAppointment !== null
      ? selectedBookedAppointment.source === "MANUAL" &&
        selectedBookedAppointment.manualAppointment !== null
        ? selectedBookedAppointment.manualAppointment.isVirtual
          ? "VIRTUAL"
          : "PRESENCIAL"
        : selectedBookedAppointment.request?.appointmentModality === "PRESENCIAL"
          ? "PRESENCIAL"
          : "VIRTUAL"
      : "VIRTUAL";
  const targetModality: "PRESENCIAL" | "VIRTUAL" =
    currentModality === "PRESENCIAL" ? "VIRTUAL" : "PRESENCIAL";

  const formattedModalityDate =
    selectedBookedAppointment !== null
      ? luxonModule.DateTime.fromISO(selectedBookedAppointment.startAt.toISO() ?? "", {
          setZone: true
        })
          .setZone(booked.timezone)
          .setLocale("es")
          .toFormat("EEE dd LLL yyyy")
      : "";

  const appointmentDetailCardProps: appointmentDetailCardModule.AppointmentDetailCardProps | null =
    selectedBookedAppointment !== null
      ? {
          origin: selectedBookedAppointment.source === "MANUAL" ? "MANUAL" : "CHATBOT",
          modality:
            selectedBookedAppointment.source === "MANUAL" &&
            selectedBookedAppointment.manualAppointment !== null
              ? selectedBookedAppointment.manualAppointment.isVirtual
                ? ("VIRTUAL" as const)
                : ("PRESENCIAL" as const)
              : selectedBookedAppointment.request?.appointmentModality === "PRESENCIAL"
                ? ("PRESENCIAL" as const)
                : ("VIRTUAL" as const),
          patientFullName: selectedBookedAppointment.patientDisplayName,
          summary:
            selectedBookedAppointment.source === "MANUAL"
              ? selectedBookedAppointment.summary
              : (selectedBookedAppointment.request?.consultationReason ?? null),
          startAt: selectedBookedAppointment.startAt.toISO() ?? "",
          endAt: selectedBookedAppointment.endAt.toISO() ?? "",
          timezone: booked.timezone,
          durationMinutes: Math.round(
            selectedBookedAppointment.endAt.diff(selectedBookedAppointment.startAt, "minutes")
              .minutes
          ),
          payment:
            selectedBookedAppointment.source === "MANUAL" &&
            selectedBookedAppointment.manualAppointment !== null
              ? {
                  status: selectedBookedAppointment.manualAppointment.paymentStatus ?? null,
                  amountCop: selectedBookedAppointment.manualAppointment.paymentAmountCop,
                  currency: selectedBookedAppointment.manualAppointment.paymentCurrency,
                  category: selectedBookedAppointment.manualAppointment.paymentMethod
                }
              : {
                  status: selectedBookedAppointment.request?.paymentStatus ?? null,
                  amountCop: selectedBookedAppointment.request?.paymentAmountCop ?? null,
                  currency: selectedBookedAppointment.request?.paymentCurrency ?? ("COP" as const),
                  category: selectedBookedAppointment.request?.paymentMethod ?? null
                },
          paymentDraft: actions.drawerPaymentDraft,
          onPaymentDraftChange: actions.setDrawerPaymentDraft,
          isSavingPayment: actions.isSavingPayment,
          onSavePayment: () => actions.handleSavePayment(selectedBookedAppointment),
          onReschedule: () => {
            actions.setExpandedBookedAction(
              actions.expandedBookedAction === "reschedule" ? null : "reschedule"
            );
          },
          ...(selectedBookedAppointment.startAt > nowDate
            ? {
                onChangeModality: () => {
                  actions.setLocalSubmitErrorMessage(null);
                  actions.setSubmitSuccessMessage(null);
                  actions.setExpandedBookedAction("change-modality");
                }
              }
            : {}),
          onCancel: () => actions.handleCancel(selectedBookedAppointment),
          errorMessage: actions.localSubmitErrorMessage ?? actions.submitErrorMessage,
          successMessage: actions.submitSuccessMessage
        }
      : null;

  const rescheduleRequestId =
    selectedBookedAppointment !== null
      ? selectedBookedAppointment.source === "MANUAL"
        ? (selectedBookedAppointment.manualAppointmentId ?? "reschedule")
        : (selectedBookedAppointment.requestId ?? "reschedule")
      : "reschedule";

  return (
    <appShellModule.AppShell>
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
          <div>
            <h2 className="text-lg font-semibold text-brand-ink sm:text-xl">Agenda profesional</h2>
            <p className="text-xs text-slate-600 sm:text-sm">
              Gestiona solicitudes y envía múltiples slots de 60 minutos.
            </p>
          </div>
          <button
            className="rounded-lg border border-border-subtle px-3 py-2 text-xs font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 sm:px-4 sm:py-2.5 sm:text-sm"
            onClick={() => {
              void queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey });
              void queryClient.invalidateQueries({ queryKey: googleCalendarConnectionQueryKey });
              void queryClient.invalidateQueries({ queryKey: patientsQueryKey });
              void queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey });
              void queryClient.invalidateQueries({
                queryKey: ["google-calendar-availability"]
              });
            }}
            type="button"
          >
            Refrescar
          </button>
        </div>

        {/* ── Tab bar ────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap gap-2">
          {agendaStatuses.map((tab) => (
            <button
              className={[
                "rounded-md border px-3 py-2 text-sm font-semibold",
                activeTab === tab.status
                  ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
              ].join(" ")}
              key={tab.status}
              onClick={() => {
                setActiveTab(tab.status);
                booked.setSelectedBookedItemKey(null);
                actions.setSubmitSuccessMessage(null);
                actions.setLocalSubmitErrorMessage(null);
                booked.setMobileBookedStep("calendar");
              }}
              type="button"
            >
              {tab.label} ({requestCountByStatus.get(tab.status) ?? 0})
            </button>
          ))}
        </div>
      </section>

      {/* ── Main grid ────────────────────────────────────────────────────────── */}
      <section className="mt-4">
        <div
          className={["grid gap-4", isBookedTab ? "" : "lg:grid-cols-[320px_minmax(0,1fr)]"].join(
            " "
          )}
        >
          {/* Left column */}
          {isBookedTab ? (
            <AppointmentCalendar
              visibleMonthStart={booked.visibleMonthStart}
              dayGrid={dayGrid}
              bookedAppointmentsByDay={booked.bookedAppointmentsByDay}
              selectedDayIso={booked.selectedDayIso}
              selectedBookedItemKey={booked.selectedBookedItemKey}
              nowDate={nowDate}
              timezone={booked.timezone}
              desktopDrawerOpen={desktopDrawerOpen}
              mobileBookedStep={booked.mobileBookedStep}
              selectedDayAppointments={booked.selectedDayAppointments}
              onDayCellClick={(isoDate, firstAppointment) => {
                booked.setSelectedDayIso(isoDate);
                if (firstAppointment !== undefined) {
                  booked.setSelectedBookedItemKey(firstAppointment.itemKey);
                  setSelectedRequestId(firstAppointment.requestId);
                  if (booked.mobileBookedStep === "calendar") {
                    booked.setMobileBookedStep("dayList");
                  }
                }
              }}
              onMobileAppointmentClick={(appointment) => {
                booked.setSelectedDayIso(appointment.dayIso);
                booked.setSelectedBookedItemKey(appointment.itemKey);
                setSelectedRequestId(appointment.requestId);
                actions.setSubmitSuccessMessage(null);
                actions.setLocalSubmitErrorMessage(null);
                actions.setExpandedBookedAction(null);
                booked.setMobileBookedStep("detail");
              }}
              onAppointmentClick={(appointment) => {
                booked.setSelectedDayIso(appointment.dayIso);
                booked.setSelectedBookedItemKey(appointment.itemKey);
                setSelectedRequestId(appointment.requestId);
                actions.setSubmitSuccessMessage(null);
                actions.setLocalSubmitErrorMessage(null);
                actions.setExpandedBookedAction(null);
                setDesktopDrawerOpen(true);
              }}
              onNewManualAppointment={() => setIsNewManualModalOpen(true)}
              onPreviousMonth={() => {
                const previous = booked.visibleMonthStart.minus({ months: 1 });
                booked.setVisibleMonth({
                  year: previous.year,
                  month: previous.month as luxonModule.MonthNumbers
                });
              }}
              onNextMonth={() => {
                const next = booked.visibleMonthStart.plus({ months: 1 });
                booked.setVisibleMonth({
                  year: next.year,
                  month: next.month as luxonModule.MonthNumbers
                });
              }}
              onMobileBackToCalendar={() => booked.setMobileBookedStep("calendar")}
            />
          ) : (
            <SchedulingRequestList
              requests={filteredRequests}
              selectedRequestId={selectedRequestId}
              patientsByWhatsappUserId={booked.patientsByWhatsappUserId}
              isLoading={booked.requestsQuery.isLoading}
              activeTab={activeTab}
              onSelectRequest={(requestId) => {
                setSelectedRequestId(requestId);
                actions.setSubmitSuccessMessage(null);
                actions.setLocalSubmitErrorMessage(null);
              }}
            />
          )}

          {/* Right column / detail panel */}
          <article
            className={[
              "space-y-4 rounded-xl border border-border-subtle bg-white p-3 shadow-card sm:p-4",
              isBookedTab && booked.mobileBookedStep !== "detail" ? "hidden" : "",
              isBookedTab && booked.mobileBookedStep === "detail" ? "sm:hidden" : ""
            ].join(" ")}
          >
            {/* Mobile back button */}
            {isBookedTab && booked.mobileBookedStep === "detail" ? (
              <button
                className="flex items-center gap-1 text-xs font-semibold text-brand-teal sm:hidden"
                onClick={() => booked.setMobileBookedStep("dayList")}
                type="button"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    d="M15 19l-7-7 7-7"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                  />
                </svg>
                Volver a citas del día
              </button>
            ) : null}

            {/* Booked tab: appointment detail */}
            {isBookedTab &&
            selectedBookedAppointment !== null &&
            appointmentDetailCardProps !== null ? (
              <appointmentDetailCardModule.AppointmentDetailCard {...appointmentDetailCardProps} />
            ) : null}

            {/* Booked tab: reschedule panel */}
            {isBookedTab &&
            selectedBookedAppointment !== null &&
            actions.expandedBookedAction === "reschedule" ? (
              <ReschedulePanel
                timezone={booked.timezone}
                busyIntervals={actions.rescheduleBusyIntervals}
                requestId={rescheduleRequestId}
                selectedSlots={actions.rescheduleSelectedSlots}
                onSelectedSlotsChange={actions.setRescheduleSelectedSlots}
                isLoadingAvailability={actions.rescheduleAvailabilityQuery.isLoading}
                onMonthChange={actions.setRescheduleSlotPickerMonth}
                isSaving={actions.isReschedulePending}
                onSave={() => actions.handleReschedule(selectedBookedAppointment)}
                onCancel={() => {
                  actions.setExpandedBookedAction(null);
                  actions.setRescheduleSelectedSlots([]);
                }}
                testId="reschedule-slotpicker-panel"
              />
            ) : null}

            {/* Booked tab: change modality panel */}
            {isBookedTab &&
            selectedBookedAppointment !== null &&
            actions.expandedBookedAction === "change-modality" ? (
              <ChangeModalityPanel
                patientDisplayName={selectedBookedAppointment.patientDisplayName}
                formattedDate={formattedModalityDate}
                currentModality={currentModality}
                targetModality={targetModality}
                isSaving={actions.isChangeModalityPending}
                onConfirm={() =>
                  actions.handleChangeModality(selectedBookedAppointment, targetModality)
                }
                onCancel={() => actions.setExpandedBookedAction(null)}
              />
            ) : null}

            {/* Empty states */}
            {isBookedTab && selectedBookedAppointment === null ? (
              <p className="text-sm text-slate-500">
                Selecciona una cita en el calendario para ver todos los detalles.
              </p>
            ) : !isBookedTab && selectedRequest === undefined ? (
              <p className="text-sm text-slate-500">
                Selecciona una solicitud para ver detalle y gestionar slots.
              </p>
            ) : !isBookedTab && selectedRequest !== undefined ? (
              <>
                {/* Patient info section */}
                <section className="rounded-lg border border-border-subtle p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-brand-ink">
                      Información del paciente
                    </h4>
                    <statusBadgeModule.StatusBadge
                      label={
                        approvalStatusLabels[selectedRequest.status]?.label ??
                        selectedRequest.status
                      }
                      tone={approvalStatusLabels[selectedRequest.status]?.tone ?? "neutral"}
                    />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2 text-sm text-slate-700">
                      <p>
                        <span className="font-semibold text-slate-500">Nombre</span>
                        <br />
                        {resolvePatientDisplayName(
                          selectedRequest,
                          booked.patientsByWhatsappUserId
                        )}
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
                      <p className="text-xs font-semibold text-slate-500">
                        Preferencias del paciente
                      </p>
                      <p className="mt-1 text-sm text-slate-700">
                        {selectedRequest.patientPreferenceNote}
                      </p>
                    </div>
                  ) : null}
                  {selectedRequest.rejectionSummary !== null ? (
                    <div className="mt-2 rounded-md bg-red-50 p-3">
                      <p className="text-xs font-semibold text-red-600">Resumen rechazo</p>
                      <p className="mt-1 text-sm text-red-700">
                        {selectedRequest.rejectionSummary}
                      </p>
                    </div>
                  ) : null}
                </section>

                {/* Manage booked/closed bot request */}
                {selectedRequest.status === "BOOKED" ||
                selectedRequest.status === "SESSION_CLOSED" ? (
                  <section className="rounded-lg border border-border-subtle p-3">
                    <h4 className="text-sm font-semibold text-brand-ink">
                      Gestionar cita del chatbot
                    </h4>
                    <div className="mt-2 flex items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ${
                          selectedRequest.paymentStatus === "PAID"
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        {selectedRequest.paymentStatus === "PAID"
                          ? "Pago confirmado"
                          : "Pago pendiente"}
                      </span>
                      {selectedRequest.paymentAmountCop != null ? (
                        <span className="text-xs text-slate-500">
                          ${selectedRequest.paymentAmountCop.toLocaleString("es-CO")} COP
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${
                          actions.expandedBookedAction === "reschedule"
                            ? "bg-brand-teal text-white"
                            : "border border-brand-teal text-brand-teal hover:bg-brand-accent-light"
                        }`}
                        onClick={() =>
                          actions.setExpandedBookedAction(
                            actions.expandedBookedAction === "reschedule" ? null : "reschedule"
                          )
                        }
                        type="button"
                      >
                        Reprogramar
                      </button>
                      <button
                        className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${
                          actions.expandedBookedAction === "cancel"
                            ? "bg-rose-600 text-white"
                            : "border border-rose-600 text-rose-600 hover:bg-rose-50"
                        }`}
                        onClick={() =>
                          actions.setExpandedBookedAction(
                            actions.expandedBookedAction === "cancel" ? null : "cancel"
                          )
                        }
                        type="button"
                      >
                        Cancelar
                      </button>
                      {selectedRequest.paymentStatus !== "PAID" ? (
                        <button
                          className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${
                            actions.expandedBookedAction === "payment"
                              ? "bg-brand-teal text-white"
                              : "border border-brand-teal text-brand-teal hover:bg-brand-accent-light"
                          }`}
                          onClick={() =>
                            actions.setExpandedBookedAction(
                              actions.expandedBookedAction === "payment" ? null : "payment"
                            )
                          }
                          type="button"
                        >
                          Agregar pago
                        </button>
                      ) : null}
                      {selectedRequest.paymentStatus !== "PAID" ? (
                        <button
                          className="rounded-md border border-amber-500 px-4 py-2 text-sm font-semibold text-amber-600 transition-colors hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={actions.isPaymentReminderPending}
                          onClick={() => actions.handleSendPaymentReminder(selectedRequest, null)}
                          type="button"
                        >
                          {actions.isPaymentReminderPending
                            ? "Enviando..."
                            : "Recordatorio de pago"}
                        </button>
                      ) : null}
                    </div>

                    {/* Inline reschedule for bot requests */}
                    {actions.expandedBookedAction === "reschedule" ? (
                      <div className="mt-3">
                        <ReschedulePanel
                          timezone={booked.timezone}
                          busyIntervals={actions.rescheduleBusyIntervals}
                          requestId={selectedBookedAppointment?.requestId ?? "reschedule"}
                          selectedSlots={actions.rescheduleSelectedSlots}
                          onSelectedSlotsChange={actions.setRescheduleSelectedSlots}
                          isLoadingAvailability={actions.rescheduleAvailabilityQuery.isLoading}
                          onMonthChange={actions.setRescheduleSlotPickerMonth}
                          isSaving={actions.isReschedulePending}
                          onSave={() => {
                            if (selectedBookedAppointment !== null) {
                              actions.handleReschedule(selectedBookedAppointment);
                            }
                          }}
                          onCancel={() => {
                            actions.setExpandedBookedAction(null);
                            actions.setRescheduleSelectedSlots([]);
                          }}
                          testId="reschedule-slotpicker-bot"
                        />
                      </div>
                    ) : null}

                    {/* Cancel form */}
                    {actions.expandedBookedAction === "cancel" ? (
                      <div className="mt-3 rounded-lg border border-border-subtle p-3">
                        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Motivo de cancelación (opcional)
                          <textarea
                            className="mt-1 min-h-20 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 text-slate-700"
                            onChange={(event) => {
                              const nextValue = event.target.value;
                              actions.setBookedAppointmentFormState((currentValue) => ({
                                ...currentValue,
                                cancelReason: nextValue
                              }));
                            }}
                            value={actions.bookedAppointmentFormState.cancelReason}
                          />
                        </label>
                        <div className="mt-3">
                          <button
                            className="rounded-md bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={actions.isCancelPending}
                            onClick={() => {
                              if (selectedRequest === undefined) {
                                return;
                              }
                              const isConfirmed = window.confirm(
                                "¿Seguro que quieres cancelar esta cita del chatbot?"
                              );
                              if (!isConfirmed) {
                                return;
                              }
                              const reason =
                                actions.bookedAppointmentFormState.cancelReason.trim() === ""
                                  ? null
                                  : actions.bookedAppointmentFormState.cancelReason.trim();
                              actions.handleCancelBotSlot(selectedRequest.requestId, reason);
                            }}
                            type="button"
                          >
                            {actions.isCancelPending ? "Cancelando..." : "Cancelar cita"}
                          </button>
                        </div>
                      </div>
                    ) : null}

                    {/* Payment form */}
                    {actions.expandedBookedAction === "payment" ? (
                      <div className="mt-3 rounded-lg border border-border-subtle p-3">
                        <div className="grid gap-3 md:grid-cols-3">
                          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Valor (COP)
                            <input
                              className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                              min={1}
                              onChange={(event) => {
                                actions.setBookedPaymentFormState((currentValue) => ({
                                  ...currentValue,
                                  paymentAmountCop: event.target.value
                                }));
                              }}
                              type="number"
                              value={actions.bookedPaymentFormState.paymentAmountCop}
                            />
                          </label>
                          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Categoría
                            <select
                              className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                              onChange={(event) => {
                                actions.setBookedPaymentFormState((currentValue) => ({
                                  ...currentValue,
                                  paymentMethod: event.target.value as "CASH" | "TRANSFER"
                                }));
                              }}
                              value={actions.bookedPaymentFormState.paymentMethod}
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
                                actions.setBookedPaymentFormState((currentValue) => ({
                                  ...currentValue,
                                  paymentStatus: event.target.value as "PENDING" | "PAID"
                                }));
                              }}
                              value={actions.bookedPaymentFormState.paymentStatus}
                            >
                              <option value="PENDING">Pendiente por pago</option>
                              <option value="PAID">Pagada</option>
                            </select>
                          </label>
                        </div>
                        <div className="mt-3">
                          <button
                            className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={actions.isUpdateBotPaymentPending}
                            onClick={() => {
                              const paymentAmountCop = Number.parseInt(
                                actions.bookedPaymentFormState.paymentAmountCop,
                                10
                              );
                              if (Number.isNaN(paymentAmountCop) || paymentAmountCop <= 0) {
                                actions.setLocalSubmitErrorMessage(
                                  "El valor del pago debe ser mayor a cero."
                                );
                                return;
                              }
                              actions.handleUpdateBotPayment(
                                selectedRequest.requestId,
                                paymentAmountCop,
                                selectedRequest.paymentCurrency ?? "COP",
                                actions.bookedPaymentFormState.paymentMethod,
                                actions.bookedPaymentFormState.paymentStatus
                              );
                            }}
                            type="button"
                          >
                            {actions.isUpdateBotPaymentPending
                              ? "Guardando pago..."
                              : "Guardar pago"}
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </section>
                ) : null}
              </>
            ) : null}

            {/* Error / success banners */}
            {loadingErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner message={loadingErrorMessage} />
            ) : null}
            {actions.submitErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner message={actions.submitErrorMessage} />
            ) : null}
            {actions.localSubmitErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner message={actions.localSubmitErrorMessage} />
            ) : null}
            {actions.submitSuccessMessage !== null ? (
              <div className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                {actions.submitSuccessMessage}
              </div>
            ) : null}
          </article>
        </div>

        {/* ── Desktop drawer (booked tab only) ─────────────────────────────── */}
        {isBookedTab ? (
          <appointmentDrawerModule.AppointmentDrawer
            isOpen={desktopDrawerOpen && selectedBookedAppointment !== null}
            onClose={() => {
              setDesktopDrawerOpen(false);
              actions.setExpandedBookedAction(null);
              actions.setLocalSubmitErrorMessage(null);
              actions.setSubmitSuccessMessage(null);
            }}
          >
            {selectedBookedAppointment !== null && appointmentDetailCardProps !== null ? (
              <>
                <appointmentDetailCardModule.AppointmentDetailCard
                  {...appointmentDetailCardProps}
                />

                {/* Drawer: change modality */}
                {actions.expandedBookedAction === "change-modality" ? (
                  <ChangeModalityPanel
                    patientDisplayName={selectedBookedAppointment.patientDisplayName}
                    formattedDate={formattedModalityDate}
                    currentModality={currentModality}
                    targetModality={targetModality}
                    isSaving={actions.isChangeModalityPending}
                    onConfirm={() =>
                      actions.handleChangeModality(selectedBookedAppointment, targetModality)
                    }
                    onCancel={() => actions.setExpandedBookedAction(null)}
                    className="border-t border-border-subtle px-5 py-4 space-y-4"
                  />
                ) : null}

                {/* Drawer: reschedule */}
                {actions.expandedBookedAction === "reschedule" ? (
                  <ReschedulePanel
                    timezone={booked.timezone}
                    busyIntervals={actions.rescheduleBusyIntervals}
                    requestId={rescheduleRequestId}
                    selectedSlots={actions.rescheduleSelectedSlots}
                    onSelectedSlotsChange={actions.setRescheduleSelectedSlots}
                    isLoadingAvailability={actions.rescheduleAvailabilityQuery.isLoading}
                    onMonthChange={actions.setRescheduleSlotPickerMonth}
                    isSaving={actions.isReschedulePending}
                    onSave={() => actions.handleReschedule(selectedBookedAppointment)}
                    onCancel={() => {
                      actions.setExpandedBookedAction(null);
                      actions.setRescheduleSelectedSlots([]);
                    }}
                    className="border-t border-border-subtle px-5 py-4 space-y-4"
                    testId="reschedule-slotpicker-drawer"
                  />
                ) : null}

                {/* Drawer: cancel */}
                {actions.expandedBookedAction === "cancel" ? (
                  <div className="border-t border-border-subtle px-5 py-4">
                    <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Cancelar cita
                    </p>
                    <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Motivo de cancelación (opcional)
                      <textarea
                        className="mt-1 min-h-20 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm text-slate-700 transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                        onChange={(event) => {
                          const nextValue = event.target.value;
                          actions.setBookedAppointmentFormState((currentValue) => ({
                            ...currentValue,
                            cancelReason: nextValue
                          }));
                        }}
                        value={actions.bookedAppointmentFormState.cancelReason}
                      />
                    </label>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        className="rounded-md bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={actions.isCancelPending}
                        onClick={() => {
                          const isConfirmed = window.confirm(
                            "¿Seguro que quieres cancelar esta cita?"
                          );
                          if (!isConfirmed) {
                            return;
                          }
                          const reason =
                            actions.bookedAppointmentFormState.cancelReason.trim() === ""
                              ? null
                              : actions.bookedAppointmentFormState.cancelReason.trim();
                          if (
                            selectedBookedAppointment.source === "BOT" &&
                            selectedBookedAppointment.requestId !== null
                          ) {
                            actions.handleCancelBotSlot(
                              selectedBookedAppointment.requestId,
                              reason
                            );
                          } else if (
                            selectedBookedAppointment.source === "MANUAL" &&
                            selectedBookedAppointment.manualAppointmentId !== null
                          ) {
                            actions.handleCancelManualAppointment(
                              selectedBookedAppointment.manualAppointmentId,
                              reason
                            );
                          }
                        }}
                        type="button"
                      >
                        {actions.isCancelPending ? "Cancelando..." : "Cancelar cita"}
                      </button>
                      <button
                        className="rounded-lg border border-border-subtle px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                        onClick={() => actions.setExpandedBookedAction(null)}
                        type="button"
                      >
                        Cerrar
                      </button>
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
          </appointmentDrawerModule.AppointmentDrawer>
        ) : null}
      </section>

      <NewManualAppointmentModal
        isOpen={isNewManualModalOpen}
        onClose={() => setIsNewManualModalOpen(false)}
        onCreated={() => {
          void queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey });
        }}
      />
    </appShellModule.AppShell>
  );
}

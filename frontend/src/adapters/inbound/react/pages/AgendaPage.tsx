import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as appointmentCalendarModule from "@adapters/inbound/react/components/AppointmentCalendar";
import * as appointmentDetailCardModule from "@adapters/inbound/react/components/AppointmentDetailCard";
import * as appointmentDrawerModule from "@adapters/inbound/react/components/AppointmentDrawer";
import * as changeModalityPanelModule from "@adapters/inbound/react/components/ChangeModalityPanel";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import { NewManualAppointmentModal } from "@adapters/inbound/react/components/NewManualAppointmentModal";
import * as reschedulePanelModule from "@adapters/inbound/react/components/ReschedulePanel";
import * as schedulingRequestListModule from "@adapters/inbound/react/components/SchedulingRequestList";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import * as useAgendaActionsModule from "@adapters/inbound/react/hooks/useAgendaActions";
import * as useAgendaDataModule from "@adapters/inbound/react/hooks/useAgendaData";
import * as useBookedAppointmentsModule from "@adapters/inbound/react/hooks/useBookedAppointments";
import * as useRescheduleModule from "@adapters/inbound/react/hooks/useReschedule";
import * as useSchedulingRequestsModule from "@adapters/inbound/react/hooks/useSchedulingRequests";
import * as uiErrorModule from "@shared/http/ui_error";
import type { Patient } from "@domain/models/patient";

export function AgendaPage() {
  const queryClient = reactQueryModule.useQueryClient();
  const nowDate = luxonModule.DateTime.now();

  // Data fetching
  const { requestsQuery, googleCalendarConnectionQuery, patientsQuery, manualAppointmentsQuery } =
    useAgendaDataModule.useAgendaData();

  const allRequests = requestsQuery.data ?? [];
  const allPatients = patientsQuery.data ?? [];
  const allManualAppointments = manualAppointmentsQuery.data ?? [];

  const patientsByWhatsappUserId = reactModule.useMemo(() => {
    const map = new Map<string, Patient>();
    allPatients.forEach((patient) => {
      map.set(patient.whatsappUserId, patient);
    });
    return map;
  }, [allPatients]);

  const timezone = googleCalendarConnectionQuery.data?.professionalTimezone ?? "UTC";

  // Tab/request selection state
  const {
    activeTab,
    setActiveTab,
    isBookedTab,
    selectedRequestId,
    setSelectedRequestId,
    filteredRequests,
    requestCountByStatus,
    selectedRequest
  } = useSchedulingRequestsModule.useSchedulingRequests(allRequests);

  // Booked appointment calendar state
  const {
    bookedAppointments,
    bookedAppointmentsByDay,
    selectedDayIso,
    setSelectedDayIso,
    setVisibleMonth,
    visibleMonthStart,
    selectedBookedItemKey,
    setSelectedBookedItemKey,
    selectedBookedAppointment,
    selectedDayAppointments
  } = useBookedAppointmentsModule.useBookedAppointments({
    allRequests,
    allManualAppointments,
    patientsByWhatsappUserId,
    timezone,
    isBookedTab
  });

  // UI state for booked tab
  const [mobileBookedStep, setMobileBookedStep] = reactModule.useState<
    "calendar" | "dayList" | "detail"
  >("calendar");
  const [expandedBookedAction, setExpandedBookedAction] = reactModule.useState<
    "reschedule" | "cancel" | "payment" | "change-modality" | null
  >(null);
  const [desktopDrawerOpen, setDesktopDrawerOpen] = reactModule.useState(false);
  const [isNewManualModalOpen, setIsNewManualModalOpen] = reactModule.useState(false);

  // Actions/mutations + feedback state
  const actions = useAgendaActionsModule.useAgendaActions({ setActiveTab });
  const {
    bookedAppointmentFormState,
    setBookedAppointmentFormState,
    bookedPaymentFormState,
    setBookedPaymentFormState,
    drawerPaymentDraft,
    setDrawerPaymentDraft,
    localSubmitErrorMessage,
    setLocalSubmitErrorMessage,
    submitSuccessMessage,
    setSubmitSuccessMessage,
    submitErrorMessage,
    resolvePaymentReviewMutation,
    rescheduleManualAppointmentMutation,
    cancelManualAppointmentMutation,
    updateManualPaymentMutation,
    rescheduleBookedSlotMutation,
    cancelBookedSlotMutation,
    updateBookedPaymentMutation,
    changeModalityMutation
  } = actions;

  // Reschedule state (availability + selected slots)
  const {
    setRescheduleSlotPickerMonth,
    rescheduleSelectedSlots,
    setRescheduleSelectedSlots,
    rescheduleAvailabilityQuery,
    rescheduleBusyIntervals
  } = useRescheduleModule.useReschedule(
    expandedBookedAction === "reschedule",
    selectedBookedAppointment
  );

  // Sync expandedBookedAction reset on selection change
  reactModule.useEffect(() => {
    setExpandedBookedAction(null);
    setBookedAppointmentFormState(useAgendaActionsModule.emptyBookedAppointmentForm());
  }, [selectedBookedAppointment]);

  // Sync payment form with selected bot request
  const selectedBookedBotRequest =
    selectedBookedAppointment?.source === "BOT" ? selectedBookedAppointment.request : null;

  reactModule.useEffect(() => {
    if (selectedBookedBotRequest === null) {
      setBookedPaymentFormState(useAgendaActionsModule.emptyPaymentForm());
      return;
    }
    setBookedPaymentFormState({
      paymentAmountCop:
        selectedBookedBotRequest.paymentAmountCop == null
          ? ""
          : String(selectedBookedBotRequest.paymentAmountCop),
      paymentMethod: selectedBookedBotRequest.paymentMethod ?? "CASH",
      paymentStatus: selectedBookedBotRequest.paymentStatus ?? "PENDING"
    });
  }, [selectedBookedBotRequest]);

  // Sync drawer payment draft
  reactModule.useEffect(() => {
    if (selectedBookedAppointment === null) {
      setDrawerPaymentDraft({ amountCop: "", category: "CASH" });
      return;
    }
    if (
      selectedBookedAppointment.source === "MANUAL" &&
      selectedBookedAppointment.manualAppointment !== null
    ) {
      const ma = selectedBookedAppointment.manualAppointment;
      setDrawerPaymentDraft({
        amountCop: ma.paymentAmountCop == null ? "" : String(ma.paymentAmountCop),
        category: ma.paymentMethod ?? "CASH"
      });
    } else if (
      selectedBookedAppointment.source === "BOT" &&
      selectedBookedAppointment.request !== null
    ) {
      const req = selectedBookedAppointment.request;
      setDrawerPaymentDraft({
        amountCop: req.paymentAmountCop == null ? "" : String(req.paymentAmountCop),
        category: req.paymentMethod ?? "CASH"
      });
    }
  }, [selectedBookedAppointment]);

  // Sync booked appointment auto-selection
  reactModule.useEffect(() => {
    if (!isBookedTab) {
      return;
    }
    if (bookedAppointments.length === 0) {
      setSelectedBookedItemKey(null);
      return;
    }
    if (selectedBookedAppointment !== null) {
      if (selectedBookedAppointment.dayIso !== selectedDayIso) {
        setSelectedDayIso(selectedBookedAppointment.dayIso);
      }
      if (
        selectedBookedAppointment.source === "BOT" &&
        selectedBookedAppointment.requestId !== null
      ) {
        setSelectedRequestId(selectedBookedAppointment.requestId);
      } else {
        setSelectedRequestId(null);
      }
      return;
    }
    const firstAppointment = bookedAppointments[0];
    if (firstAppointment === undefined) {
      return;
    }
    setSelectedBookedItemKey(firstAppointment.itemKey);
    if (firstAppointment.source === "BOT" && firstAppointment.requestId !== null) {
      setSelectedRequestId(firstAppointment.requestId);
    } else {
      setSelectedRequestId(null);
    }
    if (firstAppointment.dayIso !== selectedDayIso) {
      setSelectedDayIso(firstAppointment.dayIso);
    }
  }, [bookedAppointments, isBookedTab, selectedBookedAppointment, selectedDayIso]);

  const loadingErrorMessage = uiErrorModule.resolveUiErrorMessage([
    requestsQuery.error,
    googleCalendarConnectionQuery.error,
    patientsQuery.error,
    manualAppointmentsQuery.error
  ]);

  // Shared handler: save payment (used in both inline and drawer)
  function handleSavePayment() {
    const amountCop = Number.parseInt(drawerPaymentDraft.amountCop, 10);
    if (Number.isNaN(amountCop) || amountCop <= 0) {
      setLocalSubmitErrorMessage("El valor del pago debe ser mayor a cero.");
      return;
    }
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    if (
      selectedBookedAppointment !== null &&
      selectedBookedAppointment.source === "MANUAL" &&
      selectedBookedAppointment.manualAppointmentId !== null
    ) {
      updateManualPaymentMutation.mutate({
        appointmentId: selectedBookedAppointment.manualAppointmentId,
        input: {
          paymentAmountCop: amountCop,
          paymentCurrency: selectedBookedAppointment.manualAppointment?.paymentCurrency ?? "COP",
          paymentMethod: drawerPaymentDraft.category as "CASH" | "TRANSFER",
          paymentStatus: "PAID"
        }
      });
    } else if (
      selectedBookedAppointment !== null &&
      selectedBookedAppointment.source === "BOT" &&
      selectedBookedAppointment.requestId !== null
    ) {
      updateBookedPaymentMutation.mutate({
        requestId: selectedBookedAppointment.requestId,
        input: {
          paymentAmountCop: amountCop,
          paymentCurrency: selectedBookedAppointment.request?.paymentCurrency ?? "COP",
          paymentMethod: drawerPaymentDraft.category as "CASH" | "TRANSFER",
          paymentStatus: "PAID"
        }
      });
    }
  }

  // Shared handler: cancel appointment (used in both inline and drawer)
  function handleCancelAppointment() {
    if (selectedBookedAppointment === null) {
      return;
    }
    const isConfirmed = window.confirm("¿Seguro que quieres cancelar esta cita?");
    if (!isConfirmed) {
      return;
    }
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    if (selectedBookedAppointment.source === "BOT" && selectedBookedBotRequest !== null) {
      cancelBookedSlotMutation.mutate({
        requestId: selectedBookedBotRequest.requestId,
        input: { reason: null }
      });
    } else if (
      selectedBookedAppointment.source === "MANUAL" &&
      selectedBookedAppointment.manualAppointmentId !== null
    ) {
      cancelManualAppointmentMutation.mutate({
        appointmentId: selectedBookedAppointment.manualAppointmentId,
        input: { reason: null }
      });
    }
  }

  // Shared handler: confirm reschedule slot
  function handleRescheduleConfirm(slot: {
    slotId: string;
    startAt: string;
    endAt: string;
    timezone: string;
  }) {
    if (selectedBookedAppointment === null) {
      return;
    }
    setLocalSubmitErrorMessage(null);
    setSubmitSuccessMessage(null);
    if (
      selectedBookedAppointment.source === "MANUAL" &&
      selectedBookedAppointment.manualAppointmentId !== null
    ) {
      rescheduleManualAppointmentMutation.mutate({
        appointmentId: selectedBookedAppointment.manualAppointmentId,
        input: {
          startAt: slot.startAt,
          endAt: slot.endAt,
          timezone: slot.timezone,
          summary:
            selectedBookedAppointment.manualAppointment?.summary.trim() === ""
              ? null
              : (selectedBookedAppointment.manualAppointment?.summary ?? null)
        }
      });
    } else if (selectedBookedAppointment.source === "BOT" && selectedBookedBotRequest !== null) {
      const eventSummary =
        selectedBookedAppointment.patientDisplayName.trim() === ""
          ? "Cita"
          : `Cita - ${selectedBookedAppointment.patientDisplayName}`;
      rescheduleBookedSlotMutation.mutate({
        requestId: selectedBookedBotRequest.requestId,
        input: {
          startAt: slot.startAt,
          endAt: slot.endAt,
          timezone: slot.timezone,
          eventSummary
        }
      });
    }
  }

  // Shared AppointmentDetailCard props builder
  function buildDetailCardProps(forDrawer: boolean) {
    if (selectedBookedAppointment === null) {
      return null;
    }
    return {
      origin: selectedBookedAppointment.source === "MANUAL" ? "MANUAL" : "CHATBOT",
      modality:
        selectedBookedAppointment.source === "MANUAL" &&
        selectedBookedAppointment.manualAppointment !== null
          ? selectedBookedAppointment.manualAppointment.isVirtual
            ? "VIRTUAL"
            : "PRESENCIAL"
          : selectedBookedAppointment.request?.appointmentModality === "PRESENCIAL"
            ? "PRESENCIAL"
            : "VIRTUAL",
      patientFullName: selectedBookedAppointment.patientDisplayName,
      summary:
        selectedBookedAppointment.source === "MANUAL"
          ? selectedBookedAppointment.summary
          : (selectedBookedAppointment.request?.consultationReason ?? null),
      startAt: selectedBookedAppointment.startAt.toISO() ?? "",
      endAt: selectedBookedAppointment.endAt.toISO() ?? "",
      timezone,
      durationMinutes: Math.round(
        selectedBookedAppointment.endAt.diff(selectedBookedAppointment.startAt, "minutes").minutes
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
              currency: selectedBookedAppointment.request?.paymentCurrency ?? "COP",
              category: selectedBookedAppointment.request?.paymentMethod ?? null
            },
      paymentDraft: drawerPaymentDraft,
      onPaymentDraftChange: setDrawerPaymentDraft,
      isSavingPayment:
        updateManualPaymentMutation.isPending || updateBookedPaymentMutation.isPending,
      onSavePayment: handleSavePayment,
      onReschedule: () => {
        setExpandedBookedAction(expandedBookedAction === "reschedule" ? null : "reschedule");
      },
      ...(selectedBookedAppointment.startAt > nowDate
        ? {
            onChangeModality: () => {
              setLocalSubmitErrorMessage(null);
              setSubmitSuccessMessage(null);
              setExpandedBookedAction("change-modality");
            }
          }
        : {}),
      onCancel: handleCancelAppointment,
      errorMessage: localSubmitErrorMessage ?? submitErrorMessage,
      successMessage: forDrawer ? null : submitSuccessMessage
    } as const;
  }

  return (
    <appShellModule.AppShell>
      {/* Header */}
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
              void queryClient.invalidateQueries({
                queryKey: useAgendaDataModule.schedulingRequestsQueryKey
              });
              void queryClient.invalidateQueries({
                queryKey: useAgendaDataModule.googleCalendarConnectionQueryKey
              });
              void queryClient.invalidateQueries({
                queryKey: useAgendaDataModule.patientsQueryKey
              });
              void queryClient.invalidateQueries({
                queryKey: useAgendaDataModule.manualAppointmentsQueryKey
              });
              void queryClient.invalidateQueries({
                queryKey: ["google-calendar-availability"]
              });
            }}
            type="button"
          >
            Refrescar
          </button>
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap gap-2">
          {useSchedulingRequestsModule.agendaStatuses.map((tab) => (
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
                setSelectedBookedItemKey(null);
                setSubmitSuccessMessage(null);
                setLocalSubmitErrorMessage(null);
                setMobileBookedStep("calendar");
              }}
              type="button"
            >
              {tab.label} ({requestCountByStatus.get(tab.status) ?? 0})
            </button>
          ))}
        </div>
      </section>

      {/* Main content */}
      <section className="mt-4">
        <div
          className={["grid gap-4", isBookedTab ? "" : "lg:grid-cols-[320px_minmax(0,1fr)]"].join(
            " "
          )}
        >
          {isBookedTab ? (
            <appointmentCalendarModule.AppointmentCalendar
              visibleMonthStart={visibleMonthStart}
              nowDate={nowDate}
              timezone={timezone}
              bookedAppointmentsByDay={bookedAppointmentsByDay}
              selectedDayIso={selectedDayIso}
              selectedBookedItemKey={selectedBookedItemKey}
              desktopDrawerOpen={desktopDrawerOpen}
              mobileBookedStep={mobileBookedStep}
              selectedDayAppointments={selectedDayAppointments}
              onPreviousMonth={() => {
                const previous = visibleMonthStart.minus({ months: 1 });
                setVisibleMonth({
                  year: previous.year,
                  month: previous.month as luxonModule.MonthNumbers
                });
              }}
              onNextMonth={() => {
                const next = visibleMonthStart.plus({ months: 1 });
                setVisibleMonth({
                  year: next.year,
                  month: next.month as luxonModule.MonthNumbers
                });
              }}
              onDayClick={(isoDate, dayAppointments) => {
                setSelectedDayIso(isoDate);
                const firstAppointment = dayAppointments[0];
                if (firstAppointment !== undefined) {
                  setSelectedBookedItemKey(firstAppointment.itemKey);
                  setSelectedRequestId(firstAppointment.requestId);
                  setMobileBookedStep("dayList");
                }
              }}
              onMobileAppointmentClick={(appointment) => {
                setSelectedDayIso(appointment.dayIso);
                setSelectedBookedItemKey(appointment.itemKey);
                setSelectedRequestId(appointment.requestId);
                setSubmitSuccessMessage(null);
                setLocalSubmitErrorMessage(null);
                setMobileBookedStep("detail");
              }}
              onDesktopAppointmentClick={(appointment) => {
                setSelectedDayIso(appointment.dayIso);
                setSelectedBookedItemKey(appointment.itemKey);
                setSelectedRequestId(appointment.requestId);
                setSubmitSuccessMessage(null);
                setLocalSubmitErrorMessage(null);
                setExpandedBookedAction(null);
                setDesktopDrawerOpen(true);
              }}
              onNewManualClick={() => setIsNewManualModalOpen(true)}
              onMobileDayListBack={() => setMobileBookedStep("calendar")}
            />
          ) : (
            <schedulingRequestListModule.SchedulingRequestList
              activeTab={activeTab}
              isLoading={requestsQuery.isLoading}
              filteredRequests={filteredRequests}
              selectedRequestId={selectedRequestId}
              patientsByWhatsappUserId={patientsByWhatsappUserId}
              onSelectRequest={(requestId) => {
                setSelectedRequestId(requestId);
                setSubmitSuccessMessage(null);
                setLocalSubmitErrorMessage(null);
              }}
            />
          )}

          {/* Detail panel */}
          <article
            className={[
              "space-y-4 rounded-xl border border-border-subtle bg-white p-3 shadow-card sm:p-4",
              isBookedTab && mobileBookedStep !== "detail" ? "hidden" : "",
              isBookedTab && mobileBookedStep === "detail" ? "sm:hidden" : ""
            ].join(" ")}
          >
            {isBookedTab && mobileBookedStep === "detail" ? (
              <button
                className="flex items-center gap-1 text-xs font-semibold text-brand-teal sm:hidden"
                onClick={() => setMobileBookedStep("dayList")}
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

            {isBookedTab && selectedBookedAppointment !== null
              ? (() => {
                  const detailProps = buildDetailCardProps(false);
                  if (detailProps === null) return null;
                  return <appointmentDetailCardModule.AppointmentDetailCard {...detailProps} />;
                })()
              : null}

            {/* Reschedule panel (inline mobile/desktop, non-drawer) */}
            {isBookedTab &&
            selectedBookedAppointment !== null &&
            expandedBookedAction === "reschedule" ? (
              <reschedulePanelModule.ReschedulePanel
                selectedBookedAppointment={selectedBookedAppointment}
                rescheduleBusyIntervals={rescheduleBusyIntervals}
                rescheduleSelectedSlots={rescheduleSelectedSlots}
                isLoadingAvailability={rescheduleAvailabilityQuery.isLoading}
                isPending={
                  rescheduleManualAppointmentMutation.isPending ||
                  rescheduleBookedSlotMutation.isPending
                }
                testId="reschedule-slotpicker-panel"
                onSelectedSlotsChange={setRescheduleSelectedSlots}
                onMonthChange={setRescheduleSlotPickerMonth}
                onConfirm={handleRescheduleConfirm}
                onCancel={() => {
                  setExpandedBookedAction(null);
                  setRescheduleSelectedSlots([]);
                }}
              />
            ) : null}

            {/* Change modality panel (inline) */}
            {isBookedTab &&
            selectedBookedAppointment !== null &&
            expandedBookedAction === "change-modality" ? (
              <changeModalityPanelModule.ChangeModalityPanel
                selectedBookedAppointment={selectedBookedAppointment}
                timezone={timezone}
                isPending={changeModalityMutation.isPending}
                onConfirm={(source, id, newModality) => {
                  setLocalSubmitErrorMessage(null);
                  setSubmitSuccessMessage(null);
                  changeModalityMutation.mutate({ source, id, newModality });
                  setExpandedBookedAction(null);
                }}
                onCancel={() => setExpandedBookedAction(null)}
              />
            ) : null}

            {/* Non-booked tab: request details */}
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
                <section className="rounded-lg border border-border-subtle p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-brand-ink">
                      Información del paciente
                    </h4>
                    <statusBadgeModule.StatusBadge
                      label={
                        useSchedulingRequestsModule.approvalStatusLabels[selectedRequest.status]
                          ?.label ?? selectedRequest.status
                      }
                      tone={
                        useSchedulingRequestsModule.approvalStatusLabels[selectedRequest.status]
                          ?.tone ?? "neutral"
                      }
                    />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2 text-sm text-slate-700">
                      <p>
                        <span className="font-semibold text-slate-500">Nombre</span>
                        <br />
                        {useBookedAppointmentsModule.resolvePatientDisplayName(
                          selectedRequest,
                          patientsByWhatsappUserId
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
                  {isBookedTab && selectedBookedAppointment !== null ? (
                    <div className="mt-3 rounded-md bg-brand-accent-light p-3">
                      <p className="text-xs font-semibold text-brand-teal">Cita agendada</p>
                      <p className="mt-1 text-sm text-brand-ink">
                        {selectedBookedAppointment.startAt.toFormat("dd LLL yyyy HH:mm")} -{" "}
                        {selectedBookedAppointment.endAt.toFormat("HH:mm")}
                      </p>
                    </div>
                  ) : null}
                </section>

                {selectedRequest.status === "BOOKED" ||
                selectedRequest.status === "SESSION_CLOSED" ? (
                  <section className="rounded-lg border border-border-subtle p-3">
                    <h4 className="text-sm font-semibold text-brand-ink">
                      Gestionar cita del chatbot
                    </h4>
                    <div className="mt-2 flex items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ${selectedRequest.paymentStatus === "PAID" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}
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
                        className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${expandedBookedAction === "reschedule" ? "bg-brand-teal text-white" : "border border-brand-teal text-brand-teal hover:bg-brand-accent-light"}`}
                        onClick={() =>
                          setExpandedBookedAction(
                            expandedBookedAction === "reschedule" ? null : "reschedule"
                          )
                        }
                        type="button"
                      >
                        Reprogramar
                      </button>
                      <button
                        className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${expandedBookedAction === "cancel" ? "bg-rose-600 text-white" : "border border-rose-600 text-rose-600 hover:bg-rose-50"}`}
                        onClick={() =>
                          setExpandedBookedAction(
                            expandedBookedAction === "cancel" ? null : "cancel"
                          )
                        }
                        type="button"
                      >
                        Cancelar
                      </button>
                      {selectedRequest.paymentStatus !== "PAID" ? (
                        <button
                          className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors ${expandedBookedAction === "payment" ? "bg-brand-teal text-white" : "border border-brand-teal text-brand-teal hover:bg-brand-accent-light"}`}
                          onClick={() =>
                            setExpandedBookedAction(
                              expandedBookedAction === "payment" ? null : "payment"
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
                          disabled={resolvePaymentReviewMutation.isPending}
                          onClick={() => {
                            if (selectedBookedBotRequest === null) {
                              return;
                            }
                            setLocalSubmitErrorMessage(null);
                            setSubmitSuccessMessage(null);
                            resolvePaymentReviewMutation.mutate({
                              request: selectedRequest,
                              decision: "SEND_REMINDER",
                              professionalNote: null,
                              paymentAmountCop: null,
                              paymentCurrency: "COP"
                            });
                          }}
                          type="button"
                        >
                          {resolvePaymentReviewMutation.isPending
                            ? "Enviando..."
                            : "Recordatorio de pago"}
                        </button>
                      ) : null}
                    </div>

                    {expandedBookedAction === "reschedule" && selectedBookedAppointment !== null ? (
                      <div className="mt-3">
                        <reschedulePanelModule.ReschedulePanel
                          selectedBookedAppointment={selectedBookedAppointment}
                          rescheduleBusyIntervals={rescheduleBusyIntervals}
                          rescheduleSelectedSlots={rescheduleSelectedSlots}
                          isLoadingAvailability={rescheduleAvailabilityQuery.isLoading}
                          isPending={rescheduleBookedSlotMutation.isPending}
                          testId="reschedule-slotpicker-bot"
                          onSelectedSlotsChange={setRescheduleSelectedSlots}
                          onMonthChange={setRescheduleSlotPickerMonth}
                          onConfirm={handleRescheduleConfirm}
                          onCancel={() => {
                            setExpandedBookedAction(null);
                            setRescheduleSelectedSlots([]);
                          }}
                        />
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
                            disabled={cancelBookedSlotMutation.isPending}
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
                              cancelBookedSlotMutation.mutate({
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
                            {cancelBookedSlotMutation.isPending ? "Cancelando..." : "Cancelar cita"}
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
                            disabled={updateBookedPaymentMutation.isPending}
                            onClick={() => {
                              if (selectedBookedBotRequest === null) {
                                return;
                              }
                              const paymentAmountCop = Number.parseInt(
                                bookedPaymentFormState.paymentAmountCop,
                                10
                              );
                              if (Number.isNaN(paymentAmountCop) || paymentAmountCop <= 0) {
                                setLocalSubmitErrorMessage(
                                  "El valor del pago debe ser mayor a cero."
                                );
                                return;
                              }
                              setLocalSubmitErrorMessage(null);
                              setSubmitSuccessMessage(null);
                              updateBookedPaymentMutation.mutate({
                                requestId: selectedBookedBotRequest.requestId,
                                input: {
                                  paymentAmountCop,
                                  paymentCurrency:
                                    selectedBookedBotRequest.paymentCurrency ?? "COP",
                                  paymentMethod: bookedPaymentFormState.paymentMethod,
                                  paymentStatus: bookedPaymentFormState.paymentStatus
                                }
                              });
                            }}
                            type="button"
                          >
                            {updateBookedPaymentMutation.isPending
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

            {loadingErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner message={loadingErrorMessage} />
            ) : null}
            {submitErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner message={submitErrorMessage} />
            ) : null}
            {localSubmitErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner message={localSubmitErrorMessage} />
            ) : null}
            {submitSuccessMessage !== null ? (
              <div className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                {submitSuccessMessage}
              </div>
            ) : null}
          </article>
        </div>

        {/* Desktop drawer — only for booked tab */}
        {isBookedTab ? (
          <appointmentDrawerModule.AppointmentDrawer
            isOpen={desktopDrawerOpen && selectedBookedAppointment !== null}
            onClose={() => {
              setDesktopDrawerOpen(false);
              setExpandedBookedAction(null);
              setLocalSubmitErrorMessage(null);
              setSubmitSuccessMessage(null);
            }}
          >
            {selectedBookedAppointment !== null
              ? (() => {
                  const detailProps = buildDetailCardProps(true);
                  if (detailProps === null) return null;
                  return (
                    <>
                      <appointmentDetailCardModule.AppointmentDetailCard
                        {...detailProps}
                        successMessage={submitSuccessMessage}
                      />

                      {expandedBookedAction === "change-modality" ? (
                        <changeModalityPanelModule.ChangeModalityPanel
                          selectedBookedAppointment={selectedBookedAppointment}
                          timezone={timezone}
                          isPending={changeModalityMutation.isPending}
                          wrapperClassName="border-t border-border-subtle px-5 py-4 space-y-4"
                          onConfirm={(source, id, newModality) => {
                            setLocalSubmitErrorMessage(null);
                            setSubmitSuccessMessage(null);
                            changeModalityMutation.mutate({ source, id, newModality });
                            setExpandedBookedAction(null);
                          }}
                          onCancel={() => setExpandedBookedAction(null)}
                        />
                      ) : null}

                      {expandedBookedAction === "reschedule" ? (
                        <div className="border-t border-border-subtle px-5 py-4">
                          <reschedulePanelModule.ReschedulePanel
                            selectedBookedAppointment={selectedBookedAppointment}
                            rescheduleBusyIntervals={rescheduleBusyIntervals}
                            rescheduleSelectedSlots={rescheduleSelectedSlots}
                            isLoadingAvailability={rescheduleAvailabilityQuery.isLoading}
                            isPending={
                              rescheduleManualAppointmentMutation.isPending ||
                              rescheduleBookedSlotMutation.isPending
                            }
                            testId="reschedule-slotpicker-drawer"
                            onSelectedSlotsChange={setRescheduleSelectedSlots}
                            onMonthChange={setRescheduleSlotPickerMonth}
                            onConfirm={handleRescheduleConfirm}
                            onCancel={() => {
                              setExpandedBookedAction(null);
                              setRescheduleSelectedSlots([]);
                            }}
                          />
                        </div>
                      ) : null}

                      {expandedBookedAction === "cancel" ? (
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
                                setBookedAppointmentFormState((currentValue) => ({
                                  ...currentValue,
                                  cancelReason: nextValue
                                }));
                              }}
                              value={bookedAppointmentFormState.cancelReason}
                            />
                          </label>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button
                              className="rounded-md bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                              disabled={
                                cancelBookedSlotMutation.isPending ||
                                cancelManualAppointmentMutation.isPending
                              }
                              onClick={() => {
                                const isConfirmed = window.confirm(
                                  "¿Seguro que quieres cancelar esta cita?"
                                );
                                if (!isConfirmed) {
                                  return;
                                }
                                setLocalSubmitErrorMessage(null);
                                setSubmitSuccessMessage(null);
                                if (
                                  selectedBookedAppointment.source === "BOT" &&
                                  selectedBookedBotRequest !== null
                                ) {
                                  cancelBookedSlotMutation.mutate({
                                    requestId: selectedBookedBotRequest.requestId,
                                    input: {
                                      reason:
                                        bookedAppointmentFormState.cancelReason.trim() === ""
                                          ? null
                                          : bookedAppointmentFormState.cancelReason.trim()
                                    }
                                  });
                                } else if (
                                  selectedBookedAppointment.source === "MANUAL" &&
                                  selectedBookedAppointment.manualAppointmentId !== null
                                ) {
                                  cancelManualAppointmentMutation.mutate({
                                    appointmentId: selectedBookedAppointment.manualAppointmentId,
                                    input: {
                                      reason:
                                        bookedAppointmentFormState.cancelReason.trim() === ""
                                          ? null
                                          : bookedAppointmentFormState.cancelReason.trim()
                                    }
                                  });
                                }
                              }}
                              type="button"
                            >
                              {cancelBookedSlotMutation.isPending ||
                              cancelManualAppointmentMutation.isPending
                                ? "Cancelando..."
                                : "Cancelar cita"}
                            </button>
                            <button
                              className="rounded-lg border border-border-subtle px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                              onClick={() => setExpandedBookedAction(null)}
                              type="button"
                            >
                              Cerrar
                            </button>
                          </div>
                        </div>
                      ) : null}
                    </>
                  );
                })()
              : null}
          </appointmentDrawerModule.AppointmentDrawer>
        ) : null}
      </section>

      <NewManualAppointmentModal
        isOpen={isNewManualModalOpen}
        onClose={() => setIsNewManualModalOpen(false)}
        onCreated={() => {
          void queryClient.invalidateQueries({
            queryKey: useAgendaDataModule.manualAppointmentsQueryKey
          });
        }}
      />
    </appShellModule.AppShell>
  );
}

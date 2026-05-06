import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appointmentDetailCardModule from "@adapters/inbound/react/components/AppointmentDetailCard";
import type { AppointmentDetailCardProps } from "@adapters/inbound/react/components/AppointmentDetailCard";
import * as appointmentDrawerModule from "@adapters/inbound/react/components/AppointmentDrawer";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import { NewManualAppointmentModal } from "@adapters/inbound/react/components/NewManualAppointmentModal";
import { AppointmentCalendar } from "@adapters/inbound/react/components/agenda/AppointmentCalendar";
import { ChangeModalityPanel } from "@adapters/inbound/react/components/agenda/ChangeModalityPanel";
import { ReschedulePanel } from "@adapters/inbound/react/components/agenda/ReschedulePanel";
import { SchedulingRequestDetail } from "@adapters/inbound/react/components/agenda/SchedulingRequestDetail";
import { SchedulingRequestList } from "@adapters/inbound/react/components/agenda/SchedulingRequestList";
import { useAgendaActions } from "@adapters/inbound/react/hooks/useAgendaActions";
import * as useAgendaQueryModule from "@adapters/inbound/react/hooks/useAgendaQuery";
import { useBookedAppointments } from "@adapters/inbound/react/hooks/useBookedAppointments";
import { useReschedule } from "@adapters/inbound/react/hooks/useReschedule";
import type * as schedulingModel from "@domain/models/scheduling";
import * as uiErrorModule from "@shared/http/ui_error";

const agendaStatuses: {
  status: schedulingModel.SchedulingRequestStatus;
  label: string;
}[] = [
  { status: "BOOKED", label: "Agendadas" },
  { status: "SESSION_CLOSED", label: "Cerradas" },
  { status: "CANCELLED", label: "Canceladas" },
  { status: "HUMAN_HANDOFF", label: "Human Handoff" }
];

interface BookedAppointmentFormState {
  cancelReason: string;
}

interface PaymentFormState {
  paymentAmountCop: string;
  paymentMethod: "CASH" | "TRANSFER";
  paymentStatus: "PENDING" | "PAID";
}

function emptyBookedAppointmentForm(): BookedAppointmentFormState {
  return { cancelReason: "" };
}

function emptyPaymentForm(): PaymentFormState {
  return { paymentAmountCop: "", paymentMethod: "CASH", paymentStatus: "PENDING" };
}

interface AgendaViewProps {
  tenantId?: string;
}

export function AgendaView({ tenantId }: AgendaViewProps) {
  const queryClient = reactQueryModule.useQueryClient();
  const nowDate = luxonModule.DateTime.now();

  // ── Data queries ──────────────────────────────────────────────────────────
  const requestsQuery = useAgendaQueryModule.useAgendaSchedulingRequestsQuery(tenantId);
  const googleCalendarConnectionQuery =
    useAgendaQueryModule.useAgendaGoogleCalendarConnectionQuery(tenantId);
  const patientsQuery = useAgendaQueryModule.useAgendaPatientsQuery(tenantId);
  const manualAppointmentsQuery = useAgendaQueryModule.useAgendaManualAppointmentsQuery(tenantId);

  // ── Tab / selection state ─────────────────────────────────────────────────
  const [activeTab, setActiveTab] =
    reactModule.useState<schedulingModel.SchedulingRequestStatus>("BOOKED");
  const [selectedRequestId, setSelectedRequestId] = reactModule.useState<string | null>(null);
  const [selectedBookedItemKey, setSelectedBookedItemKey] = reactModule.useState<string | null>(
    null
  );
  const [isBookedTab] = [activeTab === "BOOKED"];

  // ── Calendar navigation state ─────────────────────────────────────────────
  const [visibleMonth, setVisibleMonth] = reactModule.useState({
    year: nowDate.year,
    month: nowDate.month
  });
  const [selectedDayIso, setSelectedDayIso] = reactModule.useState<string>(() => {
    const isoDay = nowDate.toISODate();
    return isoDay ?? "";
  });
  const [mobileBookedStep, setMobileBookedStep] = reactModule.useState<
    "calendar" | "dayList" | "detail"
  >("calendar");

  // ── Feedback state ────────────────────────────────────────────────────────
  const [localSubmitErrorMessage, setLocalSubmitErrorMessage] = reactModule.useState<string | null>(
    null
  );
  const [submitSuccessMessage, setSubmitSuccessMessage] = reactModule.useState<string | null>(null);

  // ── Appointment forms / drawer state ─────────────────────────────────────
  const [bookedAppointmentFormState, setBookedAppointmentFormState] =
    reactModule.useState<BookedAppointmentFormState>(emptyBookedAppointmentForm());
  const [bookedPaymentFormState, setBookedPaymentFormState] =
    reactModule.useState<PaymentFormState>(emptyPaymentForm());
  const [expandedBookedAction, setExpandedBookedAction] = reactModule.useState<
    "reschedule" | "cancel" | "payment" | "change-modality" | null
  >(null);
  const [desktopDrawerOpen, setDesktopDrawerOpen] = reactModule.useState(false);
  const [drawerPaymentDraft, setDrawerPaymentDraft] = reactModule.useState<{
    amountCop: string;
    category: string;
  }>({ amountCop: "", category: "CASH" });
  const [isNewManualModalOpen, setIsNewManualModalOpen] = reactModule.useState(false);

  // ── Derived data ──────────────────────────────────────────────────────────
  const allRequests = requestsQuery.data ?? [];
  const allPatients = patientsQuery.data ?? [];
  const allManualAppointments = manualAppointmentsQuery.data ?? [];
  const timezone = googleCalendarConnectionQuery.data?.professionalTimezone ?? "UTC";

  const requestCountByStatus = reactModule.useMemo(() => {
    const countMap = new Map<schedulingModel.SchedulingRequestStatus, number>();
    allRequests.forEach((request) => {
      const currentCount = countMap.get(request.status) ?? 0;
      countMap.set(request.status, currentCount + 1);
    });
    return countMap;
  }, [allRequests]);

  const filteredRequests = reactModule.useMemo(() => {
    return allRequests.filter((request) => request.status === activeTab);
  }, [allRequests, activeTab]);

  const patientsByWhatsappUserId = reactModule.useMemo(() => {
    const map = new Map<string, (typeof allPatients)[0]>();
    allPatients.forEach((patient) => {
      map.set(patient.whatsappUserId, patient);
    });
    return map;
  }, [allPatients]);

  // ── Booked appointments hook ──────────────────────────────────────────────
  const { bookedAppointments, bookedAppointmentsByDay } = useBookedAppointments({
    allRequests,
    allManualAppointments,
    patientsByWhatsappUserId,
    isBookedTab,
    timezone
  });

  // ── Selected appointment derived values ───────────────────────────────────
  const selectedRequest = allRequests.find((request) => request.requestId === selectedRequestId);

  const selectedBookedAppointment = reactModule.useMemo(() => {
    if (!isBookedTab || selectedBookedItemKey === null) {
      return null;
    }
    const appointment = bookedAppointments.find(
      (currentAppointment) => currentAppointment.itemKey === selectedBookedItemKey
    );
    return appointment ?? null;
  }, [bookedAppointments, isBookedTab, selectedBookedItemKey]);

  const selectedDayAppointments = reactModule.useMemo(() => {
    if (!isBookedTab || selectedDayIso === "") {
      return [];
    }
    return bookedAppointmentsByDay.get(selectedDayIso) ?? [];
  }, [bookedAppointmentsByDay, isBookedTab, selectedDayIso]);

  const selectedBookedBotRequest =
    selectedBookedAppointment?.source === "BOT" ? selectedBookedAppointment.request : null;

  // ── Auto-select effects ───────────────────────────────────────────────────
  // Auto-select first request when switching to a non-booked tab
  reactModule.useEffect(() => {
    if (isBookedTab) {
      return;
    }
    if (filteredRequests.length === 0) {
      setSelectedRequestId(null);
      return;
    }
    const selectedExists = filteredRequests.some(
      (request) => request.requestId === selectedRequestId
    );
    if (!selectedExists) {
      const firstRequest = filteredRequests[0];
      if (firstRequest !== undefined) {
        setSelectedRequestId(firstRequest.requestId);
      }
    }
  }, [filteredRequests, isBookedTab, selectedRequestId]);

  // Reset selected day when month changes
  const visibleMonthStart = luxonModule.DateTime.fromObject(
    { year: visibleMonth.year, month: visibleMonth.month, day: 1 },
    { zone: timezone }
  ).startOf("day");

  reactModule.useEffect(() => {
    const firstDayIso = visibleMonthStart.toISODate();
    if (firstDayIso !== null) {
      setSelectedDayIso(firstDayIso);
    }
  }, [visibleMonthStart.year, visibleMonthStart.month]);

  // Auto-select first booked appointment
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

  // Reset forms when selected appointment changes
  reactModule.useEffect(() => {
    setExpandedBookedAction(null);
    setBookedAppointmentFormState(emptyBookedAppointmentForm());
  }, [selectedBookedAppointment, selectedBookedBotRequest, timezone]);

  reactModule.useEffect(() => {
    if (selectedBookedBotRequest === null) {
      setBookedPaymentFormState(emptyPaymentForm());
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

  // ── Reschedule hook ───────────────────────────────────────────────────────
  const {
    setRescheduleSlotPickerMonth,
    rescheduleSelectedSlots,
    setRescheduleSelectedSlots,
    rescheduleAvailabilityQuery,
    rescheduleBusyIntervals
  } = useReschedule({ expandedBookedAction, selectedBookedAppointment, tenantId });

  // ── Mutations / action handlers ───────────────────────────────────────────
  const {
    rescheduleManualAppointmentMutation,
    cancelManualAppointmentMutation,
    updateManualPaymentMutation,
    rescheduleBookedSlotMutation,
    cancelBookedSlotMutation,
    updateBookedPaymentMutation,
    changeModalityMutation,
    resolvePaymentReviewMutation,
    handleRescheduleManualAppointment,
    handleCancelManualAppointment,
    handleUpdateManualPayment,
    handleRescheduleBookedSlot,
    handleCancelBookedSlot,
    handleUpdateBookedPayment,
    handleChangeModality,
    handleResolvePaymentReview,
    submitErrorMessage
  } = useAgendaActions({
    tenantId,
    setSubmitSuccessMessage,
    setLocalSubmitErrorMessage,
    setActiveTab,
    setExpandedBookedAction
  });

  const loadingErrorMessage = uiErrorModule.resolveUiErrorMessage([
    requestsQuery.error,
    googleCalendarConnectionQuery.error,
    patientsQuery.error,
    manualAppointmentsQuery.error
  ]);

  // ── Calendar grid ─────────────────────────────────────────────────────────
  const firstWeekdayOffset = visibleMonthStart.weekday % 7;
  const monthDays = visibleMonthStart.daysInMonth ?? 0;
  const dayGrid: (luxonModule.DateTime | null)[] = [];
  for (let index = 0; index < firstWeekdayOffset; index += 1) {
    dayGrid.push(null);
  }
  for (let day = 1; day <= monthDays; day += 1) {
    dayGrid.push(visibleMonthStart.set({ day }));
  }

  // ── Query keys (for manual refresh) ──────────────────────────────────────
  const schedulingRequestsQueryKey =
    tenantId !== undefined ? ["admin", tenantId, "scheduling-requests"] : ["scheduling-requests"];
  const manualAppointmentsQueryKey =
    tenantId !== undefined ? ["admin", tenantId, "manual-appointments"] : ["manual-appointments"];
  const googleCalendarConnectionQueryKey =
    tenantId !== undefined
      ? ["admin", tenantId, "google-calendar-connection"]
      : ["google-calendar-connection"];
  const patientsQueryKey = tenantId !== undefined ? ["admin", tenantId, "patients"] : ["patients"];

  // ── Shared AppointmentDetailCard props builder ────────────────────────────
  function buildDetailCardProps(): AppointmentDetailCardProps | null {
    if (selectedBookedAppointment === null) {
      return null;
    }
    const modality: "VIRTUAL" | "PRESENCIAL" =
      selectedBookedAppointment.source === "MANUAL" &&
      selectedBookedAppointment.manualAppointment !== null
        ? selectedBookedAppointment.manualAppointment.isVirtual
          ? "VIRTUAL"
          : "PRESENCIAL"
        : selectedBookedAppointment.request?.appointmentModality === "PRESENCIAL"
          ? "PRESENCIAL"
          : "VIRTUAL";

    const payment =
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
          };

    const onSavePayment = () => {
      const amountCop = Number.parseInt(drawerPaymentDraft.amountCop, 10);
      if (Number.isNaN(amountCop) || amountCop <= 0) {
        setLocalSubmitErrorMessage("El valor del pago debe ser mayor a cero.");
        return;
      }
      setLocalSubmitErrorMessage(null);
      setSubmitSuccessMessage(null);
      if (
        selectedBookedAppointment.source === "MANUAL" &&
        selectedBookedAppointment.manualAppointmentId !== null
      ) {
        handleUpdateManualPayment({
          appointmentId: selectedBookedAppointment.manualAppointmentId,
          input: {
            paymentAmountCop: amountCop,
            paymentCurrency: selectedBookedAppointment.manualAppointment?.paymentCurrency ?? "COP",
            paymentMethod: drawerPaymentDraft.category as "CASH" | "TRANSFER",
            paymentStatus: "PAID"
          }
        });
      } else if (
        selectedBookedAppointment.source === "BOT" &&
        selectedBookedAppointment.requestId !== null
      ) {
        handleUpdateBookedPayment({
          requestId: selectedBookedAppointment.requestId,
          input: {
            paymentAmountCop: amountCop,
            paymentCurrency: selectedBookedAppointment.request?.paymentCurrency ?? "COP",
            paymentMethod: drawerPaymentDraft.category as "CASH" | "TRANSFER",
            paymentStatus: "PAID"
          }
        });
      }
    };

    const onCancel = () => {
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
        handleCancelBookedSlot({
          requestId: selectedBookedBotRequest.requestId,
          input: { reason: null }
        });
      } else if (
        selectedBookedAppointment.source === "MANUAL" &&
        selectedBookedAppointment.manualAppointmentId !== null
      ) {
        handleCancelManualAppointment({
          appointmentId: selectedBookedAppointment.manualAppointmentId,
          input: { reason: null }
        });
      }
    };

    const changeModalityProp =
      selectedBookedAppointment.startAt > nowDate
        ? {
            onChangeModality: () => {
              setLocalSubmitErrorMessage(null);
              setSubmitSuccessMessage(null);
              setExpandedBookedAction("change-modality");
            }
          }
        : {};

    return {
      origin: (selectedBookedAppointment.source === "MANUAL" ? "MANUAL" : "CHATBOT") satisfies
        | "MANUAL"
        | "CHATBOT",
      modality,
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
      payment,
      paymentDraft: drawerPaymentDraft,
      onPaymentDraftChange: setDrawerPaymentDraft,
      isSavingPayment:
        updateManualPaymentMutation.isPending || updateBookedPaymentMutation.isPending,
      onSavePayment,
      onReschedule: () => {
        setExpandedBookedAction(expandedBookedAction === "reschedule" ? null : "reschedule");
      },
      ...changeModalityProp,
      onCancel,
      errorMessage: localSubmitErrorMessage ?? submitErrorMessage,
      successMessage: submitSuccessMessage
    };
  }

  const detailCardProps = buildDetailCardProps();

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <section className="space-y-4">
      {/* Header */}
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
              queryKey:
                tenantId !== undefined
                  ? ["admin", tenantId, "google-calendar-availability"]
                  : ["google-calendar-availability"]
            });
          }}
          type="button"
        >
          Refrescar
        </button>
      </div>

      {/* Tab bar */}
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

      {/* Main content grid */}
      <div
        className={["grid gap-4", isBookedTab ? "" : "lg:grid-cols-[320px_minmax(0,1fr)]"].join(
          " "
        )}
      >
        {/* Left panel: calendar or request list */}
        {isBookedTab ? (
          <AppointmentCalendar
            visibleMonthStart={visibleMonthStart}
            dayGrid={dayGrid}
            bookedAppointmentsByDay={bookedAppointmentsByDay}
            selectedDayIso={selectedDayIso}
            selectedBookedItemKey={selectedBookedItemKey}
            desktopDrawerOpen={desktopDrawerOpen}
            nowDate={nowDate}
            timezone={timezone}
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
            onDayClick={(isoDate, firstAppointment) => {
              setSelectedDayIso(isoDate);
              if (firstAppointment !== undefined) {
                setSelectedBookedItemKey(firstAppointment.itemKey);
                setSelectedRequestId(firstAppointment.requestId);
                setMobileBookedStep("dayList");
              }
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
            onMobileAppointmentClick={(appointment) => {
              setSelectedDayIso(appointment.dayIso);
              setSelectedBookedItemKey(appointment.itemKey);
              setSelectedRequestId(appointment.requestId);
              setSubmitSuccessMessage(null);
              setLocalSubmitErrorMessage(null);
              setMobileBookedStep("detail");
            }}
            onNewManualAppointment={() => setIsNewManualModalOpen(true)}
            onMobileBackToCalendar={() => setMobileBookedStep("calendar")}
          />
        ) : (
          <SchedulingRequestList
            activeTab={activeTab}
            filteredRequests={filteredRequests}
            selectedRequestId={selectedRequestId}
            patientsByWhatsappUserId={patientsByWhatsappUserId}
            isLoading={requestsQuery.isLoading}
            onSelectRequest={(requestId) => {
              setSelectedRequestId(requestId);
              setSubmitSuccessMessage(null);
              setLocalSubmitErrorMessage(null);
            }}
          />
        )}

        {/* Right panel: detail */}
        <article
          className={[
            "space-y-4 rounded-xl border border-border-subtle bg-white p-3 shadow-card sm:p-4",
            isBookedTab && mobileBookedStep !== "detail" ? "hidden" : "",
            isBookedTab && mobileBookedStep === "detail" ? "sm:hidden" : ""
          ].join(" ")}
        >
          {/* Mobile back button */}
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

          {/* Booked appointment detail card (mobile inline view — only rendered in mobile detail step) */}
          {isBookedTab && mobileBookedStep === "detail" && detailCardProps !== null ? (
            <appointmentDetailCardModule.AppointmentDetailCard {...detailCardProps} />
          ) : null}

          {/* Reschedule panel — inline (mobile and desktop without drawer) */}
          {isBookedTab &&
          selectedBookedAppointment !== null &&
          expandedBookedAction === "reschedule" ? (
            <ReschedulePanel
              selectedBookedAppointment={selectedBookedAppointment}
              rescheduleBusyIntervals={rescheduleBusyIntervals}
              rescheduleSelectedSlots={rescheduleSelectedSlots}
              onSelectedSlotsChange={setRescheduleSelectedSlots}
              isLoadingAvailability={rescheduleAvailabilityQuery.isLoading}
              onMonthChange={setRescheduleSlotPickerMonth}
              isSaving={
                rescheduleManualAppointmentMutation.isPending ||
                rescheduleBookedSlotMutation.isPending
              }
              onConfirm={() => {
                const slot = rescheduleSelectedSlots[0];
                if (slot === undefined) {
                  return;
                }
                setLocalSubmitErrorMessage(null);
                setSubmitSuccessMessage(null);
                if (
                  selectedBookedAppointment.source === "MANUAL" &&
                  selectedBookedAppointment.manualAppointmentId !== null
                ) {
                  handleRescheduleManualAppointment({
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
                } else if (
                  selectedBookedAppointment.source === "BOT" &&
                  selectedBookedBotRequest !== null
                ) {
                  const eventSummary =
                    selectedBookedAppointment.patientDisplayName.trim() === ""
                      ? "Cita"
                      : `Cita - ${selectedBookedAppointment.patientDisplayName}`;
                  handleRescheduleBookedSlot({
                    requestId: selectedBookedBotRequest.requestId,
                    input: {
                      startAt: slot.startAt,
                      endAt: slot.endAt,
                      timezone: slot.timezone,
                      eventSummary
                    }
                  });
                }
              }}
              onCancel={() => {
                setExpandedBookedAction(null);
                setRescheduleSelectedSlots([]);
              }}
            />
          ) : null}

          {/* Change modality panel — inline */}
          {isBookedTab &&
          selectedBookedAppointment !== null &&
          expandedBookedAction === "change-modality" ? (
            <ChangeModalityPanel
              selectedBookedAppointment={selectedBookedAppointment}
              timezone={timezone}
              isSaving={changeModalityMutation.isPending}
              onConfirm={handleChangeModality}
              onCancel={() => setExpandedBookedAction(null)}
            />
          ) : null}

          {/* Empty state / request detail */}
          {isBookedTab && selectedBookedAppointment === null ? (
            <p className="text-sm text-slate-500">
              Selecciona una cita en el calendario para ver todos los detalles.
            </p>
          ) : !isBookedTab && selectedRequest === undefined ? (
            <p className="text-sm text-slate-500">
              Selecciona una solicitud para ver detalle y gestionar slots.
            </p>
          ) : !isBookedTab && selectedRequest !== undefined ? (
            <SchedulingRequestDetail
              selectedRequest={selectedRequest}
              patientsByWhatsappUserId={patientsByWhatsappUserId}
              selectedBookedAppointment={selectedBookedAppointment}
              expandedBookedAction={expandedBookedAction}
              setExpandedBookedAction={setExpandedBookedAction}
              bookedAppointmentFormState={bookedAppointmentFormState}
              setBookedAppointmentFormState={setBookedAppointmentFormState}
              bookedPaymentFormState={bookedPaymentFormState}
              setBookedPaymentFormState={setBookedPaymentFormState}
              rescheduleBusyIntervals={rescheduleBusyIntervals}
              rescheduleSelectedSlots={rescheduleSelectedSlots}
              setRescheduleSelectedSlots={setRescheduleSelectedSlots}
              isLoadingAvailability={rescheduleAvailabilityQuery.isLoading}
              onRescheduleMonthChange={setRescheduleSlotPickerMonth}
              onRescheduleBookedSlot={handleRescheduleBookedSlot}
              onCancelBookedSlot={handleCancelBookedSlot}
              onUpdateBookedPayment={handleUpdateBookedPayment}
              onResolvePaymentReview={handleResolvePaymentReview}
              isReschedulingBotSlot={rescheduleBookedSlotMutation.isPending}
              isCancellingBotSlot={cancelBookedSlotMutation.isPending}
              isUpdatingBotPayment={updateBookedPaymentMutation.isPending}
              isResolvingPaymentReview={resolvePaymentReviewMutation.isPending}
              setLocalSubmitErrorMessage={setLocalSubmitErrorMessage}
              setSubmitSuccessMessage={setSubmitSuccessMessage}
            />
          ) : null}

          {/* Error / success banners */}
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

      {/* Desktop drawer — booked tab only */}
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
          {selectedBookedAppointment !== null && detailCardProps !== null ? (
            <>
              <appointmentDetailCardModule.AppointmentDetailCard {...detailCardProps} />

              {/* Change-modality panel in drawer */}
              {expandedBookedAction === "change-modality" ? (
                <ChangeModalityPanel
                  selectedBookedAppointment={selectedBookedAppointment}
                  timezone={timezone}
                  isSaving={changeModalityMutation.isPending}
                  onConfirm={handleChangeModality}
                  onCancel={() => setExpandedBookedAction(null)}
                  wrapperClassName="border-t border-border-subtle px-5 py-4 space-y-4"
                />
              ) : null}

              {/* Reschedule panel in drawer */}
              {expandedBookedAction === "reschedule" ? (
                <ReschedulePanel
                  selectedBookedAppointment={selectedBookedAppointment}
                  rescheduleBusyIntervals={rescheduleBusyIntervals}
                  rescheduleSelectedSlots={rescheduleSelectedSlots}
                  onSelectedSlotsChange={setRescheduleSelectedSlots}
                  isLoadingAvailability={rescheduleAvailabilityQuery.isLoading}
                  onMonthChange={setRescheduleSlotPickerMonth}
                  isSaving={
                    rescheduleManualAppointmentMutation.isPending ||
                    rescheduleBookedSlotMutation.isPending
                  }
                  onConfirm={() => {
                    const slot = rescheduleSelectedSlots[0];
                    if (slot === undefined) {
                      return;
                    }
                    setLocalSubmitErrorMessage(null);
                    setSubmitSuccessMessage(null);
                    if (
                      selectedBookedAppointment.source === "MANUAL" &&
                      selectedBookedAppointment.manualAppointmentId !== null
                    ) {
                      handleRescheduleManualAppointment({
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
                    } else if (
                      selectedBookedAppointment.source === "BOT" &&
                      selectedBookedBotRequest !== null
                    ) {
                      const eventSummary =
                        selectedBookedAppointment.patientDisplayName.trim() === ""
                          ? "Cita"
                          : `Cita - ${selectedBookedAppointment.patientDisplayName}`;
                      handleRescheduleBookedSlot({
                        requestId: selectedBookedBotRequest.requestId,
                        input: {
                          startAt: slot.startAt,
                          endAt: slot.endAt,
                          timezone: slot.timezone,
                          eventSummary
                        }
                      });
                    }
                  }}
                  onCancel={() => {
                    setExpandedBookedAction(null);
                    setRescheduleSelectedSlots([]);
                  }}
                  wrapperClassName="border-t border-border-subtle px-5 py-4 space-y-4"
                />
              ) : null}

              {/* Cancel panel in drawer */}
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
                          handleCancelBookedSlot({
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
                          handleCancelManualAppointment({
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
          ) : null}
        </appointmentDrawerModule.AppointmentDrawer>
      ) : null}

      <NewManualAppointmentModal
        isOpen={isNewManualModalOpen}
        onClose={() => setIsNewManualModalOpen(false)}
        onCreated={() => {
          void queryClient.invalidateQueries({ queryKey: manualAppointmentsQueryKey });
        }}
        {...(tenantId !== undefined ? { tenantId } : {})}
      />
    </section>
  );
}

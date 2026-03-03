import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import type * as schedulingModel from "@domain/models/scheduling";
import * as uiErrorModule from "@shared/http/ui_error";
import * as dateUtilsModule from "@shared/utils/date";

const schedulingRequestsQueryKey = ["scheduling-requests"] as const;
const googleCalendarConnectionQueryKey = ["google-calendar-connection"] as const;

interface SchedulingTabConfig {
  status: schedulingModel.SchedulingRequestStatus;
  label: string;
}

interface SchedulingTabGroup {
  groupId: "CONSULTATION" | "CALENDAR";
  title: string;
  helperText: string;
  tabs: SchedulingTabConfig[];
}

const consultationTabs: SchedulingTabConfig[] = [
  { status: "AWAITING_CONSULTATION_REVIEW", label: "Pendiente validar motivo" },
  { status: "AWAITING_CONSULTATION_DETAILS", label: "Esperando más detalle" },
  { status: "CONSULTATION_REJECTED", label: "Motivo rechazado" }
];

const calendarTabs: SchedulingTabConfig[] = [
  { status: "COLLECTING_PREFERENCES", label: "Recolectando preferencias" },
  { status: "AWAITING_PROFESSIONAL_SLOTS", label: "Pendientes de slots" },
  { status: "AWAITING_PATIENT_CHOICE", label: "Esperando paciente" },
  { status: "BOOKED", label: "Agendadas" },
  { status: "CANCELLED", label: "Canceladas" },
  { status: "HUMAN_HANDOFF", label: "Human handoff" }
];

const schedulingTabGroups: SchedulingTabGroup[] = [
  {
    groupId: "CONSULTATION",
    title: "Motivos de consulta",
    helperText: "Valida el motivo clínico y solicita detalle adicional si aplica.",
    tabs: consultationTabs
  },
  {
    groupId: "CALENDAR",
    title: "Calendario y agenda",
    helperText: "Gestiona preferencias, slots disponibles y resultado de agendamiento.",
    tabs: calendarTabs
  }
];

const weekDayLabels = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

interface BusyIntervalRange {
  start: luxonModule.DateTime;
  end: luxonModule.DateTime;
}

export interface CalendarSlotCandidate {
  slotId: string;
  startAt: string;
  endAt: string;
  timezone: string;
  isBusy: boolean;
  isPast: boolean;
}

export function buildCalendarSlotCandidates(params: {
  requestId: string;
  timezone: string;
  selectedDayIso: string;
  busyIntervals: BusyIntervalRange[];
  now: luxonModule.DateTime;
}): CalendarSlotCandidate[] {
  const selectedDay = luxonModule.DateTime.fromISO(params.selectedDayIso, {
    zone: params.timezone
  }).startOf("day");
  if (!selectedDay.isValid) {
    return [];
  }

  const slots: CalendarSlotCandidate[] = [];
  for (let hour = 6; hour < 22; hour += 1) {
    const startAt = selectedDay.set({
      hour,
      minute: 0,
      second: 0,
      millisecond: 0
    });
    const endAt = startAt.plus({ hours: 1 });
    const isBusy = params.busyIntervals.some((interval) => {
      return startAt < interval.end && interval.start < endAt;
    });
    const isPast = startAt <= params.now;
    const startAtIso = startAt.toISO();
    const endAtIso = endAt.toISO();
    if (startAtIso === null || endAtIso === null) {
      continue;
    }
    slots.push({
      slotId: `${params.requestId}_${startAt.toFormat("yyyyLLdd_HHmm")}`,
      startAt: startAtIso,
      endAt: endAtIso,
      timezone: params.timezone,
      isBusy,
      isPast
    });
  }
  return slots;
}

export function AgendaPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();
  const nowDate = luxonModule.DateTime.now();

  const requestsQuery = reactQueryModule.useQuery({
    queryKey: schedulingRequestsQueryKey,
    queryFn: () => appContainer.schedulingUseCase.listRequests()
  });
  const googleCalendarConnectionQuery = reactQueryModule.useQuery({
    queryKey: googleCalendarConnectionQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getGoogleCalendarConnectionStatus()
  });

  const [activeTab, setActiveTab] = reactModule.useState<schedulingModel.SchedulingRequestStatus>(
    "AWAITING_CONSULTATION_REVIEW"
  );
  const [selectedRequestId, setSelectedRequestId] = reactModule.useState<string | null>(null);
  const [visibleMonth, setVisibleMonth] = reactModule.useState({
    year: nowDate.year,
    month: nowDate.month
  });
  const [selectedDayIso, setSelectedDayIso] = reactModule.useState<string>(() => {
    const isoDay = nowDate.toISODate();
    return isoDay ?? "";
  });
  const [selectedSlotsByRequestId, setSelectedSlotsByRequestId] = reactModule.useState<
    Record<string, schedulingModel.ProfessionalSlotInput[]>
  >({});
  const [professionalNotesByRequestId, setProfessionalNotesByRequestId] = reactModule.useState<
    Record<string, string>
  >({});
  const [reviewNotesByRequestId, setReviewNotesByRequestId] = reactModule.useState<
    Record<string, string>
  >({});
  const [localSubmitErrorMessage, setLocalSubmitErrorMessage] = reactModule.useState<string | null>(
    null
  );
  const [submitSuccessMessage, setSubmitSuccessMessage] = reactModule.useState<string | null>(null);

  const allRequests = requestsQuery.data ?? [];
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

  reactModule.useEffect(() => {
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
  }, [filteredRequests, selectedRequestId]);

  const selectedRequest = allRequests.find((request) => request.requestId === selectedRequestId);
  const timezone = googleCalendarConnectionQuery.data?.professionalTimezone ?? "UTC";
  const visibleMonthStart = luxonModule.DateTime.fromObject(
    {
      year: visibleMonth.year,
      month: visibleMonth.month,
      day: 1
    },
    {
      zone: timezone
    }
  ).startOf("day");
  const visibleMonthEnd = visibleMonthStart.endOf("month");
  const monthRangeFromIso = visibleMonthStart.toISO();
  const monthRangeToIso = visibleMonthEnd.toISO();

  const availabilityQuery = reactQueryModule.useQuery({
    queryKey: ["google-calendar-availability", monthRangeFromIso, monthRangeToIso, timezone],
    enabled:
      selectedRequest?.status === "AWAITING_PROFESSIONAL_SLOTS" &&
      monthRangeFromIso !== null &&
      monthRangeToIso !== null,
    queryFn: async () => {
      if (monthRangeFromIso === null || monthRangeToIso === null) {
        throw new Error("month range is invalid");
      }
      return appContainer.schedulingUseCase.getAvailability(monthRangeFromIso, monthRangeToIso);
    }
  });

  reactModule.useEffect(() => {
    const firstDayIso = visibleMonthStart.toISODate();
    if (firstDayIso !== null) {
      setSelectedDayIso(firstDayIso);
    }
  }, [visibleMonthStart.year, visibleMonthStart.month]);

  const busyIntervals = reactModule.useMemo<BusyIntervalRange[]>(() => {
    if (availabilityQuery.data === undefined) {
      return [];
    }
    return availabilityQuery.data.busyIntervals
      .map((interval) => {
        const start = luxonModule.DateTime.fromISO(interval.startAt, { zone: timezone });
        const end = luxonModule.DateTime.fromISO(interval.endAt, { zone: timezone });
        if (!start.isValid || !end.isValid) {
          return null;
        }
        return {
          start,
          end
        };
      })
      .filter((interval): interval is BusyIntervalRange => interval !== null);
  }, [availabilityQuery.data, timezone]);

  const calendarSlots = reactModule.useMemo(() => {
    if (selectedRequest === undefined || selectedDayIso === "") {
      return [];
    }
    return buildCalendarSlotCandidates({
      requestId: selectedRequest.requestId,
      selectedDayIso,
      timezone,
      busyIntervals,
      now: luxonModule.DateTime.now().setZone(timezone)
    });
  }, [selectedRequest, selectedDayIso, timezone, busyIntervals]);

  const selectedSlots =
    selectedRequest !== undefined
      ? (selectedSlotsByRequestId[selectedRequest.requestId] ?? [])
      : [];
  const selectedSlotIdSet = new Set(selectedSlots.map((slot) => slot.slotId));
  const currentProfessionalNote =
    selectedRequest !== undefined
      ? (professionalNotesByRequestId[selectedRequest.requestId] ?? "")
      : "";
  const currentReviewNote =
    selectedRequest !== undefined ? (reviewNotesByRequestId[selectedRequest.requestId] ?? "") : "";

  const submitSlotsMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      slots: schedulingModel.ProfessionalSlotInput[];
      professionalNote: string | null;
    }) => {
      return appContainer.schedulingUseCase.submitProfessionalSlots(
        payload.request.conversationId,
        payload.request.requestId,
        {
          slots: payload.slots,
          professionalNote: payload.professionalNote
        }
      );
    },
    onSuccess: (result, payload) => {
      setSubmitSuccessMessage(result.assistantText);
      setLocalSubmitErrorMessage(null);
      setSelectedSlotsByRequestId((currentValue) => ({
        ...currentValue,
        [payload.request.requestId]: []
      }));
      queryClient.setQueryData<schedulingModel.SchedulingRequestSummary[]>(
        schedulingRequestsQueryKey,
        (currentValue) => {
          if (currentValue === undefined) {
            return currentValue;
          }
          return currentValue.map((request) => {
            if (request.requestId !== payload.request.requestId) {
              return request;
            }
            return {
              ...request,
              status: "AWAITING_PATIENT_CHOICE",
              updatedAt: luxonModule.DateTime.now().toISO() ?? request.updatedAt,
              professionalNote: payload.professionalNote,
              slots: payload.slots.map((slot) => ({
                slotId: slot.slotId,
                startAt: slot.startAt,
                endAt: slot.endAt,
                timezone: slot.timezone,
                status: "PROPOSED"
              }))
            };
          });
        }
      );
      setActiveTab("AWAITING_PATIENT_CHOICE");
    }
  });

  const resolveConsultationReviewMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      decision: "APPROVE" | "REQUEST_MORE_INFO" | "REJECT";
      professionalNote: string | null;
    }) => {
      return appContainer.schedulingUseCase.resolveConsultationReview(
        payload.request.conversationId,
        payload.request.requestId,
        {
          decision: payload.decision,
          professionalNote: payload.professionalNote
        }
      );
    },
    onSuccess: (result, payload) => {
      setSubmitSuccessMessage(result.assistantText);
      setLocalSubmitErrorMessage(null);
      queryClient.setQueryData<schedulingModel.SchedulingRequestSummary[]>(
        schedulingRequestsQueryKey,
        (currentValue) => {
          if (currentValue === undefined) {
            return currentValue;
          }
          return currentValue.map((request) => {
            if (request.requestId !== payload.request.requestId) {
              return request;
            }
            return {
              ...request,
              status: result.status,
              updatedAt: luxonModule.DateTime.now().toISO() ?? request.updatedAt,
              professionalNote: payload.professionalNote
            };
          });
        }
      );
      setActiveTab(result.status);
    }
  });

  const submitErrorMessage = uiErrorModule.resolveUiErrorMessage([
    submitSlotsMutation.error,
    resolveConsultationReviewMutation.error
  ]);
  const loadingErrorMessage = uiErrorModule.resolveUiErrorMessage([
    requestsQuery.error,
    googleCalendarConnectionQuery.error,
    availabilityQuery.error
  ]);

  const firstWeekdayOffset = visibleMonthStart.weekday % 7;
  const monthDays = visibleMonthStart.daysInMonth ?? 0;
  const dayGrid: (luxonModule.DateTime | null)[] = [];
  for (let index = 0; index < firstWeekdayOffset; index += 1) {
    dayGrid.push(null);
  }
  for (let day = 1; day <= monthDays; day += 1) {
    dayGrid.push(visibleMonthStart.set({ day }));
  }

  return (
    <appShellModule.AppShell>
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-brand-ink">Agenda profesional</h2>
            <p className="text-sm text-slate-600">
              Gestiona solicitudes y envía múltiples slots de 60 minutos.
            </p>
          </div>
          <button
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            onClick={() => {
              void queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey });
              void queryClient.invalidateQueries({ queryKey: googleCalendarConnectionQueryKey });
              void queryClient.invalidateQueries({
                queryKey: ["google-calendar-availability"]
              });
            }}
            type="button"
          >
            Refrescar
          </button>
        </div>

        <div className="grid gap-3 xl:grid-cols-2">
          {schedulingTabGroups.map((group) => (
            <section
              className="rounded-xl border border-slate-200 bg-white p-3"
              key={group.groupId}
            >
              <header className="mb-3">
                <h3 className="text-sm font-semibold text-brand-ink">{group.title}</h3>
                <p className="text-xs text-slate-500">{group.helperText}</p>
              </header>
              <div className="flex flex-wrap gap-2">
                {group.tabs.map((tab) => (
                  <button
                    className={[
                      "rounded-md border px-3 py-2 text-sm font-semibold",
                      activeTab === tab.status
                        ? "border-brand-teal bg-teal-50 text-brand-teal"
                        : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                    ].join(" ")}
                    key={tab.status}
                    onClick={() => {
                      setActiveTab(tab.status);
                      setSubmitSuccessMessage(null);
                      setLocalSubmitErrorMessage(null);
                    }}
                    type="button"
                  >
                    {tab.label} ({requestCountByStatus.get(tab.status) ?? 0})
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <article className="rounded-xl border border-slate-200 bg-white">
          <header className="border-b border-slate-200 p-4">
            <h3 className="text-base font-semibold">Solicitudes</h3>
            <p className="text-xs text-slate-500">Estado actual: {activeTab}</p>
          </header>
          <div className="max-h-[75vh] space-y-2 overflow-auto p-3">
            {requestsQuery.isLoading ? <p className="text-sm text-slate-500">Cargando...</p> : null}
            {filteredRequests.length === 0 ? (
              <p className="text-sm text-slate-500">No hay solicitudes en este estado.</p>
            ) : null}
            {filteredRequests.map((request) => {
              const isSelected = request.requestId === selectedRequestId;
              return (
                <button
                  className={[
                    "w-full rounded-lg border p-3 text-left",
                    isSelected
                      ? "border-brand-teal bg-teal-50"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  ].join(" ")}
                  key={request.requestId}
                  onClick={() => {
                    setSelectedRequestId(request.requestId);
                    setSubmitSuccessMessage(null);
                    setLocalSubmitErrorMessage(null);
                  }}
                  type="button"
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-semibold text-brand-ink">
                      {request.requestId}
                    </p>
                    <statusBadgeModule.StatusBadge label={request.status} tone="neutral" />
                  </div>
                  <p className="text-xs text-slate-600">Conv: {request.conversationId}</p>
                  <p className="text-xs text-slate-600">Paciente: {request.whatsappUserId}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {dateUtilsModule.formatDateTime(request.updatedAt)}
                  </p>
                </button>
              );
            })}
          </div>
        </article>

        <article className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
          {selectedRequest === undefined ? (
            <p className="text-sm text-slate-500">
              Selecciona una solicitud para ver detalle y gestionar slots.
            </p>
          ) : (
            <>
              <section className="grid gap-4 md:grid-cols-2">
                <div className="rounded-lg border border-slate-200 p-3">
                  <h4 className="text-sm font-semibold text-brand-ink">Detalle</h4>
                  <div className="mt-2 space-y-1 text-xs text-slate-700">
                    <p>
                      <strong>Request:</strong> {selectedRequest.requestId}
                    </p>
                    <p>
                      <strong>Conversación:</strong> {selectedRequest.conversationId}
                    </p>
                    <p>
                      <strong>Paciente:</strong> {selectedRequest.whatsappUserId}
                    </p>
                    <p>
                      <strong>Tipo:</strong> {selectedRequest.requestKind}
                    </p>
                    <p>
                      <strong>Ronda:</strong> {selectedRequest.roundNumber}
                    </p>
                    <p>
                      <strong>Estado:</strong> {selectedRequest.status}
                    </p>
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 p-3">
                  <h4 className="text-sm font-semibold text-brand-ink">
                    Preferencias del paciente
                  </h4>
                  <p className="mt-2 text-sm text-slate-700">
                    {selectedRequest.patientPreferenceNote ?? "-"}
                  </p>
                  {selectedRequest.rejectionSummary !== null ? (
                    <p className="mt-2 text-xs text-slate-600">
                      <strong>Resumen rechazo:</strong> {selectedRequest.rejectionSummary}
                    </p>
                  ) : null}
                  {selectedRequest.consultationReason !== null ? (
                    <p className="mt-2 text-xs text-slate-600">
                      <strong>Motivo:</strong> {selectedRequest.consultationReason}
                    </p>
                  ) : null}
                  {selectedRequest.consultationDetails !== null ? (
                    <p className="mt-2 text-xs text-slate-600">
                      <strong>Detalles:</strong> {selectedRequest.consultationDetails}
                    </p>
                  ) : null}
                  {selectedRequest.appointmentModality !== null ? (
                    <p className="mt-2 text-xs text-slate-600">
                      <strong>Modalidad:</strong> {selectedRequest.appointmentModality}
                    </p>
                  ) : null}
                  {selectedRequest.patientLocation !== null ? (
                    <p className="mt-2 text-xs text-slate-600">
                      <strong>Ubicación:</strong> {selectedRequest.patientLocation}
                    </p>
                  ) : null}
                </div>
              </section>

              {selectedRequest.status === "AWAITING_CONSULTATION_REVIEW" ? (
                <section className="rounded-lg border border-slate-200 p-3">
                  <h4 className="text-sm font-semibold text-brand-ink">
                    Resolver motivo de consulta
                  </h4>
                  <p className="mt-2 text-xs text-slate-600">
                    Puedes aprobar, pedir más información o rechazar este caso.
                  </p>
                  <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Nota para el bot
                    <textarea
                      className="mt-1 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                      onChange={(event) => {
                        if (selectedRequest === undefined) {
                          return;
                        }
                        const nextValue = event.target.value;
                        setReviewNotesByRequestId((currentValue) => ({
                          ...currentValue,
                          [selectedRequest.requestId]: nextValue
                        }));
                      }}
                      value={currentReviewNote}
                    />
                  </label>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={resolveConsultationReviewMutation.isPending}
                      onClick={() => {
                        if (selectedRequest === undefined) {
                          return;
                        }
                        setLocalSubmitErrorMessage(null);
                        setSubmitSuccessMessage(null);
                        resolveConsultationReviewMutation.mutate({
                          request: selectedRequest,
                          decision: "APPROVE",
                          professionalNote:
                            currentReviewNote.trim() === "" ? null : currentReviewNote.trim()
                        });
                      }}
                      type="button"
                    >
                      Aprobar motivo
                    </button>
                    <button
                      className="rounded-md bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={resolveConsultationReviewMutation.isPending}
                      onClick={() => {
                        if (selectedRequest === undefined) {
                          return;
                        }
                        if (currentReviewNote.trim() === "") {
                          setLocalSubmitErrorMessage(
                            "Debes agregar una nota para pedir más información."
                          );
                          return;
                        }
                        setLocalSubmitErrorMessage(null);
                        setSubmitSuccessMessage(null);
                        resolveConsultationReviewMutation.mutate({
                          request: selectedRequest,
                          decision: "REQUEST_MORE_INFO",
                          professionalNote: currentReviewNote.trim()
                        });
                      }}
                      type="button"
                    >
                      Pedir más info
                    </button>
                    <button
                      className="rounded-md bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={resolveConsultationReviewMutation.isPending}
                      onClick={() => {
                        if (selectedRequest === undefined) {
                          return;
                        }
                        setLocalSubmitErrorMessage(null);
                        setSubmitSuccessMessage(null);
                        resolveConsultationReviewMutation.mutate({
                          request: selectedRequest,
                          decision: "REJECT",
                          professionalNote:
                            currentReviewNote.trim() === "" ? null : currentReviewNote.trim()
                        });
                      }}
                      type="button"
                    >
                      Rechazar
                    </button>
                  </div>
                </section>
              ) : null}

              {selectedRequest.status === "AWAITING_PROFESSIONAL_SLOTS" ? (
                <>
                  <section className="rounded-lg border border-slate-200 p-3">
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <h4 className="text-sm font-semibold text-brand-ink">
                        Calendario ({timezone}) - {visibleMonthStart.toFormat("LLLL yyyy")}
                      </h4>
                      <div className="flex gap-2">
                        <button
                          className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-700 hover:bg-slate-100"
                          onClick={() => {
                            const previous = visibleMonthStart.minus({ months: 1 });
                            setVisibleMonth({
                              year: previous.year,
                              month: previous.month as luxonModule.MonthNumbers
                            });
                          }}
                          type="button"
                        >
                          Anterior
                        </button>
                        <button
                          className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-700 hover:bg-slate-100"
                          onClick={() => {
                            const next = visibleMonthStart.plus({ months: 1 });
                            setVisibleMonth({
                              year: next.year,
                              month: next.month as luxonModule.MonthNumbers
                            });
                          }}
                          type="button"
                        >
                          Siguiente
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-600">
                      {weekDayLabels.map((label) => (
                        <span key={label}>{label}</span>
                      ))}
                    </div>
                    <div className="mt-2 grid grid-cols-7 gap-1">
                      {dayGrid.map((dateCell, index) => {
                        if (dateCell === null) {
                          return (
                            <div className="h-10 rounded-md bg-slate-50" key={`empty-${index}`} />
                          );
                        }
                        const isoDate = dateCell.toISODate();
                        const isSelected = isoDate === selectedDayIso;
                        return (
                          <button
                            className={[
                              "h-10 rounded-md border text-sm",
                              isSelected
                                ? "border-brand-teal bg-teal-50 text-brand-teal"
                                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                            ].join(" ")}
                            key={dateCell.toISODate() ?? `day-${dateCell.day}-${index}`}
                            onClick={() => {
                              if (isoDate !== null) {
                                setSelectedDayIso(isoDate);
                              }
                            }}
                            type="button"
                          >
                            {dateCell.day}
                          </button>
                        );
                      })}
                    </div>
                    {availabilityQuery.isLoading ? (
                      <p className="mt-3 text-xs text-slate-500">
                        Cargando disponibilidad del mes...
                      </p>
                    ) : null}
                  </section>

                  <section className="rounded-lg border border-slate-200 p-3">
                    <h4 className="text-sm font-semibold text-brand-ink">
                      Slots de 60 min (06:00 a 22:00)
                    </h4>
                    <p className="mt-1 text-xs text-slate-500">
                      Día seleccionado: {selectedDayIso !== "" ? selectedDayIso : "-"}
                    </p>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                      {calendarSlots.map((slot) => {
                        const isSelected = selectedSlotIdSet.has(slot.slotId);
                        const isDisabled = slot.isBusy || slot.isPast;
                        const slotStartText = luxonModule.DateTime.fromISO(slot.startAt, {
                          zone: timezone
                        }).toFormat("HH:mm");
                        const slotEndText = luxonModule.DateTime.fromISO(slot.endAt, {
                          zone: timezone
                        }).toFormat("HH:mm");
                        return (
                          <button
                            className={[
                              "rounded-md border px-3 py-2 text-left text-sm",
                              isDisabled
                                ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                                : isSelected
                                  ? "border-brand-teal bg-teal-50 text-brand-teal"
                                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                            ].join(" ")}
                            disabled={isDisabled}
                            key={slot.slotId}
                            onClick={() => {
                              if (selectedRequest === undefined) {
                                return;
                              }
                              setSelectedSlotsByRequestId((currentValue) => {
                                const currentRequestSlots =
                                  currentValue[selectedRequest.requestId] ?? [];
                                const slotExists = currentRequestSlots.some(
                                  (currentSlot) => currentSlot.slotId === slot.slotId
                                );
                                const nextRequestSlots = slotExists
                                  ? currentRequestSlots.filter(
                                      (currentSlot) => currentSlot.slotId !== slot.slotId
                                    )
                                  : [
                                      ...currentRequestSlots,
                                      {
                                        slotId: slot.slotId,
                                        startAt: slot.startAt,
                                        endAt: slot.endAt,
                                        timezone: slot.timezone
                                      }
                                    ].sort((left, right) =>
                                      left.startAt.localeCompare(right.startAt)
                                    );
                                return {
                                  ...currentValue,
                                  [selectedRequest.requestId]: nextRequestSlots
                                };
                              });
                            }}
                            type="button"
                          >
                            <p className="font-semibold">
                              {slotStartText} - {slotEndText}
                            </p>
                            {slot.isBusy ? <p className="text-xs">No disponible</p> : null}
                            {slot.isPast ? <p className="text-xs">Horario pasado</p> : null}
                          </button>
                        );
                      })}
                    </div>
                    <p className="mt-3 text-xs text-slate-600">
                      Slots seleccionados: {selectedSlots.length}
                    </p>
                    <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Nota para paciente (opcional)
                      <textarea
                        className="mt-1 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                        onChange={(event) => {
                          if (selectedRequest === undefined) {
                            return;
                          }
                          const nextValue = event.target.value;
                          setProfessionalNotesByRequestId((currentValue) => ({
                            ...currentValue,
                            [selectedRequest.requestId]: nextValue
                          }));
                        }}
                        value={currentProfessionalNote}
                      />
                    </label>
                    <div className="mt-3 flex gap-2">
                      <button
                        className="rounded-md bg-brand-teal px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={submitSlotsMutation.isPending}
                        onClick={() => {
                          if (selectedRequest === undefined) {
                            return;
                          }
                          if (selectedSlots.length === 0) {
                            setLocalSubmitErrorMessage("Debes seleccionar al menos un slot.");
                            return;
                          }
                          setLocalSubmitErrorMessage(null);
                          setSubmitSuccessMessage(null);
                          submitSlotsMutation.mutate({
                            request: selectedRequest,
                            slots: selectedSlots,
                            professionalNote:
                              currentProfessionalNote.trim() === ""
                                ? null
                                : currentProfessionalNote.trim()
                          });
                        }}
                        type="button"
                      >
                        {submitSlotsMutation.isPending ? "Enviando..." : "Enviar slots al chatbot"}
                      </button>
                    </div>
                  </section>
                </>
              ) : selectedRequest.status === "AWAITING_CONSULTATION_REVIEW" ? null : (
                <section className="rounded-lg border border-slate-200 p-3">
                  <p className="text-sm text-slate-600">
                    Esta solicitud está en modo lectura para este estado.
                  </p>
                </section>
              )}
            </>
          )}

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
      </section>
    </appShellModule.AppShell>
  );
}

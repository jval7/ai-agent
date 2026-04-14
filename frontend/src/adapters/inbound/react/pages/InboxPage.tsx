import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";
import * as radixSwitchModule from "@radix-ui/react-switch";
import * as luxonModule from "luxon";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as slotPickerModule from "@adapters/inbound/react/components/SlotPicker";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import type * as conversationModel from "@domain/models/conversation";
import type * as schedulingModel from "@domain/models/scheduling";
import * as calendarUtilsModule from "@shared/utils/calendar";
import * as dateUtilsModule from "@shared/utils/date";

const conversationsQueryKey = ["conversations"] as const;
const blacklistQueryKey = ["blacklist"] as const;
const patientsQueryKey = ["patients"] as const;
const schedulingRequestsQueryKey = ["scheduling-requests"] as const;
const devFeaturesQueryKey = ["dev-features"] as const;

type AppointmentDisplayStatus =
  | "PENDIENTE_REVISION"
  | "ESPERANDO_INFO"
  | "ELIGIENDO_HORARIO"
  | "PAGO_PENDIENTE"
  | "AGENDADA"
  | "TOMADA"
  | "TERMINADA"
  | "RECHAZADA"
  | "CANCELADA"
  | "DERIVADA"
  | "SIN_CITA";

const appointmentDisplayConfig: Record<
  AppointmentDisplayStatus,
  { label: string; tone: statusBadgeModule.StatusBadgeTone }
> = {
  PENDIENTE_REVISION: { label: "Pendiente revisión", tone: "danger" },
  ESPERANDO_INFO: { label: "Esperando info", tone: "info" },
  ELIGIENDO_HORARIO: { label: "Eligiendo horario", tone: "info" },
  PAGO_PENDIENTE: { label: "Pago pendiente", tone: "warning" },
  AGENDADA: { label: "Agendada", tone: "success" },
  TOMADA: { label: "Tomada", tone: "neutral" },
  TERMINADA: { label: "Sesión terminada", tone: "neutral" },
  RECHAZADA: { label: "Rechazada", tone: "danger" },
  CANCELADA: { label: "Cancelada", tone: "danger" },
  DERIVADA: { label: "Derivada", tone: "info" },
  SIN_CITA: { label: "Sin cita", tone: "neutral" }
};

function resolveAppointmentDisplayStatus(
  request: schedulingModel.SchedulingRequestSummary
): AppointmentDisplayStatus {
  if (request.status === "AWAITING_CONSULTATION_REVIEW") {
    return "PENDIENTE_REVISION";
  }
  if (request.status === "AWAITING_CONSULTATION_DETAILS") {
    return "ESPERANDO_INFO";
  }
  if (request.status === "AWAITING_PATIENT_CHOICE") {
    return "ELIGIENDO_HORARIO";
  }
  if (request.status === "AWAITING_PAYMENT_CONFIRMATION") {
    return "PAGO_PENDIENTE";
  }
  if (request.status === "BOOKED") {
    const bookedSlot = request.slots.find((slot) => slot.status === "BOOKED");
    if (bookedSlot !== undefined) {
      const slotEnd = new Date(bookedSlot.endAt);
      if (slotEnd < new Date()) {
        return "TOMADA";
      }
    }
    return "AGENDADA";
  }
  if (request.status === "SESSION_CLOSED") {
    return "TERMINADA";
  }
  if (request.status === "CONSULTATION_REJECTED") {
    return "RECHAZADA";
  }
  if (request.status === "CANCELLED") {
    return "CANCELADA";
  }
  if (request.status === "HUMAN_HANDOFF") {
    return "DERIVADA";
  }
  return "SIN_CITA";
}

export function InboxPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const conversationsQuery = reactQueryModule.useQuery({
    queryKey: conversationsQueryKey,
    queryFn: () => appContainer.conversationUseCase.listConversations(),
    refetchInterval: 5_000
  });

  const blacklistQuery = reactQueryModule.useQuery({
    queryKey: blacklistQueryKey,
    queryFn: () => appContainer.blacklistUseCase.list()
  });

  const patientsQuery = reactQueryModule.useQuery({
    queryKey: patientsQueryKey,
    queryFn: () => appContainer.patientUseCase.listPatients()
  });

  const schedulingRequestsQuery = reactQueryModule.useQuery({
    queryKey: schedulingRequestsQueryKey,
    queryFn: () => appContainer.schedulingUseCase.listRequests(),
    refetchInterval: 5_000
  });

  const googleCalendarConnectionQuery = reactQueryModule.useQuery({
    queryKey: ["google-calendar-connection"],
    queryFn: () => appContainer.onboardingUseCase.getGoogleCalendarConnectionStatus()
  });

  const professionalTimezone =
    googleCalendarConnectionQuery.data?.professionalTimezone ?? "America/Bogota";

  const [slotPickerMonth, setSlotPickerMonth] = reactModule.useState<{
    year: number;
    month: number;
  }>(() => {
    const now = luxonModule.DateTime.now();
    return { year: now.year, month: now.month };
  });

  const latestRequestByConversationId = reactModule.useMemo(() => {
    const map = new Map<string, schedulingModel.SchedulingRequestSummary>();
    if (schedulingRequestsQuery.data === undefined) {
      return map;
    }
    for (const request of schedulingRequestsQuery.data) {
      const existing = map.get(request.conversationId);
      if (existing === undefined || request.updatedAt > existing.updatedAt) {
        map.set(request.conversationId, request);
      }
    }
    return map;
  }, [schedulingRequestsQuery.data]);

  const patientNameByWhatsappId = reactModule.useMemo(() => {
    const map = new Map<string, string>();
    if (patientsQuery.data === undefined) {
      return map;
    }
    for (const patient of patientsQuery.data) {
      const fullName = `${patient.firstName} ${patient.lastName}`.trim();
      if (fullName !== "") {
        map.set(patient.whatsappUserId, fullName);
      }
    }
    return map;
  }, [patientsQuery.data]);

  const [selectedConversationId, setSelectedConversationId] = reactModule.useState<string | null>(
    null
  );
  const [inboxMobileStep, setInboxMobileStep] = reactModule.useState<"LIST" | "DETAIL">("LIST");
  const [fabOpen, setFabOpen] = reactModule.useState(false);

  reactModule.useEffect(() => {
    if (conversationsQuery.data === undefined || conversationsQuery.data.length === 0) {
      setSelectedConversationId(null);
      return;
    }

    const hasSelectedConversation = conversationsQuery.data.some(
      (conversation) => conversation.conversationId === selectedConversationId
    );

    if (!hasSelectedConversation) {
      const firstConversation = conversationsQuery.data[0];
      if (firstConversation !== undefined) {
        setSelectedConversationId(firstConversation.conversationId);
      }
    }
  }, [conversationsQuery.data, selectedConversationId]);

  const selectedConversation = conversationsQuery.data?.find(
    (conversation) => conversation.conversationId === selectedConversationId
  );

  const messagesQuery = reactQueryModule.useQuery({
    queryKey: ["conversation-messages", selectedConversationId],
    enabled: selectedConversationId !== null,
    queryFn: () => appContainer.conversationUseCase.listMessages(selectedConversationId ?? ""),
    refetchInterval: 3_000
  });

  const controlModeMutation = reactQueryModule.useMutation({
    mutationFn: (controlMode: conversationModel.ControlMode) => {
      if (selectedConversationId === null) {
        throw new Error("No conversation selected");
      }
      return appContainer.conversationUseCase.updateControlMode(
        selectedConversationId,
        controlMode
      );
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: conversationsQueryKey });
    }
  });

  const addBlacklistMutation = reactQueryModule.useMutation({
    mutationFn: (whatsappUserId: string) => appContainer.blacklistUseCase.add(whatsappUserId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: blacklistQueryKey });
    }
  });

  const removeBlacklistMutation = reactQueryModule.useMutation({
    mutationFn: (whatsappUserId: string) => appContainer.blacklistUseCase.remove(whatsappUserId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: blacklistQueryKey });
    }
  });

  const resetMessagesMutation = reactQueryModule.useMutation({
    mutationFn: (conversationId: string) =>
      appContainer.conversationUseCase.resetMessages(conversationId),
    onSuccess: async (_data, conversationId) => {
      if (selectedConversationId === conversationId) {
        setSelectedConversationId(null);
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: conversationsQueryKey }),
        queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey }),
        queryClient.invalidateQueries({ queryKey: patientsQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["conversation-messages", conversationId] })
      ]);
    }
  });

  const [messageText, setMessageText] = reactModule.useState("");
  const [selectedSlots, setSelectedSlots] = reactModule.useState<
    schedulingModel.ProfessionalSlotInput[]
  >([]);
  const [slotPickerOpen, setSlotPickerOpen] = reactModule.useState(false);
  const [paymentAmountInput, setPaymentAmountInput] = reactModule.useState("");
  const [reviewNoteInput, setReviewNoteInput] = reactModule.useState("");
  const sendMessageMutation = reactQueryModule.useMutation({
    mutationFn: (payload: { conversationId: string; messageText: string }) =>
      appContainer.conversationUseCase.sendMessage(payload.conversationId, payload.messageText),
    onSuccess: async () => {
      setMessageText("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: conversationsQueryKey }),
        queryClient.invalidateQueries({
          queryKey: ["conversation-messages", selectedConversationId]
        })
      ]);
    }
  });

  const submitSlotsMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      slots: schedulingModel.ProfessionalSlotInput[];
      professionalNote: string | null;
    }) =>
      appContainer.schedulingUseCase.submitProfessionalSlots(
        payload.request.conversationId,
        payload.request.requestId,
        { slots: payload.slots, professionalNote: payload.professionalNote }
      ),
    onSuccess: async () => {
      setSelectedSlots([]);
      setReviewNoteInput("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey }),
        queryClient.invalidateQueries({
          queryKey: ["conversation-messages", selectedConversationId]
        })
      ]);
    }
  });

  const resolvePaymentMutation = reactQueryModule.useMutation({
    mutationFn: (payload: {
      request: schedulingModel.SchedulingRequestSummary;
      decision: "APPROVE" | "SEND_REMINDER";
      paymentAmountCop: number | null;
      professionalNote: string | null;
    }) =>
      appContainer.schedulingUseCase.resolvePaymentReview(
        payload.request.conversationId,
        payload.request.requestId,
        {
          decision: payload.decision,
          professionalNote: payload.professionalNote,
          paymentAmountCop: payload.paymentAmountCop
        }
      ),
    onSuccess: async () => {
      setPaymentAmountInput("");
      setReviewNoteInput("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey }),
        queryClient.invalidateQueries({
          queryKey: ["conversation-messages", selectedConversationId]
        })
      ]);
    }
  });

  const closeSessionMutation = reactQueryModule.useMutation({
    mutationFn: (conversationId: string) =>
      appContainer.schedulingUseCase.closeSession(conversationId),
    onSuccess: async (_data, conversationId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: conversationsQueryKey }),
        queryClient.invalidateQueries({ queryKey: schedulingRequestsQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["conversation-messages", conversationId] })
      ]);
    }
  });

  const devFeaturesQuery = reactQueryModule.useQuery({
    queryKey: devFeaturesQueryKey,
    queryFn: () => appContainer.agentUseCase.getDevFeatures(),
    staleTime: Infinity
  });

  const devFeaturesEnabled = devFeaturesQuery.data?.enabled ?? false;
  const sandboxEnabled = devFeaturesQuery.data?.sandbox_enabled ?? false;

  const sandboxMutation = reactQueryModule.useMutation({
    mutationFn: (enabled: boolean) => appContainer.agentUseCase.updateSandboxMode(enabled),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: devFeaturesQueryKey });
    }
  });

  const selectedWhatsappUserId = selectedConversation?.whatsappUserId ?? null;
  const isBlocked =
    selectedWhatsappUserId !== null
      ? (blacklistQuery.data?.some((entry) => entry.whatsappUserId === selectedWhatsappUserId) ??
        false)
      : false;

  const selectedConversationRequest =
    selectedConversationId !== null
      ? (latestRequestByConversationId.get(selectedConversationId) ?? null)
      : null;
  const selectedAppointmentStatus: AppointmentDisplayStatus =
    selectedConversationRequest !== null
      ? resolveAppointmentDisplayStatus(selectedConversationRequest)
      : "SIN_CITA";
  // eslint-disable-next-line security/detect-object-injection
  const selectedAppointmentConfig = appointmentDisplayConfig[selectedAppointmentStatus];

  const needsOwnerAction =
    selectedConversationRequest !== null &&
    (selectedConversationRequest.status === "AWAITING_CONSULTATION_REVIEW" ||
      selectedConversationRequest.status === "AWAITING_PAYMENT_CONFIRMATION");

  const slotPickerMonthStart = luxonModule.DateTime.fromObject(
    { year: slotPickerMonth.year, month: slotPickerMonth.month, day: 1 },
    { zone: professionalTimezone }
  );
  const slotPickerMonthEnd = slotPickerMonthStart.plus({ months: 1 });
  const slotPickerMonthFromIso = slotPickerMonthStart.toISO();
  const slotPickerMonthToIso = slotPickerMonthEnd.toISO();

  const availabilityQuery = reactQueryModule.useQuery({
    queryKey: [
      "google-calendar-availability",
      slotPickerMonthFromIso,
      slotPickerMonthToIso,
      professionalTimezone
    ],
    enabled:
      needsOwnerAction &&
      selectedConversationRequest?.status === "AWAITING_CONSULTATION_REVIEW" &&
      slotPickerMonthFromIso !== null &&
      slotPickerMonthToIso !== null,
    queryFn: () =>
      appContainer.schedulingUseCase.getAvailability(slotPickerMonthFromIso!, slotPickerMonthToIso!)
  });

  const busyIntervals = reactModule.useMemo<calendarUtilsModule.BusyIntervalRange[]>(() => {
    if (availabilityQuery.data === undefined) {
      return [];
    }
    return calendarUtilsModule.parseBusyIntervals(
      availabilityQuery.data.busyIntervals,
      professionalTimezone
    );
  }, [availabilityQuery.data, professionalTimezone]);

  const renderConversationItem = (
    conversation: conversationModel.ConversationSummary,
    options: { onClick: () => void }
  ) => {
    const patientName = patientNameByWhatsappId.get(conversation.whatsappUserId);
    const displayName = conversation.contactName ?? patientName ?? conversation.whatsappUserId;
    const request = latestRequestByConversationId.get(conversation.conversationId);
    const displayStatus: AppointmentDisplayStatus =
      request !== undefined ? resolveAppointmentDisplayStatus(request) : "SIN_CITA";
    // eslint-disable-next-line security/detect-object-injection
    const config = appointmentDisplayConfig[displayStatus];
    return (
      <button
        className="w-full rounded-lg border border-slate-200 bg-white p-3 text-left transition-colors hover:border-slate-300"
        key={conversation.conversationId}
        onClick={options.onClick}
        type="button"
      >
        <div className="mb-1 flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-brand-ink">{displayName}</p>
            {conversation.contactName !== null ? (
              <p className="truncate text-[11px] text-slate-400">{conversation.whatsappUserId}</p>
            ) : null}
          </div>
          <statusBadgeModule.StatusBadge
            label={conversation.controlMode}
            tone={conversation.controlMode === "AI" ? "success" : "warning"}
          />
        </div>
        <p className="truncate text-xs text-slate-500">
          {conversation.lastMessagePreview ?? "Sin preview"}
        </p>
        <div className="mt-1.5">
          <statusBadgeModule.StatusBadge label={config.label} tone={config.tone} />
        </div>
      </button>
    );
  };

  return (
    <appShellModule.AppShell>
      {/* ===== MOBILE: WhatsApp-style flow ===== */}
      <div className="lg:hidden">
        {inboxMobileStep === "LIST" ? (
          <div className="space-y-2">
            {devFeaturesEnabled ? (
              <div
                className={[
                  "mb-2 flex items-center justify-between rounded-lg border px-3 py-2",
                  sandboxEnabled ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-slate-50"
                ].join(" ")}
              >
                <div className="min-w-0 flex-1">
                  <p
                    className={[
                      "text-xs font-semibold",
                      sandboxEnabled ? "text-amber-800" : "text-slate-500"
                    ].join(" ")}
                  >
                    Sandbox
                  </p>
                  {sandboxEnabled ? (
                    <p className="text-[11px] text-amber-700">WhatsApp no envía mensajes reales</p>
                  ) : null}
                </div>
                <radixSwitchModule.Root
                  checked={sandboxEnabled}
                  className="relative h-6 w-11 rounded-full bg-slate-300 data-[state=checked]:bg-amber-500"
                  disabled={sandboxMutation.isPending}
                  onCheckedChange={(checked) => {
                    sandboxMutation.mutate(checked);
                  }}
                >
                  <radixSwitchModule.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-white transition-transform data-[state=checked]:translate-x-5" />
                </radixSwitchModule.Root>
              </div>
            ) : null}
            <header className="mb-3">
              <h2 className="text-base font-semibold text-brand-ink">Conversaciones</h2>
              <p className="text-[11px] text-slate-500">
                {conversationsQuery.data?.length ?? 0} conversaciones
              </p>
            </header>
            {conversationsQuery.isLoading ? (
              <p className="text-sm text-slate-500">Cargando...</p>
            ) : null}
            {conversationsQuery.data?.length === 0 ? (
              <p className="text-sm text-slate-500">No hay conversaciones aún.</p>
            ) : null}
            {conversationsQuery.data?.map((conversation) =>
              renderConversationItem(conversation, {
                onClick: () => {
                  setSelectedConversationId(conversation.conversationId);
                  setInboxMobileStep("DETAIL");
                  setFabOpen(false);
                }
              })
            )}
          </div>
        ) : null}

        {inboxMobileStep === "DETAIL" && selectedConversation !== undefined ? (
          <div className="relative flex h-[calc(100vh-7rem)] flex-col">
            {/* Header */}
            <header className="border-b border-border-subtle pb-3">
              <div className="flex items-center gap-2">
                <button
                  className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
                  onClick={() => {
                    setInboxMobileStep("LIST");
                    setFabOpen(false);
                  }}
                  type="button"
                >
                  <svg
                    className="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M15.75 19.5L8.25 12l7.5-7.5"
                    />
                  </svg>
                </button>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-brand-ink">
                    {selectedConversation.contactName ??
                      patientNameByWhatsappId.get(selectedConversation.whatsappUserId) ??
                      selectedConversation.whatsappUserId}
                  </p>
                </div>
                <statusBadgeModule.StatusBadge
                  label={selectedAppointmentConfig.label}
                  tone={selectedAppointmentConfig.tone}
                />
              </div>
              {selectedConversation.controlMode === "HUMAN" || isBlocked ? (
                <div className="mt-2 flex flex-wrap gap-1.5 pl-8">
                  {selectedConversation.controlMode === "HUMAN" ? (
                    <statusBadgeModule.StatusBadge label="HUMAN" tone="warning" />
                  ) : null}
                  {isBlocked ? (
                    <statusBadgeModule.StatusBadge label="Bloqueado" tone="danger" />
                  ) : null}
                </div>
              ) : null}
            </header>

            {/* Messages */}
            <div className="flex-1 space-y-3 overflow-auto py-3">
              {messagesQuery.isLoading ? (
                <p className="text-sm text-slate-500">Cargando historial...</p>
              ) : null}

              {messagesQuery.data?.map((message) => {
                const isInbound = message.direction === "INBOUND";
                return (
                  <div
                    className={[
                      "max-w-[85%] rounded-xl px-3 py-2 text-sm",
                      isInbound
                        ? "mr-auto bg-slate-100 text-slate-800"
                        : "ml-auto bg-brand-teal text-white"
                    ].join(" ")}
                    key={message.messageId}
                  >
                    <p className="mb-1 text-xs font-semibold opacity-80">{message.role}</p>
                    <p>{message.content}</p>
                    <p className="mt-1 text-[11px] opacity-80">
                      {dateUtilsModule.formatDateTime(message.createdAt)}
                    </p>
                  </div>
                );
              })}

              {messagesQuery.data?.length === 0 ? (
                <p className="text-sm text-slate-500">No hay mensajes en esta conversación.</p>
              ) : null}
            </div>

            {/* Owner action bar */}
            {needsOwnerAction && selectedConversationRequest !== null ? (
              <div className="shrink-0 border-t border-amber-200 bg-amber-50 px-3 py-2">
                {selectedConversationRequest.status === "AWAITING_CONSULTATION_REVIEW" ? (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-amber-800">Proponer horarios</p>
                    <button
                      className="w-full rounded-md bg-brand-teal px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-teal/90"
                      onClick={() => setSlotPickerOpen(true)}
                      type="button"
                    >
                      Seleccionar horarios
                    </button>
                  </div>
                ) : null}
                {selectedConversationRequest.status === "AWAITING_PAYMENT_CONFIRMATION" ? (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-amber-800">Confirmar pago</p>
                    <div className="flex gap-2">
                      <input
                        className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs focus:border-brand-teal focus:outline-none"
                        onChange={(e) => setPaymentAmountInput(e.target.value)}
                        placeholder="Monto COP (opcional)"
                        type="number"
                        value={paymentAmountInput}
                      />
                      <button
                        className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                        disabled={resolvePaymentMutation.isPending}
                        onClick={() =>
                          resolvePaymentMutation.mutate({
                            request: selectedConversationRequest,
                            decision: "APPROVE",
                            paymentAmountCop:
                              paymentAmountInput !== "" ? parseInt(paymentAmountInput, 10) : null,
                            professionalNote: null
                          })
                        }
                        type="button"
                      >
                        {resolvePaymentMutation.isPending ? "Confirmando..." : "Confirmar"}
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}

            {/* Send message input (HUMAN mode only) */}
            {selectedConversation.controlMode === "HUMAN" ? (
              <form
                className="flex gap-2 border-t border-slate-200 bg-white px-2 py-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  const trimmed = messageText.trim();
                  if (trimmed === "" || selectedConversationId === null) {
                    return;
                  }
                  sendMessageMutation.mutate({
                    conversationId: selectedConversationId,
                    messageText: trimmed
                  });
                }}
              >
                <input
                  className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-teal focus:outline-none"
                  disabled={sendMessageMutation.isPending}
                  onChange={(event) => setMessageText(event.target.value)}
                  placeholder="Escribe un mensaje..."
                  type="text"
                  value={messageText}
                />
                <button
                  className="rounded-lg bg-brand-teal px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-teal/90 disabled:opacity-60"
                  disabled={sendMessageMutation.isPending || messageText.trim() === ""}
                  type="submit"
                >
                  {sendMessageMutation.isPending ? "Enviando..." : "Enviar"}
                </button>
              </form>
            ) : null}

            {/* FAB + action menu */}
            <div
              className={[
                "pointer-events-none absolute right-2 flex flex-col items-end gap-2",
                needsOwnerAction ? "bottom-20" : "bottom-4"
              ].join(" ")}
            >
              {fabOpen ? (
                <div className="pointer-events-auto flex flex-col gap-2">
                  {devFeaturesEnabled ? (
                    <button
                      className="rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-lg ring-1 ring-slate-200 transition-colors hover:bg-slate-50"
                      onClick={() => {
                        if (selectedConversationId === null) {
                          return;
                        }
                        const isConfirmed = window.confirm(
                          "¿Seguro que quieres resetear este chat? Se eliminará la conversación, el paciente y todos sus datos asociados."
                        );
                        if (!isConfirmed) {
                          return;
                        }
                        resetMessagesMutation.mutate(selectedConversationId);
                        setFabOpen(false);
                      }}
                      type="button"
                    >
                      Resetear
                    </button>
                  ) : null}
                  <button
                    className="rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-lg ring-1 ring-slate-200 transition-colors hover:bg-slate-50"
                    onClick={() => {
                      const nextMode = selectedConversation.controlMode === "AI" ? "HUMAN" : "AI";
                      controlModeMutation.mutate(nextMode);
                      setFabOpen(false);
                    }}
                    type="button"
                  >
                    {selectedConversation.controlMode === "AI" ? "Cambiar a HUMAN" : "Cambiar a AI"}
                  </button>
                  <button
                    className={[
                      "rounded-lg px-4 py-2.5 text-sm font-semibold shadow-lg ring-1 transition-colors",
                      isBlocked
                        ? "bg-red-50 text-red-700 ring-red-200 hover:bg-red-100"
                        : "bg-white text-slate-700 ring-slate-200 hover:bg-slate-50"
                    ].join(" ")}
                    onClick={() => {
                      if (selectedWhatsappUserId === null) {
                        return;
                      }
                      if (isBlocked) {
                        removeBlacklistMutation.mutate(selectedWhatsappUserId);
                      } else {
                        addBlacklistMutation.mutate(selectedWhatsappUserId);
                      }
                      setFabOpen(false);
                    }}
                    type="button"
                  >
                    {isBlocked ? "Quitar blacklist" : "Blacklist"}
                  </button>
                  <button
                    className="rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-lg ring-1 ring-slate-200 transition-colors hover:bg-slate-50"
                    disabled={closeSessionMutation.isPending}
                    onClick={() => {
                      if (selectedConversationId === null) {
                        return;
                      }
                      const isConfirmed = window.confirm(
                        "¿Seguro que quieres cerrar la sesión de esta conversación?"
                      );
                      if (!isConfirmed) {
                        return;
                      }
                      closeSessionMutation.mutate(selectedConversationId);
                      setFabOpen(false);
                    }}
                    type="button"
                  >
                    {closeSessionMutation.isPending ? "Cerrando..." : "Cerrar sesión"}
                  </button>
                </div>
              ) : null}
              <button
                className="pointer-events-auto flex h-12 w-12 items-center justify-center rounded-full bg-brand-teal text-white shadow-lg transition-transform hover:scale-105"
                onClick={() => setFabOpen((current) => !current)}
                type="button"
              >
                {fabOpen ? (
                  <svg
                    className="h-6 w-6"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  <svg
                    className="h-6 w-6"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 6.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 12.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 18.75a.75.75 0 110-1.5.75.75 0 010 1.5z"
                    />
                  </svg>
                )}
              </button>
            </div>

            {slotPickerOpen &&
            selectedConversationRequest !== null &&
            selectedConversationRequest.status === "AWAITING_CONSULTATION_REVIEW" ? (
              <div className="fixed inset-0 z-50 flex flex-col bg-white">
                <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                  <h2 className="text-sm font-semibold text-slate-800">Proponer horarios</h2>
                  <button
                    className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
                    onClick={() => setSlotPickerOpen(false)}
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
                </header>
                <div className="flex-1 overflow-auto px-4 py-3">
                  <div className="mb-3 space-y-1 text-xs text-slate-600">
                    {selectedConversationRequest.consultationReason ? (
                      <p>
                        <span className="font-semibold">Motivo:</span>{" "}
                        {selectedConversationRequest.consultationReason}
                      </p>
                    ) : null}
                    {selectedConversationRequest.patientLocation ? (
                      <p>
                        <span className="font-semibold">Ubicación:</span>{" "}
                        {selectedConversationRequest.patientLocation}
                      </p>
                    ) : null}
                    {selectedConversationRequest.appointmentModality ? (
                      <p>
                        <span className="font-semibold">Modalidad:</span>{" "}
                        {selectedConversationRequest.appointmentModality}
                      </p>
                    ) : null}
                  </div>
                  <slotPickerModule.SlotPicker
                    busyIntervals={busyIntervals}
                    isLoadingAvailability={availabilityQuery.isLoading}
                    onMonthChange={setSlotPickerMonth}
                    onSelectedSlotsChange={setSelectedSlots}
                    requestId={selectedConversationRequest.requestId}
                    selectedSlots={selectedSlots}
                    timezone={professionalTimezone}
                  />
                  <textarea
                    className="mt-3 w-full rounded border border-slate-300 px-2 py-1 text-xs focus:border-brand-teal focus:outline-none"
                    onChange={(e) => setReviewNoteInput(e.target.value)}
                    placeholder="Nota profesional (opcional)"
                    rows={2}
                    value={reviewNoteInput}
                  />
                </div>
                <div className="border-t border-slate-200 px-4 py-3">
                  <button
                    className="w-full rounded-md bg-brand-teal px-3 py-2.5 text-sm font-semibold text-white hover:bg-brand-teal/90 disabled:opacity-60"
                    disabled={submitSlotsMutation.isPending || selectedSlots.length === 0}
                    onClick={() => {
                      submitSlotsMutation.mutate({
                        request: selectedConversationRequest,
                        slots: selectedSlots,
                        professionalNote: reviewNoteInput.trim() || null
                      });
                      setSlotPickerOpen(false);
                    }}
                    type="button"
                  >
                    {submitSlotsMutation.isPending
                      ? "Enviando..."
                      : `Enviar ${selectedSlots.length} horario${selectedSlots.length !== 1 ? "s" : ""}`}
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* ===== DESKTOP: 3-column layout (unchanged) ===== */}
      <section className="hidden gap-4 lg:grid lg:grid-cols-[280px_minmax(0,1fr)_320px]">
        <article className="rounded-xl border border-border-subtle bg-white shadow-card">
          {devFeaturesEnabled ? (
            <div
              className={[
                "flex items-center justify-between border-b px-4 py-2",
                sandboxEnabled ? "border-amber-200 bg-amber-50" : "border-slate-100 bg-slate-50"
              ].join(" ")}
            >
              <div className="min-w-0 flex-1">
                <p
                  className={[
                    "text-xs font-semibold",
                    sandboxEnabled ? "text-amber-800" : "text-slate-500"
                  ].join(" ")}
                >
                  Sandbox
                </p>
                {sandboxEnabled ? (
                  <p className="text-[11px] text-amber-700">WhatsApp no envía mensajes reales</p>
                ) : null}
              </div>
              <radixSwitchModule.Root
                checked={sandboxEnabled}
                className="relative h-6 w-11 rounded-full bg-slate-300 data-[state=checked]:bg-amber-500"
                disabled={sandboxMutation.isPending}
                onCheckedChange={(checked) => {
                  sandboxMutation.mutate(checked);
                }}
              >
                <radixSwitchModule.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-white transition-transform data-[state=checked]:translate-x-5" />
              </radixSwitchModule.Root>
            </div>
          ) : null}
          <header className="border-b border-border-subtle px-5 py-4">
            <h2 className="text-base font-semibold">Conversaciones</h2>
            <p className="text-xs text-slate-500">Selecciona una conversación para ver detalle.</p>
          </header>
          <div className="max-h-[calc(100vh-10rem)] overflow-auto p-2">
            {conversationsQuery.isLoading ? (
              <p className="p-3 text-sm text-slate-500">Cargando...</p>
            ) : null}
            {conversationsQuery.data?.length === 0 ? (
              <p className="p-3 text-sm text-slate-500">No hay conversaciones aún.</p>
            ) : null}
            {conversationsQuery.data?.map((conversation) => {
              const isSelected = conversation.conversationId === selectedConversationId;
              const isResettingConversation =
                resetMessagesMutation.isPending &&
                resetMessagesMutation.variables === conversation.conversationId;
              const patientName = patientNameByWhatsappId.get(conversation.whatsappUserId);
              const desktopDisplayName =
                conversation.contactName ?? patientName ?? conversation.whatsappUserId;
              const request = latestRequestByConversationId.get(conversation.conversationId);
              const displayStatus: AppointmentDisplayStatus =
                request !== undefined ? resolveAppointmentDisplayStatus(request) : "SIN_CITA";
              // eslint-disable-next-line security/detect-object-injection
              const config = appointmentDisplayConfig[displayStatus];
              return (
                <article
                  className={[
                    "mb-2 rounded-lg border p-3",
                    isSelected
                      ? "border-brand-teal bg-brand-accent-light"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  ].join(" ")}
                  key={conversation.conversationId}
                >
                  <button
                    className="w-full text-left"
                    onClick={() => {
                      setSelectedConversationId(conversation.conversationId);
                    }}
                    type="button"
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-brand-ink">
                          {desktopDisplayName}
                        </p>
                        {conversation.contactName !== null ? (
                          <p className="truncate text-[11px] text-slate-400">
                            {conversation.whatsappUserId}
                          </p>
                        ) : null}
                      </div>
                      <statusBadgeModule.StatusBadge
                        label={conversation.controlMode}
                        tone={conversation.controlMode === "AI" ? "success" : "warning"}
                      />
                    </div>
                    <p className="truncate text-xs text-slate-500">
                      {conversation.lastMessagePreview ?? "Sin preview"}
                    </p>
                    <div className="mt-1.5">
                      <statusBadgeModule.StatusBadge label={config.label} tone={config.tone} />
                    </div>
                  </button>

                  {devFeaturesEnabled ? (
                    <button
                      className="mt-3 w-full rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={resetMessagesMutation.isPending}
                      onClick={() => {
                        const isConfirmed = window.confirm(
                          "¿Seguro que quieres resetear este chat? Se eliminará la conversación, el paciente y todos sus datos asociados."
                        );
                        if (!isConfirmed) {
                          return;
                        }
                        resetMessagesMutation.mutate(conversation.conversationId);
                      }}
                      type="button"
                    >
                      {isResettingConversation ? "Reseteando..." : "Resetear chat"}
                    </button>
                  ) : null}
                </article>
              );
            })}
          </div>
        </article>

        <article className="rounded-xl border border-border-subtle bg-white shadow-card">
          <header className="border-b border-border-subtle px-5 py-4">
            <h2 className="text-base font-semibold">Mensajes</h2>
            {selectedConversation !== undefined ? (
              <p className="text-xs text-slate-500">
                {selectedConversation.contactName ??
                  patientNameByWhatsappId.get(selectedConversation.whatsappUserId) ??
                  selectedConversation.whatsappUserId}
              </p>
            ) : (
              <p className="text-xs text-slate-500">Selecciona una conversación.</p>
            )}
          </header>
          <div className="max-h-[calc(100vh-10rem)] space-y-3 overflow-auto p-4">
            {messagesQuery.isLoading && selectedConversationId !== null ? (
              <p className="text-sm text-slate-500">Cargando historial...</p>
            ) : null}

            {messagesQuery.data?.map((message) => {
              const isInbound = message.direction === "INBOUND";
              return (
                <div
                  className={[
                    "max-w-[90%] rounded-xl px-3 py-2 text-sm",
                    isInbound
                      ? "mr-auto bg-slate-100 text-slate-800"
                      : "ml-auto bg-brand-teal text-white"
                  ].join(" ")}
                  key={message.messageId}
                >
                  <p className="mb-1 text-xs font-semibold opacity-80">{message.role}</p>
                  <p>{message.content}</p>
                  <p className="mt-1 text-[11px] opacity-80">
                    {dateUtilsModule.formatDateTime(message.createdAt)}
                  </p>
                </div>
              );
            })}

            {messagesQuery.data?.length === 0 ? (
              <p className="text-sm text-slate-500">No hay mensajes en esta conversación.</p>
            ) : null}
          </div>

          {/* Send message input (HUMAN mode only) */}
          {selectedConversation?.controlMode === "HUMAN" ? (
            <form
              className="flex gap-2 border-t border-border-subtle px-4 py-3"
              onSubmit={(event) => {
                event.preventDefault();
                const trimmed = messageText.trim();
                if (trimmed === "" || selectedConversationId === null) {
                  return;
                }
                sendMessageMutation.mutate({
                  conversationId: selectedConversationId,
                  messageText: trimmed
                });
              }}
            >
              <input
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-teal focus:outline-none"
                disabled={sendMessageMutation.isPending}
                onChange={(event) => setMessageText(event.target.value)}
                placeholder="Escribe un mensaje..."
                type="text"
                value={messageText}
              />
              <button
                className="rounded-lg bg-brand-teal px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-teal/90 disabled:opacity-60"
                disabled={sendMessageMutation.isPending || messageText.trim() === ""}
                type="submit"
              >
                {sendMessageMutation.isPending ? "Enviando..." : "Enviar"}
              </button>
            </form>
          ) : null}
        </article>

        <article className="space-y-4 rounded-xl border border-border-subtle bg-white shadow-card p-4">
          <h2 className="text-base font-semibold">Control</h2>

          {selectedConversation === undefined ? (
            <p className="text-sm text-slate-500">
              Selecciona una conversación para gestionar control y blacklist.
            </p>
          ) : (
            <>
              {needsOwnerAction && selectedConversationRequest !== null ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-amber-700">
                    Acción requerida
                  </p>
                  {selectedConversationRequest.status === "AWAITING_CONSULTATION_REVIEW" ? (
                    <div className="mt-2 space-y-3">
                      <div className="space-y-1 text-xs text-slate-600">
                        {selectedConversationRequest.consultationReason ? (
                          <p>
                            <span className="font-semibold">Motivo:</span>{" "}
                            {selectedConversationRequest.consultationReason}
                          </p>
                        ) : null}
                        {selectedConversationRequest.patientLocation ? (
                          <p>
                            <span className="font-semibold">Ubicación:</span>{" "}
                            {selectedConversationRequest.patientLocation}
                          </p>
                        ) : null}
                        {selectedConversationRequest.appointmentModality ? (
                          <p>
                            <span className="font-semibold">Modalidad:</span>{" "}
                            {selectedConversationRequest.appointmentModality}
                          </p>
                        ) : null}
                      </div>
                      <slotPickerModule.SlotPicker
                        busyIntervals={busyIntervals}
                        isLoadingAvailability={availabilityQuery.isLoading}
                        onMonthChange={setSlotPickerMonth}
                        onSelectedSlotsChange={setSelectedSlots}
                        requestId={selectedConversationRequest.requestId}
                        selectedSlots={selectedSlots}
                        timezone={professionalTimezone}
                      />
                      <textarea
                        className="w-full rounded border border-slate-300 px-2 py-1 text-xs focus:border-brand-teal focus:outline-none"
                        onChange={(e) => setReviewNoteInput(e.target.value)}
                        placeholder="Nota profesional (opcional)"
                        rows={2}
                        value={reviewNoteInput}
                      />
                      <button
                        className="w-full rounded-md bg-brand-teal px-3 py-2 text-sm font-semibold text-white hover:bg-brand-teal/90 disabled:opacity-60"
                        disabled={submitSlotsMutation.isPending || selectedSlots.length === 0}
                        onClick={() => {
                          submitSlotsMutation.mutate({
                            request: selectedConversationRequest,
                            slots: selectedSlots,
                            professionalNote: reviewNoteInput.trim() || null
                          });
                        }}
                        type="button"
                      >
                        {submitSlotsMutation.isPending
                          ? "Enviando..."
                          : `Enviar ${selectedSlots.length} horario${selectedSlots.length !== 1 ? "s" : ""}`}
                      </button>
                    </div>
                  ) : null}
                  {selectedConversationRequest.status === "AWAITING_PAYMENT_CONFIRMATION" ? (
                    <div className="mt-2 space-y-2">
                      <p className="text-xs text-amber-800">Confirmar pago del paciente</p>
                      <input
                        className="w-full rounded border border-slate-300 px-2 py-1 text-xs focus:border-brand-teal focus:outline-none"
                        onChange={(e) => setPaymentAmountInput(e.target.value)}
                        placeholder="Monto COP (opcional)"
                        type="number"
                        value={paymentAmountInput}
                      />
                      <textarea
                        className="w-full rounded border border-slate-300 px-2 py-1 text-xs focus:border-brand-teal focus:outline-none"
                        onChange={(e) => setReviewNoteInput(e.target.value)}
                        placeholder="Nota (opcional)"
                        rows={2}
                        value={reviewNoteInput}
                      />
                      <button
                        className="w-full rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                        disabled={resolvePaymentMutation.isPending}
                        onClick={() =>
                          resolvePaymentMutation.mutate({
                            request: selectedConversationRequest,
                            decision: "APPROVE",
                            paymentAmountCop:
                              paymentAmountInput !== "" ? parseInt(paymentAmountInput, 10) : null,
                            professionalNote: reviewNoteInput.trim() || null
                          })
                        }
                        type="button"
                      >
                        {resolvePaymentMutation.isPending ? "Confirmando..." : "Confirmar pago"}
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}

              <div className="rounded-lg border border-border-subtle p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Modo de control
                </p>
                <div className="mt-2 flex items-center justify-between">
                  <p className="text-sm text-slate-700">AI ↔ HUMAN</p>
                  <radixSwitchModule.Root
                    checked={selectedConversation.controlMode === "HUMAN"}
                    className="relative h-6 w-11 rounded-full bg-slate-300 data-[state=checked]:bg-brand-teal"
                    onCheckedChange={(checked) => {
                      controlModeMutation.mutate(checked ? "HUMAN" : "AI");
                    }}
                  >
                    <radixSwitchModule.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-white transition-transform data-[state=checked]:translate-x-5" />
                  </radixSwitchModule.Root>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Actual: {selectedConversation.controlMode}
                </p>
              </div>

              <div className="rounded-lg border border-border-subtle p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Blacklist
                </p>
                <p className="mt-1 text-sm text-slate-700">
                  Contacto: {selectedConversation.whatsappUserId}
                </p>

                <button
                  className={[
                    "mt-3 w-full rounded-md px-3 py-2 text-sm font-semibold",
                    isBlocked
                      ? "border border-red-300 bg-red-50 text-red-700 hover:bg-red-100"
                      : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                  ].join(" ")}
                  onClick={() => {
                    if (selectedWhatsappUserId === null) {
                      return;
                    }
                    if (isBlocked) {
                      removeBlacklistMutation.mutate(selectedWhatsappUserId);
                    } else {
                      addBlacklistMutation.mutate(selectedWhatsappUserId);
                    }
                  }}
                  type="button"
                >
                  {isBlocked ? "Quitar de blacklist" : "Agregar a blacklist"}
                </button>

                <p className="mt-2 text-xs text-slate-500">
                  Estado: {isBlocked ? "bloqueado" : "permitido"}
                </p>
              </div>

              <div className="rounded-lg border border-border-subtle p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Sesión
                </p>
                <button
                  className="mt-3 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-60"
                  disabled={closeSessionMutation.isPending}
                  onClick={() => {
                    if (selectedConversationId === null) {
                      return;
                    }
                    const isConfirmed = window.confirm(
                      "¿Seguro que quieres cerrar la sesión de esta conversación?"
                    );
                    if (!isConfirmed) {
                      return;
                    }
                    closeSessionMutation.mutate(selectedConversationId);
                  }}
                  type="button"
                >
                  {closeSessionMutation.isPending ? "Cerrando..." : "Cerrar sesión"}
                </button>
              </div>
            </>
          )}
        </article>
      </section>
    </appShellModule.AppShell>
  );
}

import * as reactModule from "react";

import * as reactQueryModule from "@tanstack/react-query";
import * as radixSwitchModule from "@radix-ui/react-switch";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import type * as conversationModel from "@domain/models/conversation";
import * as dateUtilsModule from "@shared/utils/date";

const conversationsQueryKey = ["conversations"] as const;
const blacklistQueryKey = ["blacklist"] as const;

export function InboxPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const conversationsQuery = reactQueryModule.useQuery({
    queryKey: conversationsQueryKey,
    queryFn: () => appContainer.conversationUseCase.listConversations()
  });

  const blacklistQuery = reactQueryModule.useQuery({
    queryKey: blacklistQueryKey,
    queryFn: () => appContainer.blacklistUseCase.list()
  });

  const [selectedConversationId, setSelectedConversationId] = reactModule.useState<string | null>(
    null
  );

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
    queryFn: () => appContainer.conversationUseCase.listMessages(selectedConversationId ?? "")
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

  const selectedWhatsappUserId = selectedConversation?.whatsappUserId ?? null;
  const isBlocked =
    selectedWhatsappUserId !== null
      ? (blacklistQuery.data?.some((entry) => entry.whatsappUserId === selectedWhatsappUserId) ??
        false)
      : false;

  return (
    <appShellModule.AppShell>
      <section className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)_320px]">
        <article className="rounded-xl border border-slate-200 bg-white">
          <header className="border-b border-slate-200 p-4">
            <h2 className="text-base font-semibold">Conversaciones</h2>
            <p className="text-xs text-slate-500">Selecciona una conversación para ver detalle.</p>
          </header>
          <div className="max-h-[70vh] overflow-auto p-2">
            {conversationsQuery.isLoading ? (
              <p className="p-3 text-sm text-slate-500">Cargando...</p>
            ) : null}
            {conversationsQuery.data?.length === 0 ? (
              <p className="p-3 text-sm text-slate-500">No hay conversaciones aún.</p>
            ) : null}
            {conversationsQuery.data?.map((conversation) => {
              const isSelected = conversation.conversationId === selectedConversationId;
              return (
                <button
                  className={[
                    "mb-2 w-full rounded-lg border p-3 text-left",
                    isSelected
                      ? "border-brand-teal bg-teal-50"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  ].join(" ")}
                  key={conversation.conversationId}
                  onClick={() => {
                    setSelectedConversationId(conversation.conversationId);
                  }}
                  type="button"
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-semibold text-brand-ink">
                      {conversation.whatsappUserId}
                    </p>
                    <statusBadgeModule.StatusBadge
                      label={conversation.controlMode}
                      tone={conversation.controlMode === "AI" ? "success" : "warning"}
                    />
                  </div>
                  <p className="truncate text-xs text-slate-500">
                    {conversation.lastMessagePreview ?? "Sin preview"}
                  </p>
                </button>
              );
            })}
          </div>
        </article>

        <article className="rounded-xl border border-slate-200 bg-white">
          <header className="border-b border-slate-200 p-4">
            <h2 className="text-base font-semibold">Mensajes</h2>
            {selectedConversation !== undefined ? (
              <p className="text-xs text-slate-500">{selectedConversation.whatsappUserId}</p>
            ) : (
              <p className="text-xs text-slate-500">Selecciona una conversación.</p>
            )}
          </header>
          <div className="max-h-[70vh] space-y-3 overflow-auto p-4">
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
        </article>

        <article className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-base font-semibold">Control</h2>

          {selectedConversation === undefined ? (
            <p className="text-sm text-slate-500">
              Selecciona una conversación para gestionar control y blacklist.
            </p>
          ) : (
            <>
              <div className="rounded-lg border border-slate-200 p-3">
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

              <div className="rounded-lg border border-slate-200 p-3">
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
            </>
          )}
        </article>
      </section>
    </appShellModule.AppShell>
  );
}

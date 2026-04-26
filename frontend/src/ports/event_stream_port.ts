export type AppEvent =
  | { type: "connected"; tenantId: string }
  | { type: "conversation.updated"; id: string }
  | { type: "scheduling_request.updated"; id: string }
  | { type: "reminder.updated"; id: string };

export type EventStreamDisconnect = () => void;

export interface EventStreamPort {
  connect(onEvent: (event: AppEvent) => void): EventStreamDisconnect;
}

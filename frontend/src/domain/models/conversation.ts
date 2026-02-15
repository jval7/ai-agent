export type ControlMode = "AI" | "HUMAN";

export interface ConversationSummary {
  conversationId: string;
  whatsappUserId: string;
  lastMessagePreview: string | null;
  updatedAt: string;
  controlMode: ControlMode;
}

export interface ConversationMessage {
  messageId: string;
  conversationId: string;
  role: string;
  direction: string;
  content: string;
  createdAt: string;
}

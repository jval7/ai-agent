export type ControlMode = "AI" | "HUMAN";

export interface ConversationTag {
  id: string;
  name: string;
  slug: string;
  color: string;
  tagType: "SYSTEM" | "CUSTOM";
}

export interface ConversationSummary {
  conversationId: string;
  whatsappUserId: string;
  contactName: string | null;
  lastMessagePreview: string | null;
  updatedAt: string;
  controlMode: ControlMode;
  tags: ConversationTag[];
}

export interface ConversationMessage {
  messageId: string;
  conversationId: string;
  role: string;
  direction: string;
  content: string;
  createdAt: string;
}

export interface MessageSent {
  messageId: string;
  conversationId: string;
  role: string;
  content: string;
  createdAt: string;
}

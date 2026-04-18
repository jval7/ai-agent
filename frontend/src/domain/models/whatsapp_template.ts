export interface TemplateComponent {
  type: string;
  text: string;
  exampleValues?: string[];
}

export interface WhatsappTemplate {
  id: string;
  name: string;
  category: string;
  language: string;
  status: string;
  components: TemplateComponent[];
}

export interface CreateTemplateRequest {
  name: string;
  category: string;
  language: string;
  components: TemplateComponent[];
}

export type OfficialReminderKind = "ATTENDANCE" | "PAYMENT";

export type OfficialTemplateMetaStatus =
  | "NOT_CREATED"
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "DISABLED";

export interface OfficialTemplateStatus {
  kind: OfficialReminderKind;
  name: string;
  metaStatus: OfficialTemplateMetaStatus;
  rejectionReason: string | null;
}

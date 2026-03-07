export interface SystemPrompt {
  tenantId: string;
  systemPrompt: string;
}

export interface AgentSettings {
  tenantId: string;
  messageDebounceDelaySeconds: number;
}

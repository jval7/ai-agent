export interface EvalShape {
  name: string;
  description: string;
  requiredCombos: string[][];
  renderedSystemPrompt: string;
}

export interface EvalPersona {
  id: string;
  displayName: string;
  capabilities: string[];
  profileGroup: "psicologa" | "ortodoncista";
}

export interface EvalPromptVersion {
  id: string;
  label: string;
  active: boolean;
}

export interface EvalRunListItem {
  runDocId: string;
  runId: string;
  shapeName: string;
  startedAt: string;
  finishedAt: string | null;
  totalPersonas: number;
  ok: number;
  fail: number;
  skipped: number;
}

export interface EvalRunConversationMessage {
  direction: "INBOUND" | "OUTBOUND";
  content: string;
  timestamp: string;
}

export interface EvalCapabilityVerification {
  capability: string;
  verified: boolean;
  evidence: string | null;
  reasoning: string | null;
}

export interface EvalJudgeVerdict {
  declaredCapabilities: string[];
  verifications: EvalCapabilityVerification[];
  overall: "all_verified" | "partial" | "none";
  judgeModel: string;
  judgedAt: string;
  error: string | null;
}

export interface EvalRunConversationSnapshot {
  personaId: string;
  combosSatisfied: string[][];
  status: "ok" | "fail" | "skipped";
  elapsedSeconds: number | null;
  conversationId: string | null;
  schedulingRequestId: string | null;
  finalStatus: string | null;
  error: string | null;
  transcript: EvalRunConversationMessage[];
  judgeVerdict: EvalJudgeVerdict | null;
}

export interface EvalRunDetail {
  runDocId: string;
  runId: string;
  shapeName: string;
  promptVersionId: string | null;
  startedAt: string;
  finishedAt: string | null;
  totalPersonas: number;
  ok: number;
  fail: number;
  skipped: number;
  conversations: EvalRunConversationSnapshot[];
}

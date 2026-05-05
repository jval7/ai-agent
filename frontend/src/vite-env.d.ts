/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  // Gate for internal-only tools (Evaluation page, prompt-preview section).
  // Set to "true" in dev builds to show them; omit/false in prod.
  readonly VITE_SHOW_INTERNAL_TOOLS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

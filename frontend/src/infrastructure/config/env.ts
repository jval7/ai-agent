// An empty base means same origin: in deployed environments the backend serves
// this bundle itself, so every request is relative and there is no CORS.
// It stays required under `npm run dev`, where Vite (5173) and the API (8000)
// live on different ports and a relative URL would hit the dev server.
const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL;
const hasApiBaseUrl = typeof rawApiBaseUrl === "string" && rawApiBaseUrl.trim() !== "";

if (import.meta.env.DEV && !hasApiBaseUrl) {
  throw new Error("VITE_API_BASE_URL is required in development");
}

const apiBaseUrl = hasApiBaseUrl ? rawApiBaseUrl.trim() : "";

// Gate for internal-only tools (Evaluation page, prompt-preview section).
// True in `npm run dev` (because .env.local sets it) and in dev builds (Makefile sets it).
// False in prod builds.
const showInternalTools = import.meta.env.VITE_SHOW_INTERNAL_TOOLS === "true";

export const envConfig = {
  apiBaseUrl,
  showInternalTools
};

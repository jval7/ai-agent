const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (typeof apiBaseUrl !== "string" || apiBaseUrl.trim() === "") {
  throw new Error("VITE_API_BASE_URL is required");
}

// Gate for internal-only tools (Evaluation page, prompt-preview section).
// True in `npm run dev` (because .env.local sets it) and in dev builds (Makefile sets it).
// False in prod builds.
const showInternalTools = import.meta.env.VITE_SHOW_INTERNAL_TOOLS === "true";

export const envConfig = {
  apiBaseUrl,
  showInternalTools
};

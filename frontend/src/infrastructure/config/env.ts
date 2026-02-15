const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (typeof apiBaseUrl !== "string" || apiBaseUrl.trim() === "") {
  throw new Error("VITE_API_BASE_URL is required");
}

export const envConfig = {
  apiBaseUrl
};

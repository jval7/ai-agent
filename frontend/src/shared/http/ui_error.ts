import * as apiErrorModule from "@shared/http/api_error";

const NETWORK_ERROR_MESSAGE = "No se pudo conectar con el backend.";

export function resolveUiErrorMessage(errors: unknown[]): string | null {
  for (const error of errors) {
    if (error instanceof apiErrorModule.ApiError) {
      return apiErrorModule.formatApiErrorMessage(error);
    }
  }

  for (const error of errors) {
    if (error instanceof TypeError) {
      return NETWORK_ERROR_MESSAGE;
    }
  }

  return null;
}

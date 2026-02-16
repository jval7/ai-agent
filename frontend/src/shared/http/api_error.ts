export class ApiError extends Error {
  readonly statusCode: number;
  readonly requestId: string | null;

  constructor(statusCode: number, message: string, requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.requestId = requestId;
  }
}

export function formatApiErrorMessage(error: ApiError): string {
  if (error.requestId === null) {
    return error.message;
  }

  const normalizedRequestId = error.requestId.trim();
  if (normalizedRequestId === "") {
    return error.message;
  }
  return `${error.message} (request_id: ${normalizedRequestId})`;
}

export function assertIsString(value: unknown, errorMessage: string): asserts value is string {
  if (typeof value !== "string") {
    throw new Error(errorMessage);
  }
}

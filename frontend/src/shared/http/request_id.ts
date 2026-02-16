let fallbackRequestCounter = 0;

export function createRequestId(): string {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi !== undefined && typeof cryptoApi.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }

  fallbackRequestCounter += 1;
  const timestampToken = Date.now().toString(36);
  const counterToken = fallbackRequestCounter.toString(36);
  return `rid_${timestampToken}_${counterToken}`;
}

import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";

const onboardingStatusQueryKey = ["onboarding-status"] as const;

export function GoogleCalendarReauthBanner() {
  const appContainer = appContainerContextModule.useAppContainer();
  const onboardingStatusQuery = reactQueryModule.useQuery({
    queryKey: onboardingStatusQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getOnboardingStatus(),
    // Cheap to poll — same cadence the rest of the dashboard already uses.
    refetchInterval: 30_000
  });
  const reconnectMutation = reactQueryModule.useMutation({
    mutationFn: () => appContainer.onboardingUseCase.createGoogleSession(),
    onSuccess: (session) => {
      window.location.assign(session.connectUrl);
    }
  });

  if (onboardingStatusQuery.data?.googleCalendarReauthRequired !== true) {
    return null;
  }

  return (
    <div className="border-b border-amber-300 bg-amber-50 px-6 py-3 text-sm text-amber-900 shadow-sm">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
        <div className="flex items-start gap-2">
          <span aria-hidden="true" className="mt-0.5 text-base">
            ⚠️
          </span>
          <div>
            <p className="font-semibold">Google Calendar perdió la conexión</p>
            <p className="text-xs text-amber-800">
              No podemos validar disponibilidad ni crear eventos hasta que reconectes la cuenta.
            </p>
          </div>
        </div>
        <button
          className="inline-flex items-center justify-center rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={reconnectMutation.isPending}
          onClick={() => {
            reconnectMutation.mutate();
          }}
          type="button"
        >
          {reconnectMutation.isPending ? "Abriendo..." : "Reconectar Google Calendar"}
        </button>
      </div>
    </div>
  );
}

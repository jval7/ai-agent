import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as uiErrorModule from "@shared/http/ui_error";

const onboardingStatusQueryKey = ["onboarding-status"] as const;

export function OnboardingReadyRoute(props: { children: JSX.Element }) {
  const appContainer = appContainerContextModule.useAppContainer();
  const onboardingStatusQuery = reactQueryModule.useQuery({
    queryKey: onboardingStatusQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getOnboardingStatus()
  });

  if (onboardingStatusQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-brand-surface text-brand-ink">
        Validando onboarding...
      </div>
    );
  }

  const resolvedError = uiErrorModule.resolveUiErrorMessage([onboardingStatusQuery.error]);
  if (resolvedError !== null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-brand-surface p-6 text-brand-ink">
        <p className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          {resolvedError}
        </p>
      </div>
    );
  }

  if (onboardingStatusQuery.data?.ready !== true) {
    return <reactRouterDomModule.Navigate replace to="/onboarding" />;
  }

  return props.children;
}

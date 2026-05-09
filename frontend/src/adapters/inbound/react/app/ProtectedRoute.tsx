import * as reactRouterDomModule from "react-router-dom";

import * as googleCalendarReauthBannerModule from "@adapters/inbound/react/components/GoogleCalendarReauthBanner";
import * as authContextModule from "./AuthContext";

export function ProtectedRoute(props: { children: JSX.Element }) {
  const auth = authContextModule.useAuth();

  if (auth.status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-brand-surface text-brand-ink">
        Cargando sesión...
      </div>
    );
  }

  if (auth.status === "anonymous") {
    return <reactRouterDomModule.Navigate to="/login" replace />;
  }

  return (
    <>
      <googleCalendarReauthBannerModule.GoogleCalendarReauthBanner />
      {props.children}
    </>
  );
}

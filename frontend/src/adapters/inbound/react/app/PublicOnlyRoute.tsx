import * as reactRouterDomModule from "react-router-dom";

import * as authContextModule from "./AuthContext";

export function PublicOnlyRoute(props: { children: JSX.Element }) {
  const auth = authContextModule.useAuth();

  if (auth.status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-brand-surface text-brand-ink">
        Cargando sesión...
      </div>
    );
  }

  if (auth.status === "authenticated") {
    return <reactRouterDomModule.Navigate to="/inbox" replace />;
  }

  return props.children;
}

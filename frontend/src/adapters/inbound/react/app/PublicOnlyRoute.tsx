import * as reactRouterDomModule from "react-router-dom";

import * as authContextModule from "./AuthContext";

export function PublicOnlyRoute(props: { children: JSX.Element }) {
  const auth = authContextModule.useAuth();

  if (auth.status === "loading" || (auth.status === "authenticated" && auth.userProfile === null)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-brand-surface text-brand-ink">
        Cargando sesión...
      </div>
    );
  }

  if (auth.status === "authenticated") {
    if (auth.userProfile?.role === "admin") {
      return <reactRouterDomModule.Navigate to="/admin" replace />;
    }
    return <reactRouterDomModule.Navigate to="/configuraciones" replace />;
  }

  return props.children;
}

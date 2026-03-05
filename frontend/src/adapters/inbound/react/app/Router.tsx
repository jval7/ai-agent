import * as reactRouterDomModule from "react-router-dom";

import * as agendaPageModule from "@adapters/inbound/react/pages/AgendaPage";
import * as clientsPageModule from "@adapters/inbound/react/pages/ClientsPage";
import * as inboxPageModule from "@adapters/inbound/react/pages/InboxPage";
import * as loginPageModule from "@adapters/inbound/react/pages/LoginPage";
import * as onboardingPageModule from "@adapters/inbound/react/pages/OnboardingPage";
import * as promptPageModule from "@adapters/inbound/react/pages/PromptPage";

import * as onboardingReadyRouteModule from "./OnboardingReadyRoute";
import * as protectedRouteModule from "./ProtectedRoute";
import * as publicOnlyRouteModule from "./PublicOnlyRoute";

function LegacyOnboardingRedirect() {
  const location = reactRouterDomModule.useLocation();
  return <reactRouterDomModule.Navigate replace to={`/onboarding${location.search}`} />;
}

export function AppRouter() {
  return (
    <reactRouterDomModule.BrowserRouter>
      <reactRouterDomModule.Routes>
        <reactRouterDomModule.Route
          element={
            <publicOnlyRouteModule.PublicOnlyRoute>
              <loginPageModule.LoginPage />
            </publicOnlyRouteModule.PublicOnlyRoute>
          }
          path="/login"
        />

        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <onboardingPageModule.OnboardingPage />
            </protectedRouteModule.ProtectedRoute>
          }
          path="/onboarding"
        />
        <reactRouterDomModule.Route
          element={<LegacyOnboardingRedirect />}
          path="/onboarding/whatsapp"
        />
        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <onboardingReadyRouteModule.OnboardingReadyRoute>
                <agendaPageModule.AgendaPage />
              </onboardingReadyRouteModule.OnboardingReadyRoute>
            </protectedRouteModule.ProtectedRoute>
          }
          path="/agenda"
        />
        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <onboardingReadyRouteModule.OnboardingReadyRoute>
                <inboxPageModule.InboxPage />
              </onboardingReadyRouteModule.OnboardingReadyRoute>
            </protectedRouteModule.ProtectedRoute>
          }
          path="/inbox"
        />
        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <onboardingReadyRouteModule.OnboardingReadyRoute>
                <clientsPageModule.ClientsPage />
              </onboardingReadyRouteModule.OnboardingReadyRoute>
            </protectedRouteModule.ProtectedRoute>
          }
          path="/clientes"
        />
        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <onboardingReadyRouteModule.OnboardingReadyRoute>
                <promptPageModule.PromptPage />
              </onboardingReadyRouteModule.OnboardingReadyRoute>
            </protectedRouteModule.ProtectedRoute>
          }
          path="/agent/prompt"
        />

        <reactRouterDomModule.Route
          element={<reactRouterDomModule.Navigate replace to="/onboarding" />}
          path="/"
        />
        <reactRouterDomModule.Route
          element={<reactRouterDomModule.Navigate replace to="/onboarding" />}
          path="*"
        />
      </reactRouterDomModule.Routes>
    </reactRouterDomModule.BrowserRouter>
  );
}

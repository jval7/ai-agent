import * as reactRouterDomModule from "react-router-dom";

import * as acceptInvitePageModule from "@adapters/inbound/react/pages/AcceptInvitePage";
import * as agendaPageModule from "@adapters/inbound/react/pages/AgendaPage";
import * as clientsPageModule from "@adapters/inbound/react/pages/ClientsPage";
import * as configuracionesPageModule from "@adapters/inbound/react/pages/ConfiguracionesPage";
import * as evaluacionPageModule from "@adapters/inbound/react/pages/EvaluacionPage";
import * as runDetailPageModule from "@adapters/inbound/react/pages/evaluacion/RunDetailPage";
import * as finanzasPageModule from "@adapters/inbound/react/pages/FinanzasPage";
import * as forgotPasswordPageModule from "@adapters/inbound/react/pages/ForgotPasswordPage";
import * as inboxPageModule from "@adapters/inbound/react/pages/InboxPage";
import * as landingPageModule from "@adapters/inbound/react/pages/LandingPage";
import * as loginPageModule from "@adapters/inbound/react/pages/LoginPage";
import * as resetPasswordPageModule from "@adapters/inbound/react/pages/ResetPasswordPage";
import * as roadmapPageModule from "@adapters/inbound/react/pages/RoadmapPage";
import * as recordatoriosPageModule from "@adapters/inbound/react/pages/RecordatoriosPage";
import * as adminHomePageModule from "@adapters/inbound/react/pages/admin/AdminHomePage";
import * as adminGlobalDashboardPageModule from "@adapters/inbound/react/pages/admin/AdminGlobalDashboardPage";
import * as adminTenantDetailPageModule from "@adapters/inbound/react/pages/admin/AdminTenantDetailPage";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";

import * as adminRouteModule from "./AdminRoute";
import * as onboardingReadyRouteModule from "./OnboardingReadyRoute";
import * as protectedRouteModule from "./ProtectedRoute";
import * as publicOnlyRouteModule from "./PublicOnlyRoute";

function LegacyOnboardingRedirect() {
  const location = reactRouterDomModule.useLocation();
  return <reactRouterDomModule.Navigate replace to={`/configuraciones${location.search}`} />;
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

        {/* ===== Admin routes ===== */}
        <reactRouterDomModule.Route
          element={
            <adminRouteModule.AdminRoute>
              <appShellModule.AppShell>
                <adminHomePageModule.AdminHomePage />
              </appShellModule.AppShell>
            </adminRouteModule.AdminRoute>
          }
          path="/admin"
        />
        <reactRouterDomModule.Route
          element={
            <adminRouteModule.AdminRoute>
              <appShellModule.AppShell>
                <adminGlobalDashboardPageModule.AdminGlobalDashboardPage />
              </appShellModule.AppShell>
            </adminRouteModule.AdminRoute>
          }
          path="/admin/dashboard"
        />
        <reactRouterDomModule.Route
          element={
            <adminRouteModule.AdminRoute>
              <appShellModule.AppShell>
                <adminTenantDetailPageModule.AdminTenantDetailPage />
              </appShellModule.AppShell>
            </adminRouteModule.AdminRoute>
          }
          path="/admin/tenants/:tenantId"
        />
        <reactRouterDomModule.Route
          element={
            <adminRouteModule.AdminRoute>
              <appShellModule.AppShell>
                <adminTenantDetailPageModule.AdminTenantDetailPage />
              </appShellModule.AppShell>
            </adminRouteModule.AdminRoute>
          }
          path="/admin/tenants/:tenantId/:tab"
        />

        {/* ===== Professional routes ===== */}
        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <configuracionesPageModule.ConfiguracionesPage />
            </protectedRouteModule.ProtectedRoute>
          }
          path="/configuraciones"
        />
        {/* Legacy redirects */}
        <reactRouterDomModule.Route element={<LegacyOnboardingRedirect />} path="/onboarding" />
        <reactRouterDomModule.Route
          element={<LegacyOnboardingRedirect />}
          path="/onboarding/whatsapp"
        />
        <reactRouterDomModule.Route
          element={<reactRouterDomModule.Navigate replace to="/configuraciones" />}
          path="/agent/prompt"
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
                <finanzasPageModule.FinanzasPage />
              </onboardingReadyRouteModule.OnboardingReadyRoute>
            </protectedRouteModule.ProtectedRoute>
          }
          path="/finanzas"
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
            <reactRouterDomModule.Navigate replace to="/configuraciones?tab=recordatorios" />
          }
          path="/plantillas"
        />
        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <onboardingReadyRouteModule.OnboardingReadyRoute>
                <recordatoriosPageModule.RecordatoriosPage />
              </onboardingReadyRouteModule.OnboardingReadyRoute>
            </protectedRouteModule.ProtectedRoute>
          }
          path="/recordatorios"
        />
        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <evaluacionPageModule.EvaluacionPage />
            </protectedRouteModule.ProtectedRoute>
          }
          path="/evaluacion"
        />
        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <runDetailPageModule.RunDetailPage />
            </protectedRouteModule.ProtectedRoute>
          }
          path="/evaluacion/runs/:runDocId"
        />

        <reactRouterDomModule.Route
          element={
            <publicOnlyRouteModule.PublicOnlyRoute>
              <landingPageModule.LandingPage />
            </publicOnlyRouteModule.PublicOnlyRoute>
          }
          path="/"
        />
        <reactRouterDomModule.Route
          element={
            <publicOnlyRouteModule.PublicOnlyRoute>
              <roadmapPageModule.RoadmapPage />
            </publicOnlyRouteModule.PublicOnlyRoute>
          }
          path="/roadmap"
        />
        <reactRouterDomModule.Route
          element={
            <publicOnlyRouteModule.PublicOnlyRoute>
              <acceptInvitePageModule.AcceptInvitePage />
            </publicOnlyRouteModule.PublicOnlyRoute>
          }
          path="/accept-invite"
        />
        <reactRouterDomModule.Route
          element={
            <publicOnlyRouteModule.PublicOnlyRoute>
              <forgotPasswordPageModule.ForgotPasswordPage />
            </publicOnlyRouteModule.PublicOnlyRoute>
          }
          path="/forgot-password"
        />
        <reactRouterDomModule.Route
          element={
            <publicOnlyRouteModule.PublicOnlyRoute>
              <resetPasswordPageModule.ResetPasswordPage />
            </publicOnlyRouteModule.PublicOnlyRoute>
          }
          path="/reset-password"
        />
        <reactRouterDomModule.Route
          element={<reactRouterDomModule.Navigate replace to="/configuraciones" />}
          path="*"
        />
      </reactRouterDomModule.Routes>
    </reactRouterDomModule.BrowserRouter>
  );
}

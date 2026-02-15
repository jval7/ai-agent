import * as reactRouterDomModule from "react-router-dom";

import * as inboxPageModule from "@adapters/inbound/react/pages/InboxPage";
import * as loginPageModule from "@adapters/inbound/react/pages/LoginPage";
import * as onboardingPageModule from "@adapters/inbound/react/pages/OnboardingPage";
import * as promptPageModule from "@adapters/inbound/react/pages/PromptPage";
import * as registerPageModule from "@adapters/inbound/react/pages/RegisterPage";

import * as protectedRouteModule from "./ProtectedRoute";
import * as publicOnlyRouteModule from "./PublicOnlyRoute";

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
            <publicOnlyRouteModule.PublicOnlyRoute>
              <registerPageModule.RegisterPage />
            </publicOnlyRouteModule.PublicOnlyRoute>
          }
          path="/register"
        />

        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <onboardingPageModule.OnboardingPage />
            </protectedRouteModule.ProtectedRoute>
          }
          path="/onboarding/whatsapp"
        />
        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <inboxPageModule.InboxPage />
            </protectedRouteModule.ProtectedRoute>
          }
          path="/inbox"
        />
        <reactRouterDomModule.Route
          element={
            <protectedRouteModule.ProtectedRoute>
              <promptPageModule.PromptPage />
            </protectedRouteModule.ProtectedRoute>
          }
          path="/agent/prompt"
        />

        <reactRouterDomModule.Route
          element={<reactRouterDomModule.Navigate replace to="/inbox" />}
          path="/"
        />
        <reactRouterDomModule.Route
          element={<reactRouterDomModule.Navigate replace to="/inbox" />}
          path="*"
        />
      </reactRouterDomModule.Routes>
    </reactRouterDomModule.BrowserRouter>
  );
}

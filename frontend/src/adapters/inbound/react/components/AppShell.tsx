import type * as reactModule from "react";
import * as reactRouterDomModule from "react-router-dom";

import * as authContextModule from "@adapters/inbound/react/app/AuthContext";

const navLinks = [
  { to: "/onboarding/whatsapp", label: "Onboarding" },
  { to: "/inbox", label: "Inbox" },
  { to: "/agent/prompt", label: "Prompt" }
];

export function AppShell(props: { children: reactModule.ReactNode }) {
  const auth = authContextModule.useAuth();
  const navigate = reactRouterDomModule.useNavigate();

  const handleLogout = async () => {
    await auth.logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-brand-surface text-brand-ink">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-brand-teal">
              AI-Agents
            </p>
            <h1 className="text-lg font-semibold">Panel operativo</h1>
          </div>
          <nav className="flex items-center gap-2">
            {navLinks.map((link) => (
              <reactRouterDomModule.NavLink
                className={({ isActive }) =>
                  [
                    "rounded-md px-3 py-2 text-sm font-medium",
                    isActive ? "bg-brand-teal text-white" : "text-slate-700 hover:bg-slate-100"
                  ].join(" ")
                }
                key={link.to}
                to={link.to}
              >
                {link.label}
              </reactRouterDomModule.NavLink>
            ))}
            <button
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              onClick={() => {
                void handleLogout();
              }}
              type="button"
            >
              Salir
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl px-6 py-6">{props.children}</main>
    </div>
  );
}

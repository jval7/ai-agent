import * as reactModule from "react";
import * as reactRouterDomModule from "react-router-dom";

import * as authContextModule from "@adapters/inbound/react/app/AuthContext";
import * as useSidebarCollapsedModule from "@shared/hooks/useSidebarCollapsed";

function CalendarIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path
        d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function InboxIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path
        d="M2.25 13.5h3.86a2.25 2.25 0 0 1 2.012 1.244l.256.512a2.25 2.25 0 0 0 2.013 1.244h3.218a2.25 2.25 0 0 0 2.013-1.244l.256-.512a2.25 2.25 0 0 1 2.013-1.244h3.859M12 3v8.25m0 0-3-3m3 3 3-3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function UsersIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path
        d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function WalletIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path
        d="M21 12a2.25 2.25 0 0 0-2.25-2.25H15a3 3 0 1 1-6 0H5.25A2.25 2.25 0 0 0 3 12m18 0v6a2.25 2.25 0 0 1-2.25 2.25H5.25A2.25 2.25 0 0 1 3 18v-6m18 0V9M3 12V9m18 0a2.25 2.25 0 0 0-2.25-2.25H5.25A2.25 2.25 0 0 0 3 9m18 0V6a2.25 2.25 0 0 0-2.25-2.25H5.25A2.25 2.25 0 0 0 3 6v3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path
        d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.248a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28ZM15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path
        d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path
        d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function HamburgerIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-6 w-6"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      <path
        d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <path d="M15 19l-7-7 7-7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      <path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Orden por frecuencia de uso día a día. Configuraciones al final (setup-once).
const navLinks = [
  { to: "/agenda", label: "Agenda", Icon: CalendarIcon },
  { to: "/inbox", label: "Conversaciones", Icon: InboxIcon },
  { to: "/clientes", label: "Clientes", Icon: UsersIcon },
  { to: "/finanzas", label: "Finanzas", Icon: WalletIcon },
  { to: "/recordatorios", label: "Recordatorios", Icon: BellIcon },
  { to: "/configuraciones", label: "Configuraciones", Icon: SettingsIcon }
];

export function AppShell(props: { children: reactModule.ReactNode }) {
  const auth = authContextModule.useAuth();
  const navigate = reactRouterDomModule.useNavigate();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = reactModule.useState(false);
  const [isCollapsed, toggleCollapsed] = useSidebarCollapsedModule.useSidebarCollapsed();

  const handleLogout = async () => {
    await auth.logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex h-screen overflow-hidden bg-brand-surface text-brand-ink">
      {isMobileMenuOpen ? (
        <div
          className="fixed inset-0 z-40 bg-black/20 lg:hidden"
          onClick={() => {
            setIsMobileMenuOpen(false);
          }}
        />
      ) : null}

      <aside
        className={[
          "fixed inset-y-0 left-0 z-50 flex flex-col bg-surface-low transition-all duration-200 lg:static lg:translate-x-0",
          isMobileMenuOpen ? "translate-x-0 w-64" : "-translate-x-full w-64",
          isCollapsed ? "lg:w-16" : "lg:w-64"
        ].join(" ")}
      >
        <div className="flex h-16 shrink-0 items-center px-3">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-teal text-white">
            <svg
              aria-hidden="true"
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path
                d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div
            className={[
              "ml-3 min-w-0 flex-1 overflow-hidden transition-all duration-200",
              isCollapsed ? "lg:hidden" : ""
            ].join(" ")}
          >
            <p className="truncate text-sm font-bold font-display text-brand-teal">Agendachat</p>
            <p className="truncate text-[10px] uppercase tracking-widest text-sidebar-text/70">
              Panel operativo
            </p>
          </div>
          <button
            aria-label={isCollapsed ? "Expandir menú" : "Colapsar menú"}
            className="hidden lg:flex ml-auto shrink-0 items-center justify-center rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
            onClick={toggleCollapsed}
            type="button"
          >
            {isCollapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-4 scrollbar-thin">
          {navLinks.map((link) => (
            <reactRouterDomModule.NavLink
              className={({ isActive }) =>
                [
                  "flex items-center rounded-lg px-2 py-2.5 text-sm transition-colors",
                  isCollapsed ? "lg:justify-center lg:px-0" : "gap-3 px-3",
                  isActive
                    ? "bg-surface-white font-semibold text-brand-teal shadow-card-sm"
                    : "font-normal text-sidebar-text hover:bg-sidebar-hover hover:text-brand-ink"
                ].join(" ")
              }
              key={link.to}
              onClick={() => {
                setIsMobileMenuOpen(false);
              }}
              title={isCollapsed ? link.label : undefined}
              to={link.to}
            >
              <link.Icon />
              <span className={isCollapsed ? "lg:hidden" : ""}>{link.label}</span>
            </reactRouterDomModule.NavLink>
          ))}
        </nav>

        <div className="p-2">
          <button
            className={[
              "flex w-full items-center rounded-lg px-2 py-2.5 text-sm font-medium text-sidebar-text transition-colors hover:bg-sidebar-hover hover:text-brand-ink",
              isCollapsed ? "lg:justify-center lg:px-0" : "gap-3 px-3"
            ].join(" ")}
            onClick={() => {
              void handleLogout();
            }}
            title={isCollapsed ? "Salir" : undefined}
            type="button"
          >
            <LogoutIcon />
            <span className={isCollapsed ? "lg:hidden" : ""}>Salir</span>
          </button>
        </div>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 shrink-0 items-center bg-brand-surface px-4 lg:hidden">
          <button
            className="rounded-md p-2 text-slate-600 hover:bg-slate-100"
            onClick={() => {
              setIsMobileMenuOpen(true);
            }}
            type="button"
          >
            <HamburgerIcon />
          </button>
          <p className="ml-3 text-sm font-semibold text-brand-ink">Agendachat</p>
        </header>

        <main className="flex-1 overflow-y-auto p-3 sm:p-6">{props.children}</main>
      </div>
    </div>
  );
}

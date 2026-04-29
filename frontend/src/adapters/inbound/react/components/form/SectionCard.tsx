import * as reactModule from "react";

interface SectionCardProps {
  title: string;
  subtitle?: string;
  footer?: reactModule.ReactNode;
  children: reactModule.ReactNode;
  /**
   * Renders the card with a clickable header that collapses/expands the body.
   * When collapsed, `previewWhenCollapsed` is shown under the subtitle so the
   * user gets a sense of the section state without expanding it.
   */
  collapsible?: boolean;
  /** Initial open state when no persisted value is available. Defaults to true. */
  defaultOpen?: boolean;
  /**
   * If provided, the open state is persisted in localStorage under this key so
   * the section keeps its state across navigations and reloads.
   */
  storageKey?: string;
  previewWhenCollapsed?: reactModule.ReactNode;
}

function readStoredOpenState(storageKey: string | undefined): boolean | null {
  if (storageKey === undefined) return null;
  try {
    const stored = window.localStorage.getItem(storageKey);
    if (stored === "open") return true;
    if (stored === "closed") return false;
  } catch {
    // localStorage unavailable (private mode, quota); fall back to default.
  }
  return null;
}

function writeStoredOpenState(storageKey: string | undefined, isOpen: boolean): void {
  if (storageKey === undefined) return;
  try {
    window.localStorage.setItem(storageKey, isOpen ? "open" : "closed");
  } catch {
    // ignore
  }
}

function ChevronIcon(props: { isOpen: boolean }) {
  const rotation = props.isOpen ? "rotate-180" : "";
  return (
    <svg
      aria-hidden="true"
      className={`mt-1 h-5 w-5 flex-shrink-0 text-slate-400 transition-transform ${rotation}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SectionCard(props: SectionCardProps) {
  const collapsible = props.collapsible ?? false;

  const [isOpen, setIsOpen] = reactModule.useState<boolean>(() => {
    if (!collapsible) return true;
    const stored = readStoredOpenState(props.storageKey);
    if (stored !== null) return stored;
    return props.defaultOpen ?? true;
  });

  const handleToggle = () => {
    const next = !isOpen;
    setIsOpen(next);
    writeStoredOpenState(props.storageKey, next);
  };

  if (!collapsible) {
    return (
      <section className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
        <h3 className="text-xl font-semibold text-brand-ink">{props.title}</h3>
        {props.subtitle !== undefined ? (
          <p className="mt-1 text-sm text-slate-600">{props.subtitle}</p>
        ) : null}
        <div className="mt-6">{props.children}</div>
        {props.footer !== undefined ? <div className="mt-6">{props.footer}</div> : null}
      </section>
    );
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-border-subtle bg-white shadow-card">
      <button
        aria-expanded={isOpen}
        className="flex w-full items-start justify-between gap-4 p-6 text-left transition-colors hover:bg-slate-50/60"
        onClick={handleToggle}
        type="button"
      >
        <div className="flex-1">
          <h3 className="text-xl font-semibold text-brand-ink">{props.title}</h3>
          {props.subtitle !== undefined ? (
            <p className="mt-1 text-sm text-slate-600">{props.subtitle}</p>
          ) : null}
          {!isOpen && props.previewWhenCollapsed !== undefined ? (
            <p className="mt-2 text-sm text-slate-500">{props.previewWhenCollapsed}</p>
          ) : null}
        </div>
        <ChevronIcon isOpen={isOpen} />
      </button>
      {isOpen ? (
        <div className="border-t border-border-subtle p-6">
          <div>{props.children}</div>
          {props.footer !== undefined ? <div className="mt-6">{props.footer}</div> : null}
        </div>
      ) : null}
    </section>
  );
}

import * as reactModule from "react";

/**
 * Collapsible card with a clickable header and an expandable body.
 *
 * Header shows a chevron + summary content. Body renders below when open.
 * Used for nested lists where each item can be opened independently to
 * reduce visual density (services > tariffs, payment methods).
 *
 * Uncontrolled by default (manages its own `open` state). Pass `open` and
 * `onOpenChange` to make it controlled.
 */
interface CollapsibleCardProps {
  /** Content rendered in the header next to the chevron (always visible). */
  summary: reactModule.ReactNode;
  /** Optional secondary header content rendered to the right (badges, X). */
  trailing?: reactModule.ReactNode;
  /** Body content shown when expanded. */
  children: reactModule.ReactNode;
  /** Default open state when uncontrolled. Defaults to `false`. */
  defaultOpen?: boolean;
  /** Controlled open state. */
  open?: boolean;
  /** Called when the user toggles the card. */
  onOpenChange?: (open: boolean) => void;
  /** Optional className applied to the outer card. */
  className?: string;
}

export function CollapsibleCard(props: CollapsibleCardProps) {
  const { summary, trailing, children, defaultOpen, open, onOpenChange, className } = props;

  const [internalOpen, setInternalOpen] = reactModule.useState<boolean>(defaultOpen ?? false);
  const isControlled = open !== undefined;
  const isOpen = isControlled ? open : internalOpen;

  const toggle = () => {
    const next = !isOpen;
    if (!isControlled) {
      setInternalOpen(next);
    }
    if (onOpenChange !== undefined) {
      onOpenChange(next);
    }
  };

  const baseClass = "rounded-2xl bg-white shadow-card transition-shadow hover:shadow-md";
  const wrapperClass = className === undefined ? baseClass : `${baseClass} ${className}`;

  return (
    <div className={wrapperClass}>
      <div className="flex items-center gap-3 px-4 py-3">
        <button
          aria-expanded={isOpen}
          className="flex flex-1 items-center gap-3 rounded-lg text-left focus:outline-none focus:ring-2 focus:ring-brand-teal/30"
          onClick={toggle}
          type="button"
        >
          <ChevronIcon open={isOpen} />
          <div className="flex-1 min-w-0">{summary}</div>
        </button>
        {trailing !== undefined ? (
          <div className="flex shrink-0 items-center gap-1">{trailing}</div>
        ) : null}
      </div>
      {isOpen ? <div className="border-t border-slate-100 px-4 py-4">{children}</div> : null}
    </div>
  );
}

function ChevronIcon(props: { open: boolean }) {
  const rotation = props.open ? "rotate-90" : "rotate-0";
  return (
    <svg
      className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${rotation}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

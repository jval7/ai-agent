import type * as reactModule from "react";

interface SectionGroupProps {
  title: string;
  description?: string;
  /**
   * "primary": prominent header for the main groups.
   * "muted": discreet header for secondary groups (e.g. advanced settings)
   * so they don't compete visually with the primary ones.
   */
  tone?: "primary" | "muted";
  children: reactModule.ReactNode;
}

export function SectionGroup(props: SectionGroupProps) {
  const tone = props.tone ?? "primary";

  if (tone === "muted") {
    return (
      <div className="space-y-4">
        <header>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {props.title}
          </h2>
          <div className="mt-2 border-t border-border-subtle/60" />
        </header>
        <div className="space-y-4">{props.children}</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-lg font-semibold text-brand-ink">{props.title}</h2>
        {props.description !== undefined ? (
          <p className="mt-1 text-sm text-slate-500">{props.description}</p>
        ) : null}
        <div className="mt-3 border-t border-border-subtle" />
      </header>
      <div className="space-y-4">{props.children}</div>
    </div>
  );
}

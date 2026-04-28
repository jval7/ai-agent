import type * as reactModule from "react";

interface SectionCardProps {
  title: string;
  subtitle?: string;
  footer?: reactModule.ReactNode;
  children: reactModule.ReactNode;
}

export function SectionCard(props: SectionCardProps) {
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

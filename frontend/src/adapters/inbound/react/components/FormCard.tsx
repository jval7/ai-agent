import type * as reactModule from "react";

export function FormCard(props: {
  title: string;
  subtitle: string;
  children: reactModule.ReactNode;
}) {
  return (
    <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <header className="mb-5">
        <h1 className="text-2xl font-semibold text-brand-ink">{props.title}</h1>
        <p className="mt-1 text-sm text-slate-600">{props.subtitle}</p>
      </header>
      {props.children}
    </section>
  );
}

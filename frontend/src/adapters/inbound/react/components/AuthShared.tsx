import type * as reactModule from "react";

interface EyeIconProps {
  isVisible: boolean;
}

export function AuthScreenContainer(props: { children: reactModule.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-200 px-4 py-8">
      {props.children}
    </div>
  );
}

export function AuthCard(props: {
  title: string;
  subtitle: string;
  children: reactModule.ReactNode;
}) {
  return (
    <section className="w-full max-w-[448px] rounded-3xl bg-white px-10 py-10 shadow-[0_20px_40px_rgba(15,23,42,0.08)]">
      <BrandLockup />
      <header className="mt-10 text-center">
        <h1 className="text-4xl font-bold leading-tight text-slate-900 md:text-5xl">
          {props.title}
        </h1>
        <p className="mt-3 text-xl leading-tight text-slate-600 md:text-3xl">{props.subtitle}</p>
      </header>
      <div className="mt-10">{props.children}</div>
    </section>
  );
}

export function AuthInputLabel(props: { htmlFor: string; text: string }) {
  return (
    <label
      className="mb-2 block text-base font-medium text-slate-700 md:text-xl"
      htmlFor={props.htmlFor}
    >
      {props.text}
    </label>
  );
}

export function EyeToggleButton(props: { isVisible: boolean; onClick: () => void }) {
  return (
    <button
      aria-label={props.isVisible ? "Ocultar contraseña" : "Mostrar contraseña"}
      className="absolute inset-y-0 right-3 my-auto h-8 w-8 rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
      onClick={props.onClick}
      type="button"
    >
      <EyeIcon isVisible={props.isVisible} />
    </button>
  );
}

export function SecurityHint() {
  return (
    <div className="mt-6 flex items-center justify-center gap-2 text-base text-slate-600 md:text-[15px]">
      <ShieldCheckIcon />
      <span>Tus datos viajan cifrados</span>
    </div>
  );
}

function BrandLockup() {
  return (
    <div className="flex items-center justify-center gap-4">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-teal-700 shadow-md">
        <ChatIcon />
      </div>
      <div>
        <p className="text-3xl font-bold leading-none text-slate-900 md:text-4xl">AI-Agents</p>
        <p className="mt-1 text-sm text-slate-500 md:text-lg">WhatsApp Multi-tenant</p>
      </div>
    </div>
  );
}

function ChatIcon() {
  return (
    <svg aria-hidden="true" fill="none" height="28" viewBox="0 0 24 24" width="28">
      <path
        d="M7 6.75C7 5.7835 7.7835 5 8.75 5H17.25C18.2165 5 19 5.7835 19 6.75V13.25C19 14.2165 18.2165 15 17.25 15H11.535L8.71 17.26C8.13817 17.7174 7.29403 17.3103 7.29403 16.578V15H6.75C5.7835 15 5 14.2165 5 13.25V7.75C5 6.7835 5.7835 6 6.75 6H7V6.75Z"
        stroke="white"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function EyeIcon(props: EyeIconProps) {
  if (props.isVisible) {
    return (
      <svg aria-hidden="true" fill="none" height="20" viewBox="0 0 24 24" width="20">
        <path
          d="M3 3L21 21"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
        <path
          d="M10.584 10.587a2 2 0 0 0 2.829 2.828"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
        <path
          d="M9.88 4.24A10.94 10.94 0 0 1 12 4c5.455 0 9.5 4 10.5 8-0.386 1.544-1.25 3.035-2.52 4.34"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
        <path
          d="M6.61 6.61C4.48 8.08 3.23 10.06 2.5 12c1 4 5.045 8 9.5 8 1.384 0 2.67-0.257 3.842-0.707"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" fill="none" height="20" viewBox="0 0 24 24" width="20">
      <path
        d="M2.5 12c1-4 5.045-8 9.5-8s8.5 4 9.5 8c-1 4-5.045 8-9.5 8s-8.5-4-9.5-8Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function ShieldCheckIcon() {
  return (
    <svg aria-hidden="true" fill="none" height="18" viewBox="0 0 24 24" width="18">
      <path
        d="M12 3L5 6v6c0 4.421 2.865 7.945 7 9 4.135-1.055 7-4.579 7-9V6l-7-3Z"
        stroke="#22c55e"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="m9 12 2 2 4-4"
        stroke="#22c55e"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

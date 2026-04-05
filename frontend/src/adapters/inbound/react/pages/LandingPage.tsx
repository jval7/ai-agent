import * as reactRouterDomModule from "react-router-dom";

function FeatureCard(props: { icon: string; title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-border-subtle bg-white p-8 shadow-card transition hover:shadow-lg">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-accent-light text-2xl">
        {props.icon}
      </div>
      <h3 className="text-lg font-semibold text-brand-ink">{props.title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{props.description}</p>
    </div>
  );
}

export function LandingPage() {
  return (
    <div className="min-h-screen bg-brand-surface">
      {/* Navbar */}
      <nav className="sticky top-0 z-10 border-b border-border-subtle bg-white/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-teal text-lg font-bold text-white">
              C
            </div>
            <span className="text-lg font-bold text-brand-ink">Claudia Agent</span>
          </div>
          <reactRouterDomModule.Link
            className="rounded-xl bg-brand-teal px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-teal-hover"
            to="/login"
          >
            Iniciar sesion
          </reactRouterDomModule.Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 pb-16 pt-20 text-center md:pt-28">
        <span className="inline-block rounded-full bg-brand-accent-light px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-brand-teal">
          Asistente inteligente para profesionales de salud mental
        </span>
        <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-extrabold leading-tight text-brand-ink md:text-5xl lg:text-6xl">
          Tu consultorio en WhatsApp, atendiendo 24/7
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-600">
          Claudia Agent automatiza la atencion de tus pacientes por WhatsApp: agenda citas, responde
          consultas frecuentes y gestiona tu practica mientras tu te enfocas en lo que importa.
        </p>
        <div className="mt-10 flex items-center justify-center gap-4">
          <reactRouterDomModule.Link
            className="rounded-xl bg-brand-teal px-8 py-3.5 text-base font-semibold text-white shadow-md transition hover:bg-brand-teal-hover hover:shadow-lg"
            to="/login"
          >
            Comenzar ahora
          </reactRouterDomModule.Link>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <h2 className="mb-10 text-center text-2xl font-bold text-brand-ink md:text-3xl">
          Todo lo que necesitas para tu practica
        </h2>
        <div className="grid gap-6 md:grid-cols-3">
          <FeatureCard
            description="Tus pacientes agendan directamente por WhatsApp. El asistente verifica disponibilidad en tu calendario y confirma la cita automaticamente."
            icon="📅"
            title="Agendamiento inteligente"
          />
          <FeatureCard
            description="Historial de conversaciones, datos de contacto y seguimiento de cada paciente en un solo lugar, integrado con tu flujo de trabajo."
            icon="👥"
            title="Gestion de pacientes"
          />
          <FeatureCard
            description="Claudia responde consultas frecuentes, envia recordatorios y mantiene la comunicacion activa incluso fuera de tu horario de atencion."
            icon="💬"
            title="Respuestas 24/7"
          />
        </div>
      </section>

      {/* CTA */}
      <section className="bg-brand-teal py-16">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-2xl font-bold text-white md:text-3xl">
            Empieza a transformar tu consultorio hoy
          </h2>
          <p className="mt-4 text-base text-teal-100">
            Conecta tu WhatsApp Business y deja que Claudia se encargue del resto.
          </p>
          <reactRouterDomModule.Link
            className="mt-8 inline-block rounded-xl bg-white px-8 py-3.5 text-base font-semibold text-brand-teal shadow-md transition hover:bg-slate-50 hover:shadow-lg"
            to="/login"
          >
            Iniciar sesion
          </reactRouterDomModule.Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border-subtle bg-white py-8">
        <div className="mx-auto max-w-6xl px-6 text-center text-sm text-slate-500">
          <p>Claudia Agent — Asistente WhatsApp para profesionales de salud mental</p>
          <p className="mt-2">
            <reactRouterDomModule.Link
              className="underline hover:text-brand-teal"
              to="/privacy-policy.html"
            >
              Politica de privacidad
            </reactRouterDomModule.Link>
          </p>
        </div>
      </footer>
    </div>
  );
}

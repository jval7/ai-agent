import * as landingPageModule from "@adapters/inbound/react/pages/LandingPage";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RoadmapCardProps {
  icon: string;
  title: string;
  description: string;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function BuildingCard({ icon, title, description }: RoadmapCardProps) {
  return (
    <div className="rounded-2xl border border-brand-teal/30 bg-white p-5 shadow-card">
      <span className="mb-3 block text-3xl">{icon}</span>
      <h3 className="mb-1.5 text-base font-bold text-brand-ink">{title}</h3>
      <p className="mb-3 text-sm leading-relaxed text-slate-500">{description}</p>
      <span className="inline-block rounded-full bg-brand-teal/10 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide text-brand-teal">
        En construcción
      </span>
    </div>
  );
}

function SoonCard({ icon, title, description }: RoadmapCardProps) {
  return (
    <div className="rounded-2xl border border-amber-200 bg-white p-5 shadow-card">
      <span className="mb-3 block text-3xl">{icon}</span>
      <h3 className="mb-1.5 text-base font-bold text-brand-ink">{title}</h3>
      <p className="mb-3 text-sm leading-relaxed text-slate-500">{description}</p>
      <span className="inline-block rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide text-amber-700">
        Próximamente
      </span>
    </div>
  );
}

function ResearchCard({ icon, title, description }: RoadmapCardProps) {
  return (
    <div className="rounded-2xl border border-border-subtle bg-white p-5 shadow-card">
      <span className="mb-3 block text-3xl">{icon}</span>
      <h3 className="mb-1.5 text-base font-bold text-brand-ink">{title}</h3>
      <p className="mb-3 text-sm leading-relaxed text-slate-500">{description}</p>
      <span className="inline-block rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide text-slate-600">
        En investigación
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function RoadmapPage() {
  const buildingItems: RoadmapCardProps[] = [
    {
      icon: "🏷️",
      title: "Etiquetas inteligentes",
      description:
        "Clasificá pacientes automáticamente por tipo de consulta, estado de pago o historial de asistencia."
    },
    {
      icon: "📝",
      title: "Plantillas de WhatsApp custom",
      description:
        "Creá y editá tus propias plantillas aprobadas por Meta desde la app, sin pasar por soporte."
    },
    {
      icon: "⚙️",
      title: "System prompt editable desde la app",
      description:
        "Personalizá el tono, las instrucciones y los límites de tu IA directamente desde el panel, sin código."
    }
  ];

  const soonItems: RoadmapCardProps[] = [
    {
      icon: "🔌",
      title: "Integraciones (Zapier, Sheets)",
      description:
        "Conectá Agendachat con tus otras herramientas. Enviá datos de citas a Google Sheets o disparar flujos en Zapier."
    },
    {
      icon: "📊",
      title: "Reportes y métricas",
      description:
        "Dashboards con tasas de asistencia, conversaciones por mes, ingresos estimados y más."
    },
    {
      icon: "💳",
      title: "Pagos integrados",
      description: "Cobrar dentro de la misma conversación de WhatsApp, sin salir del chat."
    },
    {
      icon: "📅",
      title: "Multi-agenda mejorada",
      description:
        "Soporte avanzado para consultorios con varias especialidades y horarios independientes."
    }
  ];

  const researchItems: RoadmapCardProps[] = [
    {
      icon: "📩",
      title: "Multi-canal (Instagram DM)",
      description:
        "Extender el asistente IA a mensajes directos de Instagram para captar pacientes desde más canales."
    },
    {
      icon: "🧠",
      title: "Análisis de sentimiento",
      description:
        "Detectar pacientes insatisfechos o confundidos en tiempo real y alertar al profesional."
    },
    {
      icon: "💬",
      title: "Sugerencias de mensajes",
      description:
        "En modo manual, la IA sugiere respuestas basadas en el contexto del paciente para agilizar la atención."
    }
  ];

  return (
    <div className="min-h-screen bg-brand-surface font-sans antialiased">
      <landingPageModule.Navbar />

      {/* Hero pequeño */}
      <section className="border-b border-border-subtle bg-white py-14 md:py-20">
        <div className="mx-auto max-w-3xl px-4 text-center">
          <span className="inline-block rounded-full border border-brand-accent-light bg-brand-surface px-3 py-1 text-xs font-bold uppercase tracking-widest text-brand-teal">
            Transparencia total
          </span>
          <h1 className="mb-4 mt-4 text-3xl font-extrabold leading-tight tracking-tight text-brand-ink md:text-4xl">
            Roadmap de Agendachat
          </h1>
          <p className="text-lg leading-relaxed text-slate-500">
            Lo que estamos construyendo, en orden de prioridad.{" "}
            <strong className="text-brand-ink">Tu feedback ayuda a moverlas.</strong>
          </p>
        </div>
      </section>

      {/* En construcción */}
      <section className="border-b border-border-subtle bg-white py-12 md:py-16">
        <div className="mx-auto max-w-6xl px-4">
          <div className="mb-8 flex items-center gap-3">
            <span className="text-2xl">🚧</span>
            <div>
              <h2 className="text-xl font-bold text-brand-ink">En construcción</h2>
              <p className="text-sm text-slate-500">Activamente en desarrollo — llegan pronto.</p>
            </div>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 md:grid-cols-3">
            {buildingItems.map((item) => (
              <BuildingCard key={item.title} {...item} />
            ))}
          </div>
        </div>
      </section>

      {/* Próximamente */}
      <section className="border-b border-border-subtle bg-brand-surface py-12 md:py-16">
        <div className="mx-auto max-w-6xl px-4">
          <div className="mb-8 flex items-center gap-3">
            <span className="text-2xl">🔜</span>
            <div>
              <h2 className="text-xl font-bold text-brand-ink">Próximamente</h2>
              <p className="text-sm text-slate-500">
                Prioridades claras, diseño en proceso o esperando demanda.
              </p>
            </div>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 md:grid-cols-4">
            {soonItems.map((item) => (
              <SoonCard key={item.title} {...item} />
            ))}
          </div>
        </div>
      </section>

      {/* En investigación */}
      <section className="border-b border-border-subtle bg-white py-12 md:py-16">
        <div className="mx-auto max-w-6xl px-4">
          <div className="mb-8 flex items-center gap-3">
            <span className="text-2xl">🔬</span>
            <div>
              <h2 className="text-xl font-bold text-brand-ink">En investigación</h2>
              <p className="text-sm text-slate-500">
                Ideas que validamos con usuarios antes de comprometer desarrollo.
              </p>
            </div>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 md:grid-cols-3">
            {researchItems.map((item) => (
              <ResearchCard key={item.title} {...item} />
            ))}
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="bg-brand-surface py-14">
        <div className="mx-auto max-w-2xl px-4 text-center">
          <p className="mb-4 text-lg font-semibold text-brand-ink">
            ¿Necesitás algo que no está acá?
          </p>
          <p className="mb-6 text-slate-500">
            Escribinos y lo evaluamos. Las funciones más pedidas suben en prioridad.
          </p>
          <a
            className="inline-flex items-center gap-2 rounded-full bg-brand-teal px-6 py-3 text-base font-bold text-white shadow-md transition hover:bg-brand-teal-hover"
            href="/#empezar"
          >
            Sugerí una funcionalidad →
          </a>
        </div>
      </section>

      <landingPageModule.Footer />
    </div>
  );
}

import { useState } from "react";
import * as reactRouterDomModule from "react-router-dom";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LeadFormState {
  nombre: string;
  profesion: string;
  whatsapp: string;
  citasSemana: string;
}

// ---------------------------------------------------------------------------
// Navbar
// ---------------------------------------------------------------------------

export function Navbar() {
  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <nav className="fixed top-0 z-50 h-16 w-full border-b border-gray-200/50 bg-[#F8F9FA]/80 shadow-sm backdrop-blur-md">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-6">
        {/* Logo + links */}
        <div className="flex items-center gap-8">
          <a className="font-display text-xl font-bold tracking-tight text-brand-teal" href="#">
            Agendachat
          </a>
          <div className="hidden items-center gap-6 md:flex">
            <a
              className="text-sm font-semibold text-slate-600 transition-colors hover:text-brand-teal"
              href="#como-funciona"
              onClick={(e) => {
                e.preventDefault();
                scrollTo("como-funciona");
              }}
            >
              Cómo funciona
            </a>
            <a
              className="text-sm font-semibold text-slate-600 transition-colors hover:text-brand-teal"
              href="#precios"
              onClick={(e) => {
                e.preventDefault();
                scrollTo("precios");
              }}
            >
              Precios
            </a>
            <a
              className="text-sm font-semibold text-slate-600 transition-colors hover:text-brand-teal"
              href="#comparativa"
              onClick={(e) => {
                e.preventDefault();
                scrollTo("comparativa");
              }}
            >
              Comparativa
            </a>
            <a
              className="text-sm font-semibold text-slate-600 transition-colors hover:text-brand-teal"
              href="#roadmap"
              onClick={(e) => {
                e.preventDefault();
                scrollTo("roadmap");
              }}
            >
              Roadmap
            </a>
            <a
              className="text-sm font-semibold text-slate-600 transition-colors hover:text-brand-teal"
              href="#faq"
              onClick={(e) => {
                e.preventDefault();
                scrollTo("faq");
              }}
            >
              FAQ
            </a>
          </div>
        </div>

        {/* CTA */}
        <reactRouterDomModule.Link
          className="rounded-lg bg-brand-teal px-5 py-2 text-sm font-semibold text-white transition hover:opacity-90 active:scale-95"
          to="/login"
        >
          Comenzar ahora
        </reactRouterDomModule.Link>
      </div>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

function WhatsAppChatMockup() {
  return (
    <div className="z-20 w-full max-w-[320px] self-start overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
      {/* Header */}
      <div className="flex items-center gap-3 bg-[#075e54] p-3 text-white">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/20">
          <span className="material-symbols-outlined text-sm">person</span>
        </div>
        <div>
          <p className="text-xs font-bold">Asistente Dr. García</p>
          <p className="text-[10px] opacity-80">En línea</p>
        </div>
      </div>
      {/* Messages */}
      <div
        className="flex min-h-[320px] flex-col space-y-3 p-4"
        style={{
          backgroundColor: "#e5ddd5",
          backgroundImage: "linear-gradient(to bottom, rgba(0, 109, 119, 0.18), transparent 70%)"
        }}
      >
        <div className="self-end max-w-[80%] rounded-lg bg-[#dcf8c6] p-2 text-[11px] shadow-sm">
          Hola, quiero agendar una cita
        </div>
        <div className="self-start max-w-[80%] whitespace-pre-line rounded-lg bg-white p-2 text-[11px] shadow-sm">
          ¡Hola! 😊 Soy la asistente del Dr. García. ¿Me dices tu nombre por favor?
        </div>
        <div className="self-end max-w-[80%] rounded-lg bg-[#dcf8c6] p-2 text-[11px] shadow-sm">
          María Pérez
        </div>
        <div className="self-start max-w-[80%] whitespace-pre-line rounded-lg bg-white p-2 text-[11px] shadow-sm">
          {`¡Mucho gusto, María! 📅 Esta semana tengo disponible:\n🕒 Martes 3:00 pm\n🕒 Miércoles 10:00 am\n🕒 Jueves 5:00 pm\n¿Cuál prefieres?`}
        </div>
        <div className="self-end max-w-[80%] rounded-lg bg-[#dcf8c6] p-2 text-[11px] shadow-sm">
          Miércoles 10am
        </div>
        <div className="self-start max-w-[80%] whitespace-pre-line rounded-lg bg-white p-2 text-[11px] shadow-sm">
          {`¡Perfecto! ✅ Tu cita quedó agendada:\n📅 Miércoles 10:00 am\n👨‍⚕️ Dr. García\n📍 Consultorio principal\nTe envío un recordatorio el martes 🔔`}
        </div>
      </div>
    </div>
  );
}

function CalendarMockup() {
  return (
    <div className="z-30 w-full max-w-[280px] self-end rounded-xl border border-border-subtle bg-white/70 p-4 shadow-xl backdrop-blur-sm lg:-mt-16">
      <div className="mb-4 flex items-center justify-between">
        <h4 className="flex items-center gap-2 text-xs font-bold uppercase text-gray-500">
          TU AGENDA ESTA SEMANA{" "}
          <span className="material-symbols-outlined text-sm text-gray-400">calendar_month</span>
        </h4>
      </div>
      <div className="space-y-2">
        {/* row 1 */}
        <div className="flex items-center gap-3 rounded border-l-2 border-gray-200 bg-gray-100/50 p-2">
          <span className="text-[10px] text-gray-500">Lun 9am · Bloqueo administrativo</span>
        </div>
        {/* row 2 */}
        <div className="flex items-center gap-3 rounded border-l-2 border-gray-200 bg-white p-2">
          <span className="text-[10px] text-gray-600">Mar 3pm · Laura M.</span>
        </div>
        {/* row 3 — highlighted */}
        <div className="flex flex-col gap-1 rounded border-l-4 border-[#008080] bg-[#f0fdfa] p-2 shadow-sm ring-1 ring-[#008080]/10">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-[#004d40]">Mié 10am · María Pérez</span>
            <span className="rounded-full bg-[#008080] px-1.5 py-0.5 text-[8px] font-bold text-white">
              NUEVA
            </span>
          </div>
        </div>
        {/* row 4 */}
        <div className="flex items-center gap-3 rounded border-l-2 border-gray-200 bg-white p-2">
          <span className="text-[10px] text-gray-600">Jue 5pm · Pedro G.</span>
        </div>
        {/* row 5 */}
        <div className="flex items-center gap-3 rounded border-l-2 border-gray-200 bg-white p-2">
          <span className="text-[10px] text-gray-600">Vie 11am · Ana T.</span>
        </div>
      </div>
    </div>
  );
}

function NotificationToast() {
  return (
    <div className="z-30 mt-4 w-full max-w-[280px] self-end animate-bounce rounded-lg border border-brand-teal/20 bg-white/90 p-3 shadow-lg backdrop-blur-md">
      <p className="flex items-center gap-2 text-[10px] font-medium text-brand-ink">
        <span className="material-symbols-outlined text-sm text-brand-teal">notifications</span>
        Tu IA agendó: María Pérez — Miércoles 10:00 am
      </p>
    </div>
  );
}

function Hero() {
  function scrollToSection(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <header className="overflow-hidden px-6 pb-20 pt-32">
      <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-16 lg:grid-cols-2">
        {/* Copy */}
        <div className="space-y-8">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full bg-brand-accent-light/30 px-3 py-1 font-sans text-xs font-semibold uppercase tracking-wider text-brand-teal">
            <span className="material-symbols-outlined text-sm">smart_toy</span>
            La evolución del agendamiento
          </div>

          {/* H1 */}
          <h1 className="font-display text-5xl font-bold leading-tight tracking-tight text-brand-ink lg:text-6xl">
            Tu IA secretaria que agenda citas por{" "}
            <span className="text-brand-teal">WhatsApp 24/7</span>
          </h1>

          {/* Subtitle — 2 paragraphs */}
          <div className="max-w-xl space-y-4">
            <p className="font-display text-xl font-semibold text-brand-teal">
              Agendachat automatiza lo operativo. Tú decides lo que requiere criterio.
            </p>
            <p className="text-base text-slate-500">
              Ideal para profesionales de la salud, estética, fitness y servicios afines que quieren
              automatizar su agendamiento sin perder el control.
            </p>
          </div>

          {/* CTAs */}
          <div className="flex flex-col gap-4 sm:flex-row">
            <a
              className="cursor-pointer rounded-xl bg-brand-teal px-8 py-4 font-display text-lg font-semibold text-white shadow-md transition hover:shadow-lg active:scale-95"
              href="#cliente-fundador"
              onClick={(e) => {
                e.preventDefault();
                scrollToSection("cliente-fundador");
              }}
            >
              Ser Cliente Fundador →
            </a>
            <a
              className="cursor-pointer rounded-xl border-2 border-brand-teal px-8 py-4 font-display text-lg font-semibold text-brand-teal transition hover:bg-brand-teal/5"
              href="#como-funciona"
              onClick={(e) => {
                e.preventDefault();
                scrollToSection("como-funciona");
              }}
            >
              Ver cómo funciona
            </a>
          </div>
        </div>

        {/* Mockup — WhatsApp + Calendar stacked */}
        <div className="relative">
          <div className="absolute inset-0 -z-10 rounded-full bg-gradient-to-tr from-brand-teal/5 to-brand-accent-light/10 blur-3xl" />
          <div className="flex flex-col items-center gap-6">
            <WhatsAppChatMockup />
            <CalendarMockup />
            <NotificationToast />
          </div>
        </div>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Features (3 cards)
// ---------------------------------------------------------------------------

interface FeatureCardProps {
  icon: string;
  title: string;
  subtitle: string;
  bullets: string[];
  accentClass: string;
}

function FeatureCard({ icon, title, subtitle, bullets, accentClass }: FeatureCardProps) {
  return (
    <div className="group rounded-2xl border border-border-subtle bg-white p-8 transition-shadow hover:shadow-xl">
      <div
        className={`mb-6 flex h-12 w-12 items-center justify-center rounded-xl transition-colors ${accentClass}`}
      >
        <span className="material-symbols-outlined">{icon}</span>
      </div>
      <h3 className="mb-3 font-display text-xl font-semibold text-brand-ink">{title}</h3>
      <div className="text-sm text-slate-500">
        <p className="mb-4">{subtitle}</p>
        <ul className="space-y-2">
          {bullets.map((b) => (
            <li className="flex items-start gap-2 text-brand-ink" key={b}>
              <span className="material-symbols-outlined text-lg text-brand-teal">
                check_circle
              </span>
              {b}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function FeaturesSection() {
  return (
    <section className="bg-surface-low px-6 py-20">
      <div className="mx-auto max-w-7xl">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
          <FeatureCard
            accentClass="bg-brand-teal/10 text-brand-teal group-hover:bg-brand-teal group-hover:text-white"
            bullets={[
              "Precios, horarios y servicios respondidos al instante",
              "Dudas genéricas resueltas sin tu intervención",
              "Solo te llegan los casos que necesitan tu criterio"
            ]}
            icon="filter_alt"
            subtitle="Tu IA filtra el ruido y atiende lo repetitivo."
            title="Responde solo lo importante"
          />
          <FeatureCard
            accentClass="bg-brand-accent-light/20 text-brand-teal group-hover:bg-brand-accent-light group-hover:text-brand-teal"
            bullets={[
              "Motivo de consulta capturado por la IA",
              "Modalidad presencial o virtual confirmada",
              "Datos clave del paciente",
              "Tú decides: confirmas, ajustas o rechazas"
            ]}
            icon="info"
            subtitle="Llegas a cada cita con todo el contexto que necesitas."
            title="Información completa antes de agendar"
          />
          <FeatureCard
            accentClass="bg-amber-50 text-amber-700 group-hover:bg-amber-100 group-hover:text-amber-800"
            bullets={[
              "Recordatorios por WhatsApp el día anterior",
              "Reprogramación automática cuando el paciente cambia",
              "Confirmación de asistencia sin que tú preguntes"
            ]}
            icon="event_repeat"
            subtitle="Menos inasistencias, menos coordinación manual."
            title="Recordatorios y reprogramación automática"
          />
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Cómo Funciona
// ---------------------------------------------------------------------------

interface StepProps {
  number: string;
  title: string;
  description: string;
}

function Step({ number, title, description }: StepProps) {
  return (
    <div className="relative flex items-start gap-8">
      <div className="z-10 flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-teal text-2xl font-bold text-white shadow-lg">
        {number}
      </div>
      <div className="flex-grow rounded-2xl border border-border-subtle bg-white p-8 shadow-sm transition-shadow hover:shadow-md">
        <h4 className="mb-4 font-display text-2xl font-semibold text-brand-teal">{title}</h4>
        <p className="text-base text-slate-500">{description}</p>
      </div>
    </div>
  );
}

function HowItWorks() {
  return (
    <section className="px-6 py-20" id="como-funciona">
      <div className="mx-auto max-w-4xl text-center">
        <h2 className="mb-4 font-display text-4xl font-bold text-brand-ink">
          Un flujo diseñado para tu paz mental
        </h2>
        <p className="mb-16 text-slate-500">Simple, directo y sin complicaciones técnicas.</p>
      </div>
      <div className="relative mx-auto max-w-4xl space-y-12">
        {/* Vertical line */}
        <div className="absolute bottom-4 left-[27px] top-4 w-0.5 bg-brand-teal/20" />
        <Step
          description="Levanta información, propone horarios y cierra la cita. Tú decides con criterio."
          number="1"
          title="El paciente pregunta"
        />
        <Step
          description="Cita confirmada en tu Google Calendar, con todos los detalles listos."
          number="2"
          title="La IA negocia"
        />
        <Step
          description="Recibes la cita confirmada directamente en tu Google Calendar, con link de Google Meet generado automáticamente para sesiones virtuales y todos los detalles del paciente al instante."
          number="3"
          title="Tú solo atiendes"
        />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Pricing
// ---------------------------------------------------------------------------

interface PricingFeatureItem {
  text: string;
  icon?: "check_circle" | "stars";
}

interface PricingCardV16Props {
  name: string;
  description: string;
  price: string;
  copPrice: string | null;
  features: PricingFeatureItem[];
  ctaLabel: string;
  highlighted?: boolean;
  ctaAction: "login" | "scroll-empezar";
}

function PricingCardV16({
  name,
  description,
  price,
  copPrice,
  features,
  ctaLabel,
  highlighted,
  ctaAction
}: PricingCardV16Props) {
  const cardBase = highlighted
    ? "relative z-10 flex flex-col rounded-2xl border-2 border-brand-teal bg-white p-8 shadow-2xl md:scale-[1.03]"
    : "flex flex-col rounded-2xl border border-border-subtle bg-white p-8 shadow-sm";

  function handleCta(e: React.MouseEvent) {
    if (ctaAction === "scroll-empezar") {
      e.preventDefault();
      document.getElementById("empezar")?.scrollIntoView({ behavior: "smooth" });
    }
  }

  return (
    <div className={cardBase}>
      {highlighted && (
        <div className="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-brand-teal px-4 py-1 text-xs font-bold uppercase tracking-wide text-white">
          MÁS ELEGIDO
        </div>
      )}

      <h3 className="mb-2 font-display text-xl font-semibold text-brand-ink">{name}</h3>
      <p className="mb-6 text-sm text-slate-500">{description}</p>

      <div className="mb-1">
        <span className="font-display text-4xl font-bold text-brand-ink">{price}</span>
        {price !== "Hablemos" && <span className="text-slate-500">/mes</span>}
      </div>
      {copPrice && <p className="mb-6 text-[11px] text-gray-500">{copPrice}</p>}
      {!copPrice && <div className="mb-6" />}

      <ul className="mb-8 flex-grow space-y-4">
        {features.map((f) => (
          <li className="flex items-center gap-2 text-sm text-slate-500" key={f.text}>
            <span className="material-symbols-outlined text-lg text-brand-teal">
              {f.icon ?? "check_circle"}
            </span>
            {f.text}
          </li>
        ))}
      </ul>

      {ctaAction === "login" ? (
        <reactRouterDomModule.Link
          className={
            highlighted
              ? "block w-full rounded-xl bg-brand-teal py-3 text-center font-semibold text-white transition hover:opacity-90"
              : "block w-full rounded-xl border-2 border-brand-teal py-3 text-center font-semibold text-brand-teal transition hover:bg-brand-teal/5"
          }
          to="/login"
        >
          {ctaLabel}
        </reactRouterDomModule.Link>
      ) : (
        <a
          className="block w-full rounded-xl border-2 border-brand-teal py-3 text-center font-semibold text-brand-teal transition hover:bg-brand-teal/5"
          href="#empezar"
          onClick={handleCta}
        >
          {ctaLabel}
        </a>
      )}
    </div>
  );
}

function Pricing() {
  const starterFeatures: PricingFeatureItem[] = [
    { text: "Hasta 50 conversaciones IA por mes" },
    { text: "CRM de pacientes" },
    { text: "Agendamiento manual desde el panel" }
  ];

  const proFeatures: PricingFeatureItem[] = [
    { text: "Todo lo de Starter, más:", icon: "stars" },
    { text: "Hasta 250 conversaciones IA por mes" },
    { text: "Recordatorios automáticos por WhatsApp" },
    { text: "Módulo de finanzas (registro de pagos por cita)" }
  ];

  const customFeatures: PricingFeatureItem[] = [
    { text: "Todo lo de Pro, más:" },
    { text: "Conversaciones IA a medida" },
    { text: "Varios profesionales en una cuenta" },
    { text: "Onboarding 1-a-1 con setup personalizado" },
    { text: "Integraciones a medida (API)" },
    { text: "Soporte prioritario" },
    { text: "Account manager dedicado" }
  ];

  return (
    <section className="bg-surface-container px-6 py-20" id="precios">
      <div className="mx-auto max-w-7xl">
        <div className="mb-16 text-center">
          <h2 className="mb-4 font-display text-4xl font-bold text-brand-ink">
            Planes para cada etapa
          </h2>
          <p className="text-slate-500">Sin costos de configuración. Cancela cuando quieras.</p>
        </div>

        <div className="grid grid-cols-1 items-stretch gap-8 md:grid-cols-3">
          <PricingCardV16
            copPrice={null}
            ctaAction="login"
            ctaLabel="Empezar"
            description="Para profesionales con volumen moderado de citas."
            features={starterFeatures}
            name="Starter"
            price="$150.000 COP"
          />
          <PricingCardV16
            copPrice={null}
            ctaAction="login"
            ctaLabel="Empezar Pro"
            description="Para profesionales con agenda llena o colapsada."
            features={proFeatures}
            highlighted
            name="Pro"
            price="$240.000 COP"
          />
          <PricingCardV16
            copPrice={null}
            ctaAction="scroll-empezar"
            ctaLabel="Hablemos"
            description="Para clínicas, equipos y casos con necesidades específicas."
            features={customFeatures}
            name="Personalizado"
            price="Hablemos"
          />
        </div>

        <p className="mt-12 text-center text-sm font-medium text-slate-500">
          Todos los planes incluyen soporte por WhatsApp y configuración inicial sin costo.
        </p>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Cliente Fundador Banner
// ---------------------------------------------------------------------------

function ClienteFundadorBanner() {
  return (
    <section className="px-6 py-12">
      <div className="mx-auto max-w-7xl">
        <div
          className="flex flex-col items-center justify-between gap-8 rounded-3xl border-2 border-brand-accent-light bg-brand-accent-light/20 p-8 text-center md:flex-row md:p-12 md:text-left"
          id="cliente-fundador"
        >
          <div className="max-w-2xl">
            <h3 className="mb-4 font-display text-2xl font-bold text-brand-teal md:text-3xl">
              🎁 Precio especial por ser Cliente Fundador
            </h3>
            <p className="text-base text-slate-600">
              Recibe 15 días gratis. Solo los primeros 30 profesionales obtienen el plan Pro a{" "}
              <s className="text-gray-400">$240.000 COP</s> →{" "}
              <strong className="text-brand-teal">$120.000 COP</strong> por mes.
            </p>
          </div>
          <reactRouterDomModule.Link
            className="whitespace-nowrap rounded-xl bg-brand-teal px-8 py-4 font-bold text-white shadow-md transition hover:shadow-lg active:scale-95"
            to="/login"
          >
            Quiero ser Cliente Fundador
          </reactRouterDomModule.Link>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Comparativa
// ---------------------------------------------------------------------------

interface CompareCell {
  text: string;
  note?: string;
  type: "check" | "partial" | "cancel" | "text";
}

interface CompareRowData {
  feature: string;
  agendachat: CompareCell;
  wati: CompareCell;
  agendapro: CompareCell;
  doctoralia: CompareCell;
  respondio: CompareCell;
}

function CompareCellContent({ cell }: { cell: CompareCell }) {
  if (cell.type === "check") {
    return (
      <span
        className="material-symbols-outlined font-bold text-brand-teal"
        style={{ fontVariationSettings: "'FILL' 1" }}
      >
        check_circle
      </span>
    );
  }
  if (cell.type === "cancel") {
    return <span className="material-symbols-outlined text-slate-400">cancel</span>;
  }
  if (cell.type === "partial") {
    return (
      <div className="flex flex-col items-center gap-1">
        <span className="material-symbols-outlined text-slate-400">error</span>
        {cell.note && <span className="text-xs text-slate-400">{cell.note}</span>}
      </div>
    );
  }
  return (
    <span className="font-bold text-brand-teal">
      {cell.text}
      {cell.note && <span className="ml-1 text-xs text-slate-400">{cell.note}</span>}
    </span>
  );
}

function Comparator() {
  const rows: CompareRowData[] = [
    {
      feature: "WhatsApp Business API",
      agendachat: { text: "", type: "check" },
      wati: { text: "", type: "check" },
      agendapro: { text: "", note: "Externo", type: "partial" },
      doctoralia: { text: "", note: "Solo recordatorios", type: "partial" },
      respondio: { text: "", type: "check" }
    },
    {
      feature: "IA que agenda sola 24/7",
      agendachat: { text: "", type: "check" },
      wati: { text: "", type: "cancel" },
      agendapro: { text: "", type: "cancel" },
      doctoralia: { text: "", type: "cancel" },
      respondio: { text: "", note: "desde $159", type: "partial" }
    },
    {
      feature: "Google Calendar bidireccional",
      agendachat: { text: "", type: "check" },
      wati: { text: "", type: "cancel" },
      agendapro: { text: "", note: "Parcial", type: "partial" },
      doctoralia: { text: "", type: "cancel" },
      respondio: { text: "", type: "cancel" }
    },
    {
      feature: "Recordatorios de pago",
      agendachat: { text: "", type: "check" },
      wati: { text: "", type: "cancel" },
      agendapro: { text: "", note: "Parcial", type: "partial" },
      doctoralia: { text: "", type: "cancel" },
      respondio: { text: "", type: "cancel" }
    },
    {
      feature: "CRM de pacientes incluido",
      agendachat: { text: "", type: "check" },
      wati: { text: "", note: "Básico", type: "partial" },
      agendapro: { text: "", type: "check" },
      doctoralia: { text: "", type: "check" },
      respondio: { text: "", note: "Básico", type: "partial" }
    },
    {
      feature: "Precio plan principal",
      agendachat: { text: "$240.000 COP", type: "text" },
      wati: { text: "$49 USD+", type: "text" },
      agendapro: { text: "$40 USD+", type: "text" },
      doctoralia: { text: "No público", type: "text" },
      respondio: { text: "$79 USD+", type: "text" }
    }
  ];

  return (
    <section className="px-6 py-20" id="comparativa">
      <div className="mx-auto max-w-7xl">
        <div className="mb-16 text-center">
          <h2 className="mb-4 font-display text-4xl font-bold text-brand-ink">Por qué elegirnos</h2>
          <p className="text-base text-slate-500">
            Somos los únicos especialistas en agendamiento conversacional para salud.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-left">
            <thead>
              <tr className="border-b border-border-subtle">
                <th className="py-6 font-display text-base font-semibold text-brand-ink">
                  Característica
                </th>
                <th className="rounded-t-xl bg-brand-teal/5 px-6 py-6 text-center font-display text-base font-semibold text-brand-teal">
                  Agendachat
                </th>
                <th className="py-6 text-center text-base font-normal text-gray-400">Wati</th>
                <th className="py-6 text-center text-base font-normal text-gray-400">Agendapro</th>
                <th className="py-6 text-center text-base font-normal text-gray-400">Doctoralia</th>
                <th className="py-6 text-center text-base font-normal text-gray-400">Respond.io</th>
              </tr>
            </thead>
            <tbody className="text-brand-ink">
              {rows.map((row) => (
                <tr className="border-b border-border-subtle" key={row.feature}>
                  <td className="py-6 font-medium">{row.feature}</td>
                  <td className="bg-brand-teal/5 px-6 py-6 text-center">
                    <CompareCellContent cell={row.agendachat} />
                  </td>
                  <td className="py-6 text-center text-slate-400">
                    <CompareCellContent cell={row.wati} />
                  </td>
                  <td className="py-6 text-center text-slate-400">
                    <CompareCellContent cell={row.agendapro} />
                  </td>
                  <td className="py-6 text-center text-slate-400">
                    <CompareCellContent cell={row.doctoralia} />
                  </td>
                  <td className="py-6 text-center text-slate-400">
                    <CompareCellContent cell={row.respondio} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Roadmap
// ---------------------------------------------------------------------------

interface RoadmapItem {
  emoji: string;
  title: string;
  subtitle: string;
}

function RoadmapSection() {
  const items: RoadmapItem[] = [
    { emoji: "📱", subtitle: "Lleva Agendachat contigo donde estés.", title: "App móvil" },
    {
      emoji: "💳",
      subtitle: "Cobra dentro del mismo chat, sin redirigir a otra plataforma.",
      title: "Pagos por WhatsApp"
    },
    {
      emoji: "🏷️",
      subtitle: "Clasifica conversaciones y pacientes automáticamente.",
      title: "Sistema de etiquetas"
    },
    {
      emoji: "🎯",
      subtitle: "Detecta leads valiosos antes que otros.",
      title: "Reconocimiento de clientes potenciales"
    },
    {
      emoji: "📊",
      subtitle:
        "Pacientes, citas por mes, servicios más buscados y recuperación de clientes potenciales.",
      title: "Panel de métricas avanzado"
    }
  ];

  return (
    <section className="bg-white px-6 py-20" id="roadmap">
      <div className="mx-auto max-w-7xl">
        <h2 className="mb-12 text-center font-display text-4xl font-bold text-brand-ink">
          Funcionalidades en camino
        </h2>
        <div className="mx-auto max-w-4xl space-y-4">
          {items.map((item) => (
            <div
              className="flex items-center gap-6 rounded-2xl border border-border-subtle bg-white p-6"
              key={item.title}
            >
              <span className="shrink-0 text-4xl">{item.emoji}</span>
              <div>
                <h4 className="font-display text-lg font-semibold text-brand-ink">{item.title}</h4>
                <p className="text-sm text-slate-500">{item.subtitle}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// FAQ
// ---------------------------------------------------------------------------

interface FaqItem {
  question: string;
  answer: string;
}

function FAQ() {
  const items: FaqItem[] = [
    {
      answer:
        "Es inteligencia artificial de última generación. Entiende modismos, abreviaturas y puede mantener una conversación fluida, no solo responder opciones numéricas.",
      question: "¿Realmente entiende el contexto o es un robot rígido?"
    },
    {
      answer:
        "Cuando la solicitud requiere tu criterio, la IA escala la conversación automáticamente a un agente humano. Tomas el control desde el inbox y respondes directamente.",
      question: "¿Qué pasa si una conversación necesita mi intervención?"
    },
    {
      answer:
        "Cumplimos con estándares internacionales de privacidad. Solo procesamos los datos necesarios para el agendamiento y no compartimos información con terceros.",
      question: "¿Es seguro para los datos de mis pacientes?"
    },
    {
      answer:
        "Sí, a través de nuestra integración oficial con la API de WhatsApp, puedes mantener tu identidad de marca y número actual.",
      question: "¿Puedo usar mi propio número de WhatsApp?"
    }
  ];

  return (
    <section className="px-6 py-20" id="faq">
      <div className="mx-auto max-w-3xl">
        <h2 className="mb-12 text-center font-display text-4xl font-bold text-brand-ink">
          Preguntas Frecuentes
        </h2>
        <div className="space-y-4">
          {items.map((item, i) => (
            <details
              className="group overflow-hidden rounded-2xl border border-border-subtle bg-white"
              key={item.question}
              open={i === 0}
            >
              <summary className="flex cursor-pointer list-none items-center justify-between p-6">
                <span className="font-display text-lg font-semibold text-brand-ink">
                  {item.question}
                </span>
                <span className="material-symbols-outlined text-slate-400 transition-transform group-open:rotate-180">
                  expand_more
                </span>
              </summary>
              <div className="px-6 pb-6 text-base text-slate-500">{item.answer}</div>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Lead Capture Form
// ---------------------------------------------------------------------------

function LeadForm() {
  const [form, setForm] = useState<LeadFormState>({
    citasSemana: "",
    nombre: "",
    profesion: "",
    whatsapp: ""
  });

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // TODO: conectar a webhook real
    console.warn("TODO: hook real form submit", form);
  }

  return (
    <section className="bg-brand-teal px-6 py-20" id="empezar">
      <div className="relative mx-auto max-w-4xl overflow-hidden rounded-3xl p-12 text-center text-white">
        {/* Background grid pattern */}
        <div className="pointer-events-none absolute inset-0 opacity-10">
          <svg height="100%" preserveAspectRatio="none" viewBox="0 0 100 100" width="100%">
            <defs>
              <pattern height="10" id="grid-lf" patternUnits="userSpaceOnUse" width="10">
                <path d="M 10 0 L 0 0 0 10" fill="none" stroke="white" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect fill="url(#grid-lf)" height="100%" width="100%" />
          </svg>
        </div>

        <h2 className="relative mb-6 font-display text-4xl font-bold">
          ¿Estás listo para recuperar tu tiempo?
        </h2>
        <p className="relative mb-10 text-lg text-brand-accent-light">
          Déjanos tus datos y te configuramos todo en 24 horas.
        </p>

        <form
          className="relative mx-auto max-w-md space-y-4 rounded-2xl bg-white p-7 shadow-card-hover"
          onSubmit={handleSubmit}
        >
          {/* Nombre */}
          <div className="text-left">
            <label
              className="mb-1.5 block text-sm font-semibold text-brand-ink"
              htmlFor="lf-nombre"
            >
              Nombre completo
            </label>
            <input
              className="w-full rounded-xl border border-border-subtle px-4 py-3 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-teal"
              id="lf-nombre"
              name="nombre"
              onChange={handleChange}
              placeholder="Tu nombre"
              required
              type="text"
              value={form.nombre}
            />
          </div>

          {/* Profesión */}
          <div className="text-left">
            <label
              className="mb-1.5 block text-sm font-semibold text-brand-ink"
              htmlFor="lf-profesion"
            >
              Profesión
            </label>
            <select
              className="w-full rounded-xl border border-border-subtle bg-white px-4 py-3 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-teal"
              id="lf-profesion"
              name="profesion"
              onChange={handleChange}
              required
              value={form.profesion}
            >
              <option disabled value="">
                Selecciona tu profesión
              </option>
              <option value="Psicólogo/a">Psicólogo/a</option>
              <option value="Médico/a">Médico/a</option>
              <option value="Esteticista">Esteticista</option>
              <option value="Odontólogo/a">Odontólogo/a</option>
              <option value="Entrenador/a personal">Entrenador/a personal</option>
              <option value="Otro">Otro</option>
            </select>
          </div>

          {/* WhatsApp */}
          <div className="text-left">
            <label
              className="mb-1.5 block text-sm font-semibold text-brand-ink"
              htmlFor="lf-whatsapp"
            >
              WhatsApp
            </label>
            <input
              className="w-full rounded-xl border border-border-subtle px-4 py-3 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-teal"
              id="lf-whatsapp"
              name="whatsapp"
              onChange={handleChange}
              placeholder="+57 300 000 0000"
              required
              type="tel"
              value={form.whatsapp}
            />
          </div>

          {/* Citas/semana */}
          <div className="text-left">
            <label className="mb-1.5 block text-sm font-semibold text-brand-ink" htmlFor="lf-citas">
              ¿Cuántas citas atiendes por semana?
            </label>
            <select
              className="w-full rounded-xl border border-border-subtle bg-white px-4 py-3 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-teal"
              id="lf-citas"
              name="citasSemana"
              onChange={handleChange}
              required
              value={form.citasSemana}
            >
              <option disabled value="">
                Selecciona un rango
              </option>
              <option value="0-10">0-10</option>
              <option value="10-30">10-30</option>
              <option value="30-60">30-60</option>
              <option value="60+">60+</option>
            </select>
          </div>

          <button
            className="w-full rounded-full bg-brand-teal py-3 text-base font-bold text-white shadow-md transition hover:bg-brand-teal-hover"
            type="submit"
          >
            Quiero ser Cliente Fundador
          </button>
        </form>

        <p className="relative mt-6 text-xs text-brand-accent-light/70">
          Al unirte aceptas nuestros términos y condiciones.
        </p>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Footer
// ---------------------------------------------------------------------------

export function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-white px-6 py-16">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-12 md:grid-cols-4">
        {/* Brand */}
        <div className="md:col-span-1">
          <a className="font-display text-2xl font-bold text-brand-teal" href="#">
            Agendachat
          </a>
          <p className="mt-4 text-sm leading-relaxed text-slate-500">
            La primera IA secretaria diseñada específicamente para profesionales en Latinoamérica.
          </p>
          <div className="mt-6 flex gap-4">
            <a className="text-gray-400 transition-colors hover:text-brand-teal" href="#">
              <span className="material-symbols-outlined">share</span>
            </a>
            <a className="text-gray-400 transition-colors hover:text-brand-teal" href="#">
              <span className="material-symbols-outlined">public</span>
            </a>
          </div>
        </div>

        {/* Producto */}
        <div>
          <h4 className="mb-6 text-xs font-bold uppercase tracking-widest text-gray-400">
            Producto
          </h4>
          <ul className="space-y-4">
            <li>
              <a
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                href="#como-funciona"
              >
                Cómo funciona
              </a>
            </li>
            <li>
              <a
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                href="#precios"
              >
                Precios
              </a>
            </li>
            <li>
              <a
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                href="#roadmap"
              >
                Roadmap
              </a>
            </li>
            <li>
              <a
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                href="#comparativa"
              >
                Comparativa
              </a>
            </li>
          </ul>
        </div>

        {/* Empresa */}
        <div>
          <h4 className="mb-6 text-xs font-bold uppercase tracking-widest text-gray-400">
            Empresa
          </h4>
          <ul className="space-y-4">
            <li>
              <a
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                href="#"
              >
                Sobre nosotros
              </a>
            </li>
            <li>
              <a
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                href="#"
              >
                Blog
              </a>
            </li>
            <li>
              <a
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                href="#"
              >
                Carreras
              </a>
            </li>
            <li>
              <a
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                href="#"
              >
                Soporte
              </a>
            </li>
          </ul>
        </div>

        {/* Legal */}
        <div>
          <h4 className="mb-6 text-xs font-bold uppercase tracking-widest text-gray-400">Legal</h4>
          <ul className="space-y-4">
            <li>
              <reactRouterDomModule.Link
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                to="/privacy-policy.html"
              >
                Privacidad
              </reactRouterDomModule.Link>
            </li>
            <li>
              <reactRouterDomModule.Link
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                to="/data-deletion.html"
              >
                Eliminación de datos
              </reactRouterDomModule.Link>
            </li>
            <li>
              <a
                className="text-sm text-slate-500 transition-colors hover:text-brand-teal"
                href="#"
              >
                Cookies
              </a>
            </li>
          </ul>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="mx-auto mt-16 flex max-w-7xl flex-col items-center justify-between gap-4 border-t border-gray-100 pt-8 md:flex-row">
        <p className="text-sm text-gray-400">© 2025 Agendachat. La IA que agenda por ti.</p>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 animate-pulse rounded-full bg-brand-teal" />
          <span className="text-xs font-semibold uppercase tracking-tighter text-gray-500">
            Sistemas Operativos
          </span>
        </div>
      </div>
    </footer>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function LandingPage() {
  return (
    <div className="min-h-screen bg-brand-surface font-sans antialiased">
      <Navbar />
      <main>
        <Hero />
        <FeaturesSection />
        <HowItWorks />
        <Pricing />
        <ClienteFundadorBanner />
        <Comparator />
        <RoadmapSection />
        <FAQ />
        <LeadForm />
      </main>
      <Footer />
    </div>
  );
}

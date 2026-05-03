import { useMemo, useState } from "react";
import * as reactRouterDomModule from "react-router-dom";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FeatureCardProps {
  icon: string;
  title: string;
  description: string;
}

interface PricingCardProps {
  tier: string;
  price: string;
  copPrice: string;
  description: string;
  features: { text: string; included: boolean }[];
  ctaLabel: string;
  highlighted?: boolean;
}

interface StepCardProps {
  number: string;
  title: string;
  description: string;
}

interface CompareRow {
  feature: string;
  agendachat: string;
  wati: string;
  agendapro: string;
  respondio: string;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-border-subtle bg-white/95 backdrop-blur shadow-card-sm">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        {/* Logo */}
        <a className="flex shrink-0 items-center gap-2" href="#">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-teal text-sm font-bold text-white select-none">
            A
          </div>
          <span className="text-lg font-bold tracking-tight text-brand-ink">Agendachat</span>
        </a>

        {/* Nav links – hidden on mobile */}
        <nav className="hidden items-center gap-6 text-sm font-medium text-slate-600 md:flex">
          <a className="transition-colors hover:text-brand-teal" href="#como-funciona">
            Cómo funciona
          </a>
          <a className="transition-colors hover:text-brand-teal" href="#pricing">
            Precios
          </a>
          <a className="transition-colors hover:text-brand-teal" href="#comparativa">
            Comparativa
          </a>
          <a className="transition-colors hover:text-brand-teal" href="#faq">
            FAQ
          </a>
        </nav>

        {/* CTA */}
        <reactRouterDomModule.Link
          className="inline-flex shrink-0 items-center gap-1 rounded-full bg-brand-teal px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-teal-hover"
          to="/login"
        >
          Iniciar sesión
        </reactRouterDomModule.Link>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------

function WhatsAppMockup() {
  return (
    <div className="flex justify-center md:justify-end">
      <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-border-subtle bg-[#e5ddd5] shadow-card-hover">
        {/* Chat header */}
        <div className="flex items-center gap-3 bg-brand-teal px-4 py-3 text-white">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20 text-lg">
            🤖
          </div>
          <div>
            <p className="text-sm font-semibold leading-none">Asistente Dr. García</p>
            <p className="mt-0.5 text-xs text-brand-accent-light">en línea</p>
          </div>
        </div>
        {/* Messages */}
        <div className="space-y-2 p-3 text-sm">
          <div className="flex justify-end">
            <div className="max-w-[80%] rounded-tl-2xl rounded-bl-2xl rounded-tr-sm rounded-br-2xl bg-[#dcf8c6] px-3 py-2 text-gray-800 shadow-card-sm">
              Hola, quiero una cita
              <span className="mt-0.5 block text-right text-[10px] text-gray-400">9:14</span>
            </div>
          </div>
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-tl-sm rounded-tr-2xl rounded-bl-2xl rounded-br-2xl bg-white px-3 py-2 text-gray-800 shadow-card-sm">
              ¡Hola! Soy la asistente del Dr. García. ¿Cuál es tu nombre?
              <span className="mt-0.5 block text-right text-[10px] text-gray-400">9:14</span>
            </div>
          </div>
          <div className="flex justify-end">
            <div className="max-w-[80%] rounded-tl-2xl rounded-bl-2xl rounded-tr-sm rounded-br-2xl bg-[#dcf8c6] px-3 py-2 text-gray-800 shadow-card-sm">
              María
              <span className="mt-0.5 block text-right text-[10px] text-gray-400">9:14</span>
            </div>
          </div>
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-tl-sm rounded-tr-2xl rounded-bl-2xl rounded-br-2xl bg-white px-3 py-2 text-gray-800 shadow-card-sm">
              Tengo disponibles:
              <br />
              📅 Martes 3pm
              <br />
              📅 Miércoles 10am
              <br />
              📅 Jueves 5pm
              <br />
              ¿Cuál preferís?
              <span className="mt-0.5 block text-right text-[10px] text-gray-400">9:14</span>
            </div>
          </div>
          <div className="flex justify-end">
            <div className="max-w-[80%] rounded-tl-2xl rounded-bl-2xl rounded-tr-sm rounded-br-2xl bg-[#dcf8c6] px-3 py-2 text-gray-800 shadow-card-sm">
              Miércoles 10am
              <span className="mt-0.5 block text-right text-[10px] text-gray-400">9:15</span>
            </div>
          </div>
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-tl-sm rounded-tr-2xl rounded-bl-2xl rounded-br-2xl bg-white px-3 py-2 text-gray-800 shadow-card-sm">
              ✅ Listo María, agendada miércoles 10am. Te mando recordatorio el martes.
              <span className="mt-0.5 block text-right text-[10px] text-gray-400">9:15</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function Hero() {
  return (
    <section className="border-b border-border-subtle bg-white">
      <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-14 md:grid-cols-2 md:py-20">
        {/* Copy */}
        <div>
          <span className="inline-block rounded-full border border-brand-accent-light bg-brand-surface px-3 py-1 text-xs font-bold uppercase tracking-widest text-brand-teal">
            WhatsApp Business API · IA · Google Calendar
          </span>
          <h1 className="mb-4 mt-4 text-4xl font-extrabold leading-tight tracking-tight text-brand-ink md:text-5xl">
            Tu IA secretaria que agenda citas por WhatsApp{" "}
            <span className="text-brand-teal">24/7</span>
          </h1>
          <p className="mb-8 text-lg leading-relaxed text-slate-500">
            Para psicólogos, médicos y profesionales que pierden citas respondiendo WhatsApp a mano.
            Conectada a tu Google Calendar. Recordatorios de pago automáticos.{" "}
            <strong className="text-brand-ink">Probalo en 2 minutos.</strong>
          </p>
          <div className="flex flex-wrap gap-3">
            <reactRouterDomModule.Link
              className="inline-flex items-center gap-2 rounded-full bg-brand-teal px-6 py-3 text-base font-bold text-white shadow-md transition hover:bg-brand-teal-hover"
              to="/login"
            >
              Quiero probarlo gratis →
            </reactRouterDomModule.Link>
            <a
              className="inline-flex items-center gap-2 rounded-full border border-border-subtle px-6 py-3 text-base font-semibold text-brand-ink transition hover:border-brand-teal hover:text-brand-teal"
              href="#como-funciona"
            >
              Ver cómo funciona
            </a>
          </div>
        </div>

        <WhatsAppMockup />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

function FeatureCard(props: FeatureCardProps) {
  return (
    <div className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
      <div className="mb-3 text-3xl">{props.icon}</div>
      <h3 className="mb-2 text-lg font-bold text-brand-ink">{props.title}</h3>
      <p className="text-sm leading-relaxed text-slate-500">{props.description}</p>
    </div>
  );
}

function WhyAgendachat() {
  return (
    <section className="border-b border-border-subtle bg-brand-surface py-14 md:py-20">
      <div className="mx-auto max-w-6xl px-4">
        <h2 className="mb-10 text-center text-2xl font-bold text-brand-ink md:text-3xl">
          Por qué profesionales eligen Agendachat
        </h2>
        <div className="grid gap-6 md:grid-cols-3">
          <FeatureCard
            description="La IA agenda sola incluso cuando dormís. Tu celular descansa. Tus citas, no."
            icon="📱"
            title="Dejá de responder WhatsApp a las 11pm"
          />
          <FeatureCard
            description="Recordatorios automáticos de pago. Menos inasistencias. Hasta 70% menos citas perdidas."
            icon="💰"
            title="Cobrá antes de la cita"
          />
          <FeatureCard
            description="Conectada a tu Google Calendar real. Sin doble-agendamiento. Sin conflictos de horarios."
            icon="📅"
            title="Que el paciente se agende solo"
          />
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

function StepCard(props: StepCardProps) {
  return (
    <div className="flex flex-col items-start gap-3">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-brand-accent-light bg-brand-surface text-2xl font-extrabold text-brand-teal">
        {props.number}
      </div>
      <h3 className="text-lg font-bold text-brand-ink">{props.title}</h3>
      <p className="text-sm leading-relaxed text-slate-500">{props.description}</p>
    </div>
  );
}

function HowItWorks() {
  return (
    <section className="border-b border-border-subtle bg-white py-14 md:py-20" id="como-funciona">
      <div className="mx-auto max-w-4xl px-4 text-center">
        <h2 className="mb-3 text-2xl font-bold text-brand-ink md:text-3xl">Cómo funciona</h2>
        <p className="mb-12 text-slate-500">
          Tres pasos. Sin código. Sin configuraciones complejas.
        </p>
        <div className="grid gap-8 text-left md:grid-cols-3">
          <StepCard
            description="2 minutos, sin código. Te guiamos en el onboarding paso a paso."
            number="1"
            title="Conectás tu WhatsApp y Google Calendar"
          />
          <StepCard
            description="La IA atiende sola, negocia horarios y agenda. Vos no respondés."
            number="2"
            title="El paciente te escribe normal"
          />
          <StepCard
            description="Recordatorio de asistencia y de pago. Automático. Sin que hagas nada."
            number="3"
            title="La cita queda agendada con recordatorio"
          />
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

function PricingCard(props: PricingCardProps) {
  if (props.highlighted) {
    return (
      <div className="relative scale-[1.03] rounded-2xl bg-brand-teal p-7 shadow-card-hover ring-4 ring-brand-teal/30">
        <span className="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-yellow-400 px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-yellow-900 shadow">
          ⭐ Más elegido
        </span>
        <p className="mb-2 text-xs font-bold uppercase tracking-widest text-brand-accent-light">
          {props.tier}
        </p>
        <p className="mb-1 text-4xl font-extrabold text-white">
          {props.price}
          <span className="text-lg font-semibold text-brand-accent-light">/mes</span>
        </p>
        <p className="mb-6 text-sm text-brand-accent-light">{props.copPrice}</p>
        <p className="mb-5 text-sm font-medium text-brand-accent-light">{props.description}</p>
        <ul className="mb-8 space-y-2.5 text-sm">
          {props.features.map((f) => (
            <li className="flex items-start gap-2 text-white" key={f.text}>
              <span className="mt-0.5">{f.included ? "✅" : "❌"}</span>
              {f.text}
            </li>
          ))}
        </ul>
        <reactRouterDomModule.Link
          className="block rounded-full bg-white py-2.5 text-center text-sm font-bold text-brand-teal shadow-md transition hover:bg-slate-50"
          to="/login"
        >
          {props.ctaLabel}
        </reactRouterDomModule.Link>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border-subtle bg-white p-7 shadow-card">
      <p className="mb-2 text-xs font-bold uppercase tracking-widest text-slate-400">
        {props.tier}
      </p>
      <p className="mb-1 text-4xl font-extrabold text-brand-ink">
        {props.price}
        <span className="text-lg font-semibold text-slate-400">/mes</span>
      </p>
      <p className="mb-6 text-sm text-slate-400">{props.copPrice}</p>
      <p className="mb-5 text-sm font-medium text-slate-600">{props.description}</p>
      <ul className="mb-8 space-y-2.5 text-sm">
        {props.features.map((f) => (
          <li
            className={`flex items-start gap-2 ${f.included ? "text-brand-ink" : "text-slate-400"}`}
            key={f.text}
          >
            <span className={`mt-0.5 ${f.included ? "text-brand-teal" : ""}`}>
              {f.included ? "✅" : "❌"}
            </span>
            {f.text}
          </li>
        ))}
      </ul>
      <reactRouterDomModule.Link
        className="block rounded-full border border-brand-teal py-2.5 text-center text-sm font-semibold text-brand-teal transition hover:bg-brand-surface"
        to="/login"
      >
        {props.ctaLabel}
      </reactRouterDomModule.Link>
    </div>
  );
}

function Pricing() {
  const starterFeatures: { text: string; included: boolean }[] = [
    { text: "Hasta 200 conversaciones IA/mes", included: true },
    { text: "1 número WhatsApp Business", included: true },
    { text: "1 Google Calendar", included: true },
    { text: "Recordatorios básicos", included: true },
    { text: "Recordatorios de pago automáticos", included: false },
    { text: "Plantillas WhatsApp personalizadas", included: false },
    { text: "System prompt editable", included: false }
  ];

  const proFeatures: { text: string; included: boolean }[] = [
    { text: "Conversaciones IA ilimitadas (fair use)", included: true },
    { text: "Recordatorios de pago + asistencia", included: true },
    { text: "Plantillas WhatsApp personalizadas", included: true },
    { text: "Etiquetas y CRM de pacientes", included: true },
    { text: "System prompt editable", included: true },
    { text: "Soporte por WhatsApp", included: true }
  ];

  const clinicFeatures: { text: string; included: boolean }[] = [
    { text: "Todo lo de Pro", included: true },
    { text: "Multi-agenda y multi-usuario", included: true },
    { text: "System prompt avanzado", included: true },
    { text: "Soporte prioritario", included: true }
  ];

  return (
    <section className="border-b border-border-subtle bg-brand-surface py-14 md:py-20" id="pricing">
      <div className="mx-auto max-w-6xl px-4">
        <h2 className="mb-3 text-center text-2xl font-bold text-brand-ink md:text-3xl">
          Precios simples, sin sorpresas
        </h2>
        <p className="mb-12 text-center text-slate-500">
          Cancelás cuando quieras. Sin permanencia.
        </p>

        {/* Cards */}
        <div className="mb-10 grid items-start gap-6 md:grid-cols-3">
          <PricingCard
            copPrice="~$120.000 COP/mes"
            ctaLabel="Empezar →"
            description="Para profesional solo, bajo volumen"
            features={starterFeatures}
            price="$29"
            tier="Starter"
          />
          <PricingCard
            copPrice="~$240.000 COP/mes"
            ctaLabel="Probar 14 días gratis →"
            description="Para profesional con agenda llena"
            features={proFeatures}
            highlighted
            price="$59"
            tier="Pro"
          />
          <PricingCard
            copPrice="~$520.000 COP/mes"
            ctaLabel="Hablar con ventas →"
            description="Para consultorios 2-5 profesionales"
            features={clinicFeatures}
            price="$129"
            tier="Clinic"
          />
        </div>

        {/* Founding Members banner */}
        <div className="mb-8 rounded-2xl border-2 border-yellow-300 bg-gradient-to-r from-yellow-50 to-orange-50 p-6 text-center md:p-8">
          <p className="mb-2 text-2xl">🎁</p>
          <p className="mb-2 text-xs font-bold uppercase tracking-widest text-yellow-700">
            Oferta de lanzamiento — Founding Members
          </p>
          <p className="mb-1 text-2xl font-extrabold text-brand-ink md:text-3xl">
            Pro a <span className="text-brand-teal">$29 USD</span> /{" "}
            <span className="text-brand-teal">$120.000 COP</span>
          </p>
          <p className="mb-2 text-slate-600">
            Precio fijo <strong>de por vida</strong>. Solo los primeros 30 cupos.
          </p>
          <p className="mb-5 text-lg font-bold text-orange-600">
            Quedan <span className="underline">17 lugares</span>.
          </p>
          <reactRouterDomModule.Link
            className="inline-flex items-center gap-2 rounded-full bg-brand-teal px-8 py-3 font-bold text-white shadow-md transition hover:bg-brand-teal-hover"
            to="/login"
          >
            Quiero ser Founding Member →
          </reactRouterDomModule.Link>
        </div>

        {/* Guarantee */}
        <div className="mx-auto flex max-w-2xl items-start gap-4 rounded-2xl border border-border-subtle bg-white p-5">
          <span className="shrink-0 text-2xl">🛡️</span>
          <p className="text-sm leading-relaxed text-slate-600">
            <strong className="text-brand-ink">Garantía 30 días:</strong> si no recuperás el plan
            con 1 cita rescatada por recordatorio, te devolvemos la plata. Sin preguntas.
          </p>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

function Comparator() {
  const rows: CompareRow[] = [
    {
      feature: "WhatsApp Business API oficial",
      agendachat: "✅",
      wati: "✅",
      agendapro: "❌",
      respondio: "✅"
    },
    {
      feature: "IA que agenda sola 24/7",
      agendachat: "✅",
      wati: "❌",
      agendapro: "❌",
      respondio: "✅ (desde $159)"
    },
    {
      feature: "Google Calendar bidireccional",
      agendachat: "✅",
      wati: "❌",
      agendapro: "Parcial",
      respondio: "❌"
    },
    {
      feature: "Recordatorios de pago",
      agendachat: "✅",
      wati: "❌",
      agendapro: "Parcial",
      respondio: "❌"
    },
    {
      feature: "CRM de pacientes incluido",
      agendachat: "✅",
      wati: "✅",
      agendapro: "✅",
      respondio: "✅"
    },
    {
      feature: "Precio plan principal (USD/mes)",
      agendachat: "$59",
      wati: "$69–$149",
      agendapro: "$59",
      respondio: "$159"
    }
  ];

  return (
    <section className="border-b border-border-subtle bg-white py-14 md:py-20" id="comparativa">
      <div className="mx-auto max-w-6xl px-4">
        <h2 className="mb-3 text-center text-2xl font-bold text-brand-ink md:text-3xl">
          Cómo se compara Agendachat
        </h2>
        <p className="mb-10 text-center text-slate-500">
          La única herramienta en LATAM que combina los 4 ejes.
        </p>

        {/* Horizontal scroll on mobile */}
        <div className="overflow-x-auto rounded-2xl border border-border-subtle shadow-card">
          <table className="w-full min-w-[600px] text-sm">
            <thead>
              <tr className="border-b border-border-subtle bg-brand-surface">
                <th className="px-5 py-4 text-left font-semibold text-brand-ink">Feature</th>
                <th className="bg-brand-accent-light/40 px-4 py-4 text-center font-bold text-brand-teal">
                  Agendachat
                </th>
                <th className="px-4 py-4 text-center font-semibold text-slate-600">Wati</th>
                <th className="px-4 py-4 text-center font-semibold text-slate-600">Agendapro</th>
                <th className="px-4 py-4 text-center font-semibold text-slate-600">Respond.io</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {rows.map((row, i) => (
                <tr className={i % 2 !== 0 ? "bg-brand-surface/50" : ""} key={row.feature}>
                  <td
                    className={`px-5 py-3.5 text-slate-700 ${i === rows.length - 1 ? "font-semibold" : ""}`}
                  >
                    {row.feature}
                  </td>
                  <td
                    className={`bg-brand-accent-light/40 px-4 py-3.5 text-center text-lg ${i === rows.length - 1 ? "font-bold text-brand-teal" : ""}`}
                  >
                    {row.agendachat}
                  </td>
                  <td className="px-4 py-3.5 text-center text-lg">{row.wati}</td>
                  <td className="px-4 py-3.5 text-center text-lg">{row.agendapro}</td>
                  <td className="px-4 py-3.5 text-center text-lg">{row.respondio}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-3 text-center text-xs text-slate-400">
          Precios públicos verificados a 2026. Pueden variar. Ver fuentes:{" "}
          <a className="underline" href="https://wati.io/pricing" rel="noopener" target="_blank">
            wati.io/pricing
          </a>
          ,{" "}
          <a className="underline" href="https://respond.io/pricing" rel="noopener" target="_blank">
            respond.io/pricing
          </a>
          , agendapro.co/planes.
        </p>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

function ROICalculator() {
  const [precioCita, setPrecioCita] = useState<number>(100000);
  const [citasCaidas, setCitasCaidas] = useState<number>(5);

  const result = useMemo(() => {
    const perdida = precioCita * citasCaidas;
    const recuperado = perdida * 0.7;
    const costoPlan = 240000;
    const roi = costoPlan > 0 ? recuperado / costoPlan : 0;
    return { perdida, recuperado, costoPlan, roi };
  }, [precioCita, citasCaidas]);

  function formatCOP(n: number): string {
    return "$" + Math.round(n).toLocaleString("es-CO");
  }

  return (
    <section className="border-b border-border-subtle bg-brand-surface py-14 md:py-20" id="roi">
      <div className="mx-auto max-w-2xl px-4">
        <h2 className="mb-3 text-center text-2xl font-bold text-brand-ink md:text-3xl">
          Calculadora de ROI
        </h2>
        <p className="mb-10 text-center text-slate-500">
          ¿Cuánto estás perdiendo cada mes por inasistencias?
        </p>

        <div className="space-y-6 rounded-2xl border border-border-subtle bg-white p-7 shadow-card">
          {/* Precio cita */}
          <div>
            <label
              className="mb-1.5 block text-sm font-semibold text-brand-ink"
              htmlFor="precio-cita"
            >
              ¿Cuánto cobrás por cita? (COP)
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-400">
                $
              </span>
              <input
                className="w-full rounded-xl border border-border-subtle py-3 pl-7 pr-4 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-teal focus:border-transparent"
                id="precio-cita"
                min={0}
                onChange={(e) => setPrecioCita(parseFloat(e.target.value) || 0)}
                step={10000}
                type="number"
                value={precioCita}
              />
            </div>
          </div>

          {/* Citas caidas */}
          <div>
            <label
              className="mb-1.5 block text-sm font-semibold text-brand-ink"
              htmlFor="citas-caidas"
            >
              ¿Cuántas citas se caen al mes por inasistencia?
            </label>
            <input
              className="w-full rounded-xl border border-border-subtle px-4 py-3 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-teal focus:border-transparent"
              id="citas-caidas"
              min={0}
              onChange={(e) => setCitasCaidas(parseFloat(e.target.value) || 0)}
              type="number"
              value={citasCaidas}
            />
          </div>

          {/* Result */}
          <div className="space-y-2 rounded-xl border border-brand-accent-light bg-brand-surface p-5 text-sm">
            <p className="text-slate-700">
              Estás perdiendo <strong className="text-red-600">{formatCOP(result.perdida)}</strong>{" "}
              al mes.
            </p>
            <p className="text-slate-700">
              Agendachat recupera ~70% ={" "}
              <strong className="text-brand-teal">{formatCOP(result.recuperado)}</strong>
            </p>
            <p className="text-slate-700">
              Costo del plan Pro:{" "}
              <strong className="text-brand-ink">{formatCOP(result.costoPlan)}</strong>
            </p>
            <div className="mt-3 border-t border-brand-accent-light pt-3">
              <p className="text-lg font-extrabold text-brand-teal">
                ROI: <span>{result.roi.toFixed(1)}x</span> tu inversión
              </p>
            </div>
          </div>

          <a
            className="block rounded-full bg-brand-teal py-3 text-center text-sm font-bold text-white transition hover:bg-brand-teal-hover"
            href="#pricing"
          >
            Recuperá ese dinero con Agendachat →
          </a>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

function FAQ() {
  return (
    <section className="border-b border-border-subtle bg-white py-14 md:py-20" id="faq">
      <div className="mx-auto max-w-3xl px-4">
        <h2 className="mb-10 text-center text-2xl font-bold text-brand-ink md:text-3xl">
          Preguntas frecuentes
        </h2>

        <div className="space-y-3">
          <details className="group rounded-2xl border border-border-subtle bg-brand-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4 text-sm font-semibold text-brand-ink">
              ¿Necesito tener WhatsApp Business API?
              <span className="text-lg text-brand-teal transition-transform group-open:rotate-45">
                +
              </span>
            </summary>
            <div className="px-6 pb-4 text-sm leading-relaxed text-slate-500">
              Te ayudamos a configurarlo en el onboarding. Si ya tenés WhatsApp Business normal, te
              migramos a la API oficial.
            </div>
          </details>

          <details className="group rounded-2xl border border-border-subtle bg-brand-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4 text-sm font-semibold text-brand-ink">
              ¿Y si la IA se equivoca? ¿Puedo intervenir?
              <span className="text-lg text-brand-teal transition-transform group-open:rotate-45">
                +
              </span>
            </summary>
            <div className="px-6 pb-4 text-sm leading-relaxed text-slate-500">
              Sí. Cada conversación tiene un toggle "modo manual": tomás el control cuando querés y
              la IA se calla.
            </div>
          </details>

          <details className="group rounded-2xl border border-border-subtle bg-brand-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4 text-sm font-semibold text-brand-ink">
              ¿Funciona con mi Google Calendar actual?
              <span className="text-lg text-brand-teal transition-transform group-open:rotate-45">
                +
              </span>
            </summary>
            <div className="px-6 pb-4 text-sm leading-relaxed text-slate-500">
              Sí, conexión directa con cualquier cuenta de Google. Sin apps adicionales.
            </div>
          </details>

          <details className="group rounded-2xl border border-border-subtle bg-brand-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4 text-sm font-semibold text-brand-ink">
              ¿Hay permanencia o contrato?
              <span className="text-lg text-brand-teal transition-transform group-open:rotate-45">
                +
              </span>
            </summary>
            <div className="px-6 pb-4 text-sm leading-relaxed text-slate-500">
              No. Cancelás cuando quieras desde la app. Sin letras chicas.
            </div>
          </details>

          <details className="group rounded-2xl border border-border-subtle bg-brand-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4 text-sm font-semibold text-brand-ink">
              ¿Cuánto cuesta WhatsApp aparte del plan?
              <span className="text-lg text-brand-teal transition-transform group-open:rotate-45">
                +
              </span>
            </summary>
            <div className="px-6 pb-4 text-sm leading-relaxed text-slate-500">
              Meta cobra ~$0.01–0.04 USD por mensaje de utilidad. En el plan Pro incluimos un cupo
              mensual. Arriba de eso facturamos al costo de Meta sin sobreprecio.
            </div>
          </details>

          <details className="group rounded-2xl border border-border-subtle bg-brand-surface">
            <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4 text-sm font-semibold text-brand-ink">
              ¿Es legal en Colombia?
              <span className="text-lg text-brand-teal transition-transform group-open:rotate-45">
                +
              </span>
            </summary>
            <div className="px-6 pb-4 text-sm leading-relaxed text-slate-500">
              Sí, cumplimos Habeas Data (Ley 1581/2012). Ver nuestra{" "}
              <reactRouterDomModule.Link
                className="text-brand-teal underline underline-offset-2"
                to="/privacy-policy.html"
              >
                política de privacidad
              </reactRouterDomModule.Link>
              .
            </div>
          </details>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

interface LeadFormState {
  nombre: string;
  profesion: string;
  whatsapp: string;
  citasSemana: string;
}

function LeadForm() {
  const [form, setForm] = useState<LeadFormState>({
    nombre: "",
    profesion: "",
    whatsapp: "",
    citasSemana: ""
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
    <section className="bg-brand-teal py-14 md:py-20" id="empezar">
      <div className="mx-auto max-w-xl px-4">
        <h2 className="mb-2 text-center text-2xl font-bold text-white md:text-3xl">Empezá hoy</h2>
        <p className="mb-10 text-center text-brand-accent-light">
          Te configuramos todo en 24 horas.
        </p>

        <form
          className="space-y-4 rounded-2xl bg-white p-7 shadow-card-hover"
          onSubmit={handleSubmit}
        >
          {/* Nombre */}
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-brand-ink" htmlFor="nombre">
              Nombre completo
            </label>
            <input
              className="w-full rounded-xl border border-border-subtle px-4 py-3 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-teal focus:border-transparent"
              id="nombre"
              name="nombre"
              onChange={handleChange}
              placeholder="Tu nombre"
              required
              type="text"
              value={form.nombre}
            />
          </div>

          {/* Profesion */}
          <div>
            <label
              className="mb-1.5 block text-sm font-semibold text-brand-ink"
              htmlFor="profesion"
            >
              Profesión
            </label>
            <select
              className="w-full rounded-xl border border-border-subtle bg-white px-4 py-3 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-teal focus:border-transparent"
              id="profesion"
              name="profesion"
              onChange={handleChange}
              required
              value={form.profesion}
            >
              <option disabled value="">
                Seleccioná tu profesión
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
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-brand-ink" htmlFor="whatsapp">
              Tu WhatsApp
            </label>
            <input
              className="w-full rounded-xl border border-border-subtle px-4 py-3 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-teal focus:border-transparent"
              id="whatsapp"
              name="whatsapp"
              onChange={handleChange}
              placeholder="+57 300 000 0000"
              required
              type="tel"
              value={form.whatsapp}
            />
          </div>

          {/* Citas semana */}
          <div>
            <label
              className="mb-1.5 block text-sm font-semibold text-brand-ink"
              htmlFor="citas-semana"
            >
              ¿Cuántas citas atendés por semana?
            </label>
            <select
              className="w-full rounded-xl border border-border-subtle bg-white px-4 py-3 text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-teal focus:border-transparent"
              id="citas-semana"
              name="citasSemana"
              onChange={handleChange}
              required
              value={form.citasSemana}
            >
              <option disabled value="">
                Seleccioná un rango
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
            Quiero probarlo gratis
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-brand-accent-light">
          Acceso directo al fundador. Sin chatbots de soporte.
        </p>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

function Footer() {
  return (
    <footer className="bg-brand-ink py-12 text-slate-400">
      <div className="mx-auto max-w-6xl px-4">
        <div className="mb-10 grid gap-8 sm:grid-cols-2 md:grid-cols-4">
          {/* Brand */}
          <div className="md:col-span-1">
            <div className="mb-3 flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-teal text-sm font-bold text-white">
                A
              </div>
              <span className="text-lg font-bold text-white">Agendachat</span>
            </div>
            <p className="text-sm leading-relaxed text-slate-500">
              Tu IA secretaria que agenda citas por WhatsApp.
            </p>
          </div>

          {/* Producto */}
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-500">
              Producto
            </p>
            <ul className="space-y-2 text-sm">
              <li>
                <a className="transition-colors hover:text-white" href="#como-funciona">
                  Cómo funciona
                </a>
              </li>
              <li>
                <a className="transition-colors hover:text-white" href="#pricing">
                  Precios
                </a>
              </li>
              <li>
                <a className="transition-colors hover:text-white" href="#comparativa">
                  Comparativa
                </a>
              </li>
              <li>
                <a className="transition-colors hover:text-white" href="#roi">
                  Calculadora ROI
                </a>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-500">Legal</p>
            <ul className="space-y-2 text-sm">
              <li>
                <reactRouterDomModule.Link
                  className="transition-colors hover:text-white"
                  to="/privacy-policy.html"
                >
                  Política de privacidad
                </reactRouterDomModule.Link>
              </li>
              <li>
                <reactRouterDomModule.Link
                  className="transition-colors hover:text-white"
                  to="/data-deletion.html"
                >
                  Eliminación de datos
                </reactRouterDomModule.Link>
              </li>
            </ul>
          </div>

          {/* Contacto */}
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-500">
              Contacto
            </p>
            <ul className="space-y-2 text-sm">
              <li>
                <a
                  className="break-all transition-colors hover:text-white"
                  href="mailto:jhonvalderramaa7@gmail.com"
                >
                  jhonvalderramaa7@gmail.com
                </a>
              </li>
              <li>
                <a
                  className="transition-colors hover:text-white"
                  href="https://wa.me/573127457050"
                  rel="noopener"
                  target="_blank"
                >
                  WhatsApp +57 312 745 7050
                </a>
              </li>
              <li className="text-xs text-slate-600">Cali, Colombia</li>
            </ul>
          </div>
        </div>

        <div className="flex flex-col items-center justify-between gap-3 border-t border-slate-800 pt-6 text-xs text-slate-600 sm:flex-row">
          <p>© 2026 Agendachat</p>
          <p>Última actualización: 2026-04-27</p>
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
      <Hero />
      <WhyAgendachat />
      <HowItWorks />
      <Pricing />
      <Comparator />
      <ROICalculator />
      <FAQ />
      <LeadForm />
      <Footer />
    </div>
  );
}

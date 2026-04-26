import * as reactModule from "react";

const META_BILLING_HUB_URL = "https://business.facebook.com/billing_hub/payment_settings";

interface BillingDisclosureModalProps {
  isOpen: boolean;
  onContinue: () => void;
  onCancel: () => void;
}

export function BillingDisclosureModal({
  isOpen,
  onContinue,
  onCancel
}: BillingDisclosureModalProps) {
  reactModule.useEffect(() => {
    if (!isOpen) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCancel();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onCancel]);

  if (!isOpen) {
    return null;
  }

  const handleBackdropClick = (event: reactModule.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onCancel();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="billing-disclosure-title"
    >
      <div className="w-full max-w-lg rounded-2xl border border-border-subtle bg-white shadow-card">
        <div className="border-b border-border-subtle px-6 py-4">
          <h2 className="text-base font-semibold text-brand-ink" id="billing-disclosure-title">
            Antes de activar los recordatorios
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Información importante sobre el costo del servicio y la configuración requerida en Meta.
          </p>
        </div>

        <div className="space-y-5 px-6 py-5 text-sm leading-relaxed text-slate-700">
          <section>
            <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Costos asociados
            </h3>
            <p className="mt-2">
              Meta te cobra cada recordatorio (tarifa <em>UTILITY</em>) directamente a la tarjeta
              configurada en tu cuenta de WhatsApp Business. Nosotros no intermediamos el cobro.
            </p>
          </section>

          <section>
            <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Cómo configurar el método de pago en Meta
            </h3>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-slate-700">
              <li>Abrí Meta Business Manager con la cuenta vinculada a tu WhatsApp Business.</li>
              <li>
                Andá a <span className="font-medium">Configuración</span> →{" "}
                <span className="font-medium">Cuentas de WhatsApp</span> y seleccioná tu cuenta.
              </li>
              <li>
                Entrá a la pestaña <span className="font-medium">Métodos de pago</span> y agregá una
                tarjeta de crédito o débito vigente.
              </li>
              <li>Volvé a esta página y continuá la activación.</li>
            </ol>
          </section>
        </div>

        <div className="flex flex-col gap-2 border-t border-border-subtle px-6 py-4 sm:flex-row sm:justify-between">
          <a
            className="inline-flex items-center justify-center rounded-lg border border-brand-teal px-4 py-2.5 text-sm font-semibold text-brand-teal transition-colors hover:bg-brand-teal/10"
            href={META_BILLING_HUB_URL}
            rel="noopener"
            target="_blank"
          >
            Abrir Meta Business Manager
          </a>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
              onClick={onCancel}
              type="button"
            >
              Cancelar
            </button>
            <button
              className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover"
              onClick={onContinue}
              type="button"
            >
              Ya configuré el método de pago, continuar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

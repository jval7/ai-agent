import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as apiErrorModule from "@shared/http/api_error";

const META_BILLING_HUB_URL = "https://business.facebook.com/billing_hub/payment_settings";
const E164_REGEX = /^\+\d{8,15}$/;

interface BillingPreflightModalProps {
  isOpen: boolean;
  defaultPhoneNumber: string;
  onSuccess: (phoneNumber: string) => void;
  onCancel: () => void;
}

interface PreflightDetail {
  code: string | undefined;
  metaErrorCode: number | null;
  message: string | undefined;
}

function readPreflightDetail(error: unknown): PreflightDetail | null {
  if (!(error instanceof apiErrorModule.ApiError)) {
    return null;
  }
  const detail = error.detail;
  if (detail === null || typeof detail !== "object") {
    return null;
  }
  const detailObject = detail as Record<string, unknown>;
  const codeRaw = detailObject["code"];
  const metaCodeRaw = detailObject["meta_error_code"];
  const messageRaw = detailObject["message"];
  return {
    code: typeof codeRaw === "string" ? codeRaw : undefined,
    metaErrorCode: typeof metaCodeRaw === "number" ? metaCodeRaw : null,
    message: typeof messageRaw === "string" ? messageRaw : undefined
  };
}

export function BillingPreflightModal({
  isOpen,
  defaultPhoneNumber,
  onSuccess,
  onCancel
}: BillingPreflightModalProps) {
  const appContainer = appContainerContextModule.useAppContainer();
  const [phoneNumber, setPhoneNumber] = reactModule.useState(defaultPhoneNumber);

  reactModule.useEffect(() => {
    if (isOpen) {
      setPhoneNumber(defaultPhoneNumber);
    }
  }, [isOpen, defaultPhoneNumber]);

  const preflightMutation = reactQueryModule.useMutation({
    mutationFn: (phone: string) => appContainer.whatsappBillingUseCase.runPreflight(phone),
    onSuccess: (result) => {
      onSuccess(result.recipientPhoneNumber);
    }
  });

  reactModule.useEffect(() => {
    if (!isOpen) {
      preflightMutation.reset();
    }
  }, [isOpen, preflightMutation]);

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

  const trimmedPhone = phoneNumber.trim();
  const isPhoneValid = E164_REGEX.test(trimmedPhone);
  const isLoading = preflightMutation.isPending;
  const detail = readPreflightDetail(preflightMutation.error);
  const isBillingNotConfigured = detail?.code === "WHATSAPP_BILLING_NOT_CONFIGURED";
  const showError = preflightMutation.isError;

  const handleSubmit = () => {
    if (!isPhoneValid || isLoading) {
      return;
    }
    preflightMutation.mutate(trimmedPhone);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="billing-preflight-title"
    >
      <div className="w-full max-w-md rounded-2xl border border-border-subtle bg-white shadow-card">
        <div className="border-b border-border-subtle px-6 py-4">
          <h2 className="text-base font-semibold text-brand-ink" id="billing-preflight-title">
            Verificá tu método de pago
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Vamos a enviar el mensaje de prueba <span className="font-mono">hello_world</span> a tu
            WhatsApp para confirmar que la facturación esté correctamente configurada.
          </p>
        </div>

        <div className="space-y-4 px-6 py-5">
          <div>
            <label
              className="block text-xs font-semibold uppercase tracking-wide text-slate-500"
              htmlFor="preflight-phone"
            >
              Tu número de WhatsApp (formato internacional)
            </label>
            <input
              className="mt-2 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
              id="preflight-phone"
              inputMode="tel"
              onChange={(event) => {
                setPhoneNumber(event.target.value);
              }}
              placeholder="+573001234567"
              type="text"
              value={phoneNumber}
            />
            {trimmedPhone !== "" && !isPhoneValid ? (
              <p className="mt-1 text-xs text-amber-700">
                Ingresá tu número en formato internacional, comenzando con + y sólo dígitos.
              </p>
            ) : null}
          </div>

          {isLoading ? (
            <p className="rounded-lg border border-border-subtle bg-slate-50 px-3 py-2 text-xs text-slate-600">
              Enviando "Hello World" a tu número…
            </p>
          ) : null}

          {showError && isBillingNotConfigured ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
              <p className="text-sm font-medium">
                Aún no detectamos un método de pago activo en tu cuenta de Meta.
              </p>
              <p className="mt-1 text-xs">
                Por favor verificá que la tarjeta esté correctamente vinculada a tu cuenta de
                WhatsApp Business y volvé a intentar.
              </p>
              <a
                className="mt-3 inline-flex items-center rounded-lg border border-amber-700 px-3 py-1.5 text-xs font-semibold text-amber-900 transition-colors hover:bg-amber-100"
                href={META_BILLING_HUB_URL}
                rel="noopener"
                target="_blank"
              >
                Abrir Meta Business Manager
              </a>
              <p className="mt-3 text-[10px] text-slate-500">Código Meta: 131042</p>
            </div>
          ) : null}

          {showError && !isBillingNotConfigured ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
              <p className="text-sm font-medium">
                No pudimos verificar la facturación de WhatsApp en este momento.
              </p>
              <p className="mt-1 text-xs">
                {detail?.message ?? "Volvé a intentarlo en unos minutos."}
              </p>
              {detail?.metaErrorCode !== null && detail?.metaErrorCode !== undefined ? (
                <p className="mt-3 text-[10px] text-slate-500">
                  Código Meta: {detail.metaErrorCode}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="flex justify-end gap-2 border-t border-border-subtle px-6 py-4">
          <button
            className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
            onClick={onCancel}
            type="button"
          >
            Cancelar
          </button>
          <button
            className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
            disabled={!isPhoneValid || isLoading}
            onClick={handleSubmit}
            type="button"
          >
            {isLoading ? "Verificando…" : showError ? "Reintentar" : "Verificar"}
          </button>
        </div>
      </div>
    </div>
  );
}

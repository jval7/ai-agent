import * as reactModule from "react";
import * as reactRouterDomModule from "react-router-dom";
import * as authContextModule from "@adapters/inbound/react/app/AuthContext";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as authSharedModule from "@adapters/inbound/react/components/AuthShared";
import * as uiErrorModule from "@shared/http/ui_error";

const inputClassName =
  "h-12 w-full rounded-xl border border-palette-mist bg-white px-4 text-base text-slate-800 placeholder:text-slate-400 focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 md:h-14 md:text-lg";

export function ForgotPasswordPage() {
  const auth = authContextModule.useAuth();

  const [email, setEmail] = reactModule.useState("");
  const [isSubmitting, setIsSubmitting] = reactModule.useState(false);
  const [errorMessage, setErrorMessage] = reactModule.useState<string | null>(null);
  const [hasSubmittedSuccessfully, setHasSubmittedSuccessfully] = reactModule.useState(false);

  const handleSubmit = async (event: reactModule.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await auth.requestPasswordReset({ email: email.trim() });
      setHasSubmittedSuccessfully(true);
    } catch (error: unknown) {
      const resolvedErrorMessage = uiErrorModule.resolveUiErrorMessage([error]);
      if (resolvedErrorMessage === null) {
        throw error;
      }
      setErrorMessage(resolvedErrorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (hasSubmittedSuccessfully) {
    return (
      <authSharedModule.AuthScreenContainer>
        <authSharedModule.AuthCard
          subtitle="Revisá tu bandeja de entrada"
          title="Reestablecer contraseña"
        >
          <p className="text-center text-base text-slate-600 md:text-xl">
            Si la cuenta existe, te enviamos un link para reestablecer la contraseña. Revisá tu
            bandeja de entrada (y la carpeta de spam).
          </p>
          <p className="mt-8 text-center text-base text-slate-600 md:text-xl">
            <reactRouterDomModule.Link
              className="font-medium text-brand-teal underline hover:text-brand-teal-hover"
              to="/login"
            >
              Volver al inicio de sesión
            </reactRouterDomModule.Link>
          </p>
        </authSharedModule.AuthCard>
      </authSharedModule.AuthScreenContainer>
    );
  }

  return (
    <authSharedModule.AuthScreenContainer>
      <authSharedModule.AuthCard
        subtitle="Te enviaremos un link para crear una nueva"
        title="Reestablecer contraseña"
      >
        <form className="space-y-5" onSubmit={(event) => void handleSubmit(event)}>
          <div>
            <authSharedModule.AuthInputLabel htmlFor="email" text="Correo electrónico" />
            <input
              autoComplete="email"
              className={inputClassName}
              id="email"
              onChange={(event) => {
                setEmail(event.target.value);
              }}
              placeholder="tu@empresa.com"
              required
              type="email"
              value={email}
            />
          </div>

          {errorMessage !== null ? (
            <errorBannerModule.ErrorBanner
              className="rounded-xl bg-red-100 px-3 py-2 text-base font-medium text-red-700 md:text-[18px]"
              message={errorMessage}
            />
          ) : null}

          <button
            className="mt-2 h-12 w-full rounded-xl bg-brand-teal px-4 text-base font-semibold text-white transition hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60 md:h-14 md:text-xl"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? "Enviando..." : "Enviar link"}
          </button>
        </form>

        <p className="mt-8 text-center text-base text-slate-600 md:text-xl">
          <reactRouterDomModule.Link
            className="font-medium text-brand-teal underline hover:text-brand-teal-hover"
            to="/login"
          >
            Volver al inicio de sesión
          </reactRouterDomModule.Link>
        </p>
      </authSharedModule.AuthCard>
    </authSharedModule.AuthScreenContainer>
  );
}

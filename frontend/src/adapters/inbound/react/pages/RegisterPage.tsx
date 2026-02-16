import * as reactModule from "react";
import * as reactRouterDomModule from "react-router-dom";

import * as authContextModule from "@adapters/inbound/react/app/AuthContext";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as authSharedModule from "@adapters/inbound/react/components/AuthShared";
import * as uiErrorModule from "@shared/http/ui_error";

const inputClassName =
  "h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-base text-slate-800 placeholder:text-slate-400 focus:border-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-700/20 md:h-14 md:text-lg";

export function RegisterPage() {
  const auth = authContextModule.useAuth();
  const navigate = reactRouterDomModule.useNavigate();

  const [tenantName, setTenantName] = reactModule.useState("");
  const [email, setEmail] = reactModule.useState("");
  const [password, setPassword] = reactModule.useState("");
  const [passwordConfirmation, setPasswordConfirmation] = reactModule.useState("");
  const [isPasswordVisible, setIsPasswordVisible] = reactModule.useState(false);
  const [isPasswordConfirmationVisible, setIsPasswordConfirmationVisible] =
    reactModule.useState(false);
  const [isSubmitting, setIsSubmitting] = reactModule.useState(false);
  const [errorMessage, setErrorMessage] = reactModule.useState<string | null>(null);

  const handleSubmit = async (event: reactModule.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    // eslint-disable-next-line security/detect-possible-timing-attacks
    if (password !== passwordConfirmation) {
      setErrorMessage("Las contraseñas no coinciden.");
      return;
    }

    setIsSubmitting(true);

    try {
      await auth.register({
        tenantName: tenantName.trim(),
        email: email.trim(),
        password
      });
      navigate("/onboarding/whatsapp", { replace: true });
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

  return (
    <authSharedModule.AuthScreenContainer>
      <authSharedModule.AuthCard
        subtitle="Comienza a usar AI-Agents hoy mismo"
        title="Crear cuenta"
      >
        <form className="space-y-5" onSubmit={(event) => void handleSubmit(event)}>
          <div>
            <authSharedModule.AuthInputLabel htmlFor="tenant-name" text="Nombre de la empresa" />
            <input
              className={inputClassName}
              id="tenant-name"
              onChange={(event) => {
                setTenantName(event.target.value);
              }}
              placeholder="Mi Empresa S.A."
              required
              value={tenantName}
            />
          </div>

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

          <div>
            <authSharedModule.AuthInputLabel htmlFor="password" text="Contraseña" />
            <div className="relative">
              <input
                autoComplete="new-password"
                className={`${inputClassName} pr-12`}
                id="password"
                minLength={8}
                onChange={(event) => {
                  setPassword(event.target.value);
                }}
                placeholder="••••••••"
                required
                type={isPasswordVisible ? "text" : "password"}
                value={password}
              />
              <authSharedModule.EyeToggleButton
                isVisible={isPasswordVisible}
                onClick={() => {
                  setIsPasswordVisible((currentValue) => !currentValue);
                }}
              />
            </div>
          </div>

          <div>
            <authSharedModule.AuthInputLabel
              htmlFor="password-confirmation"
              text="Confirmar contraseña"
            />
            <div className="relative">
              <input
                autoComplete="new-password"
                className={`${inputClassName} pr-12`}
                id="password-confirmation"
                minLength={8}
                onChange={(event) => {
                  setPasswordConfirmation(event.target.value);
                }}
                placeholder="••••••••"
                required
                type={isPasswordConfirmationVisible ? "text" : "password"}
                value={passwordConfirmation}
              />
              <authSharedModule.EyeToggleButton
                isVisible={isPasswordConfirmationVisible}
                onClick={() => {
                  setIsPasswordConfirmationVisible((currentValue) => !currentValue);
                }}
              />
            </div>
          </div>

          {errorMessage !== null ? (
            <errorBannerModule.ErrorBanner
              className="rounded-xl bg-red-100 px-3 py-2 text-base font-medium text-red-700 md:text-[18px]"
              message={errorMessage}
            />
          ) : null}

          <button
            className="mt-2 h-12 w-full rounded-xl bg-teal-700 px-4 text-base font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60 md:h-14 md:text-xl"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? "Creando..." : "Crear cuenta"}
          </button>
        </form>

        <p className="mt-8 text-center text-base text-slate-600 md:text-xl">
          ¿Ya tienes cuenta?{" "}
          <reactRouterDomModule.Link
            className="font-semibold text-teal-700 hover:underline"
            to="/login"
          >
            Iniciar sesión
          </reactRouterDomModule.Link>
        </p>
      </authSharedModule.AuthCard>
    </authSharedModule.AuthScreenContainer>
  );
}

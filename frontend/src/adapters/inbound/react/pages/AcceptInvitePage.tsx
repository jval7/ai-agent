import * as reactModule from "react";
import * as reactRouterDomModule from "react-router-dom";
import * as authContextModule from "@adapters/inbound/react/app/AuthContext";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as authSharedModule from "@adapters/inbound/react/components/AuthShared";
import * as uiErrorModule from "@shared/http/ui_error";

const inputClassName =
  "h-12 w-full rounded-xl border border-palette-mist bg-white px-4 text-base text-slate-800 placeholder:text-slate-400 focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 md:h-14 md:text-lg";

export function AcceptInvitePage() {
  const auth = authContextModule.useAuth();
  const navigate = reactRouterDomModule.useNavigate();
  const [searchParams] = reactRouterDomModule.useSearchParams();

  const token = searchParams.get("token") ?? "";

  const [newPassword, setNewPassword] = reactModule.useState("");
  const [confirmPassword, setConfirmPassword] = reactModule.useState("");
  const [isNewPasswordVisible, setIsNewPasswordVisible] = reactModule.useState(false);
  const [isConfirmPasswordVisible, setIsConfirmPasswordVisible] = reactModule.useState(false);
  const [isSubmitting, setIsSubmitting] = reactModule.useState(false);
  const [errorMessage, setErrorMessage] = reactModule.useState<string | null>(null);

  if (token.length === 0) {
    return (
      <authSharedModule.AuthScreenContainer>
        <authSharedModule.AuthCard subtitle="Configura tu contraseña" title="Crear cuenta">
          <errorBannerModule.ErrorBanner
            className="rounded-xl bg-red-100 px-3 py-2 text-base font-medium text-red-700 md:text-[18px]"
            message="Link inválido o expirado"
          />
          <p className="mt-6 text-center text-base text-slate-600 md:text-xl">
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

  const handleSubmit = async (event: reactModule.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (newPassword !== confirmPassword) {
      setErrorMessage("Las contraseñas no coinciden");
      return;
    }

    setIsSubmitting(true);

    try {
      await auth.acceptInvitation({ token, password: newPassword });
      navigate("/configuraciones", { replace: true });
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
        subtitle="Elige una contraseña para tu cuenta"
        title="Crear cuenta"
      >
        <form className="space-y-5" onSubmit={(event) => void handleSubmit(event)}>
          <div>
            <authSharedModule.AuthInputLabel htmlFor="new_password" text="Nueva contraseña" />
            <div className="relative">
              <input
                autoComplete="new-password"
                className={`${inputClassName} pr-12`}
                id="new_password"
                minLength={8}
                onChange={(event) => {
                  setNewPassword(event.target.value);
                }}
                placeholder="••••••••"
                required
                type={isNewPasswordVisible ? "text" : "password"}
                value={newPassword}
              />
              <authSharedModule.EyeToggleButton
                isVisible={isNewPasswordVisible}
                onClick={() => {
                  setIsNewPasswordVisible((currentValue) => !currentValue);
                }}
              />
            </div>
          </div>

          <div>
            <authSharedModule.AuthInputLabel
              htmlFor="confirm_password"
              text="Confirmar contraseña"
            />
            <div className="relative">
              <input
                autoComplete="new-password"
                className={`${inputClassName} pr-12`}
                id="confirm_password"
                minLength={8}
                onChange={(event) => {
                  setConfirmPassword(event.target.value);
                }}
                placeholder="••••••••"
                required
                type={isConfirmPasswordVisible ? "text" : "password"}
                value={confirmPassword}
              />
              <authSharedModule.EyeToggleButton
                isVisible={isConfirmPasswordVisible}
                onClick={() => {
                  setIsConfirmPasswordVisible((currentValue) => !currentValue);
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
            className="mt-2 h-12 w-full rounded-xl bg-brand-teal px-4 text-base font-semibold text-white transition hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60 md:h-14 md:text-xl"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? "Creando cuenta..." : "Crear cuenta"}
          </button>
        </form>

        <authSharedModule.SecurityHint />
      </authSharedModule.AuthCard>
    </authSharedModule.AuthScreenContainer>
  );
}

import * as reactModule from "react";

import type * as authModel from "@domain/models/auth";

import * as appContainerContextModule from "./AppContainerContext";

export interface AuthContextValue {
  status: authModel.AuthStatus;
  userProfile: authModel.UserProfile | null;
  login(input: authModel.LoginInput): Promise<void>;
  logout(): Promise<void>;
  acceptInvitation(input: authModel.AcceptInvitationInput): Promise<void>;
  requestPasswordReset(input: authModel.RequestPasswordResetInput): Promise<void>;
  confirmPasswordReset(input: authModel.ConfirmPasswordResetInput): Promise<void>;
}

const AuthContext = reactModule.createContext<AuthContextValue | null>(null);

export function AuthProvider(props: { children: reactModule.ReactNode }) {
  const appContainer = appContainerContextModule.useAppContainer();
  const [status, setStatus] = reactModule.useState<authModel.AuthStatus>("loading");
  const [userProfile, setUserProfile] = reactModule.useState<authModel.UserProfile | null>(null);

  reactModule.useEffect(() => {
    let isMounted = true;

    const bootstrap = async () => {
      const profile = await appContainer.authUseCase.bootstrapSession();
      if (!isMounted) {
        return;
      }
      if (profile !== null) {
        setUserProfile(profile);
        setStatus("authenticated");
      } else {
        setUserProfile(null);
        setStatus("anonymous");
      }
    };

    void bootstrap();

    return () => {
      isMounted = false;
    };
  }, [appContainer.authUseCase]);

  const value = reactModule.useMemo<AuthContextValue>(
    () => ({
      status,
      userProfile,
      login: async (input) => {
        const profile = await appContainer.authUseCase.login(input);
        setUserProfile(profile);
        setStatus("authenticated");
      },
      logout: async () => {
        await appContainer.authUseCase.logout();
        setUserProfile(null);
        setStatus("anonymous");
      },
      acceptInvitation: async (input) => {
        await appContainer.authUseCase.acceptInvitation(input);
        setStatus("authenticated");
      },
      requestPasswordReset: async (input) => {
        await appContainer.authUseCase.requestPasswordReset(input);
      },
      confirmPasswordReset: async (input) => {
        await appContainer.authUseCase.confirmPasswordReset(input);
      }
    }),
    [appContainer.authUseCase, status, userProfile]
  );

  return <AuthContext.Provider value={value}>{props.children}</AuthContext.Provider>;
}

export function useAuth() {
  const contextValue = reactModule.useContext(AuthContext);
  if (contextValue === null) {
    throw new Error("AuthProvider is required");
  }
  return contextValue;
}

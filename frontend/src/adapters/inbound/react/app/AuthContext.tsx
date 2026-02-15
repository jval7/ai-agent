import * as reactModule from "react";

import type * as authModel from "@domain/models/auth";

import * as appContainerContextModule from "./AppContainerContext";

interface AuthContextValue {
  status: authModel.AuthStatus;
  login(input: authModel.LoginInput): Promise<void>;
  register(input: authModel.RegisterInput): Promise<void>;
  logout(): Promise<void>;
}

const AuthContext = reactModule.createContext<AuthContextValue | null>(null);

export function AuthProvider(props: { children: reactModule.ReactNode }) {
  const appContainer = appContainerContextModule.useAppContainer();
  const [status, setStatus] = reactModule.useState<authModel.AuthStatus>("loading");

  reactModule.useEffect(() => {
    let isMounted = true;

    const bootstrap = async () => {
      const hasSession = await appContainer.authUseCase.bootstrapSession();
      if (!isMounted) {
        return;
      }
      setStatus(hasSession ? "authenticated" : "anonymous");
    };

    void bootstrap();

    return () => {
      isMounted = false;
    };
  }, [appContainer.authUseCase]);

  const value = reactModule.useMemo<AuthContextValue>(
    () => ({
      status,
      login: async (input) => {
        await appContainer.authUseCase.login(input);
        setStatus("authenticated");
      },
      register: async (input) => {
        await appContainer.authUseCase.register(input);
        setStatus("authenticated");
      },
      logout: async () => {
        await appContainer.authUseCase.logout();
        setStatus("anonymous");
      }
    }),
    [appContainer.authUseCase, status]
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

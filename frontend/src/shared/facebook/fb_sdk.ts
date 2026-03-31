declare global {
  interface Window {
    fbAsyncInit: () => void;
    FB: {
      init: (params: {
        appId: string;
        autoLogAppEvents: boolean;
        xfbml: boolean;
        version: string;
      }) => void;
      login: (callback: (response: FBLoginResponse) => void, options: FBLoginOptions) => void;
    };
  }
}

interface FBLoginResponse {
  status: string;
  authResponse?: {
    code?: string;
    accessToken?: string;
    userID?: string;
    expiresIn?: number;
  };
}

interface FBLoginOptions {
  config_id: string;
  response_type?: string;
  override_default_response_type?: boolean;
  extras: {
    setup: Record<string, never>;
    featureType: string;
    sessionInfoVersion: string;
  };
}

export function loadFacebookSdk(appId: string): Promise<void> {
  if (window.FB) return Promise.resolve();

  return new Promise((resolve) => {
    window.fbAsyncInit = function () {
      window.FB.init({
        appId,
        autoLogAppEvents: true,
        xfbml: true,
        version: "v22.0"
      });
      resolve();
    };
    const script = document.createElement("script");
    script.src = "https://connect.facebook.net/en_US/sdk.js";
    script.async = true;
    script.defer = true;
    script.crossOrigin = "anonymous";
    document.head.appendChild(script);
  });
}

export interface EmbeddedSignupResult {
  code: string;
  redirectUri: string | null;
}

export function launchEmbeddedSignup(configId: string): Promise<EmbeddedSignupResult> {
  return new Promise((resolve, reject) => {
    let capturedRedirectUri: string | null = null;

    const originalOpen = window.open;
    window.open = function (...args: Parameters<typeof window.open>) {
      const url = args[0];
      if (typeof url === "string" && url.includes("facebook.com")) {
        try {
          const parsed = new URL(url);
          capturedRedirectUri = parsed.searchParams.get("redirect_uri");
        } catch {
          /* ignore parse errors */
        }
      }
      return originalOpen.apply(window, args);
    };

    window.FB.login(
      (response: FBLoginResponse) => {
        window.open = originalOpen;
        if (response.authResponse?.code) {
          resolve({ code: response.authResponse.code, redirectUri: capturedRedirectUri });
        } else {
          reject(new Error("Facebook login cancelled or failed"));
        }
      },
      {
        config_id: configId,
        response_type: "code",
        override_default_response_type: true,
        extras: {
          setup: {},
          featureType: "whatsapp_business_app_onboarding",
          sessionInfoVersion: "3"
        }
      }
    );
  });
}

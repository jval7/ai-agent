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

export interface SessionInfo {
  phoneNumberId?: string;
  wabaId?: string;
  businessId?: string;
}

export interface EmbeddedSignupResult {
  code: string;
  sessionInfo: SessionInfo;
}

export function launchEmbeddedSignup(configId: string): Promise<EmbeddedSignupResult> {
  return new Promise((resolve, reject) => {
    const sessionInfo: SessionInfo = {};

    interface EmbeddedSignupEvent {
      type?: string;
      data?: {
        phone_number_id?: string;
        waba_id?: string;
        business_id?: string;
      };
    }

    const messageHandler = (event: MessageEvent) => {
      if (!event.origin?.endsWith("facebook.com")) return;
      try {
        const parsed = JSON.parse(String(event.data)) as EmbeddedSignupEvent;
        if (parsed.type === "WA_EMBEDDED_SIGNUP" && parsed.data) {
          if (parsed.data.phone_number_id) sessionInfo.phoneNumberId = parsed.data.phone_number_id;
          if (parsed.data.waba_id) sessionInfo.wabaId = parsed.data.waba_id;
          if (parsed.data.business_id) sessionInfo.businessId = parsed.data.business_id;
        }
      } catch {
        /* non-JSON message, ignore */
      }
    };
    window.addEventListener("message", messageHandler);

    window.FB.login(
      (response: FBLoginResponse) => {
        window.removeEventListener("message", messageHandler);
        if (response.authResponse?.code) {
          resolve({ code: response.authResponse.code, sessionInfo });
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

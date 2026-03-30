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
    code: string;
  };
}

interface FBLoginOptions {
  config_id: string;
  response_type: string;
  override_default_response_type: boolean;
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

export function launchEmbeddedSignup(configId: string): Promise<string> {
  return new Promise((resolve, reject) => {
    window.FB.login(
      (response: FBLoginResponse) => {
        if (response.authResponse?.code) {
          resolve(response.authResponse.code);
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

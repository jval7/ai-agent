import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import type { PaymentTiming } from "@domain/models/agent";
import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as billingDisclosureModalModule from "@adapters/inbound/react/components/BillingDisclosureModal";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as plantillasSectionModule from "@adapters/inbound/react/components/sections/PlantillasSection";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import * as settingsSidebarModule from "@adapters/inbound/react/components/settings/SettingsSidebar";
import * as agentIdentityDetailSectionModule from "@adapters/inbound/react/components/ProfessionalProfileForm/AgentIdentityDetailSection";
import * as agentServicesDetailSectionModule from "@adapters/inbound/react/components/ProfessionalProfileForm/AgentServicesDetailSection";
import * as agentPaymentsDetailSectionModule from "@adapters/inbound/react/components/ProfessionalProfileForm/AgentPaymentsDetailSection";
import * as uiErrorModule from "@shared/http/ui_error";
import * as fbSdkModule from "@shared/facebook/fb_sdk";
import * as dateUtilsModule from "@shared/utils/date";

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------
const whatsappConnectionQueryKey = ["whatsapp-connection"] as const;
const googleCalendarConnectionQueryKey = ["google-calendar-connection"] as const;
const onboardingStatusQueryKey = ["onboarding-status"] as const;
const promptQueryKey = ["system-prompt"] as const;
const settingsQueryKey = ["agent-settings"] as const;
const officialTemplateStatusQueryKey = ["official-template-status"] as const;
const tenantProfileQueryKey = ["tenant-profile"] as const;

// ---------------------------------------------------------------------------
// Section routing
// ---------------------------------------------------------------------------
type SectionId =
  | "perfil"
  | "consultorio"
  | "identidad"
  | "servicios"
  | "medios-pago"
  | "whatsapp"
  | "google-calendar"
  | "recordatorios-config"
  | "plantillas"
  | "momento-cobro"
  | "delay";

const SIDEBAR_GROUPS: settingsSidebarModule.SidebarGroup[] = [
  {
    id: "general",
    label: "General",
    items: [
      { id: "perfil", label: "Perfil del profesional" },
      { id: "consultorio", label: "Datos del consultorio" }
    ]
  },
  {
    id: "agente",
    label: "Agente",
    items: [
      { id: "identidad", label: "Identidad del asistente" },
      { id: "servicios", label: "Servicios y práctica" },
      { id: "medios-pago", label: "Medios de pago" }
    ]
  },
  {
    id: "conexiones",
    label: "Conexiones",
    items: [
      { id: "whatsapp", label: "WhatsApp Business" },
      { id: "google-calendar", label: "Google Calendar" }
    ]
  },
  {
    id: "recordatorios",
    label: "Recordatorios",
    items: [
      { id: "recordatorios-config", label: "Activación y configuración" },
      { id: "plantillas", label: "Plantillas de mensajes" }
    ]
  },
  {
    id: "avanzadas",
    label: "Avanzadas",
    items: [
      { id: "momento-cobro", label: "Momento del cobro" },
      { id: "delay", label: "Delay de respuesta" }
    ]
  }
];

const ALL_SECTION_IDS = new Set<string>(SIDEBAR_GROUPS.flatMap((g) => g.items.map((i) => i.id)));

const DEFAULT_SECTION: SectionId = "perfil";

/** Resolves legacy ?tab= values and new ?section= values to a SectionId. */
function resolveSectionFromParams(params: URLSearchParams): SectionId {
  const section = params.get("section");
  if (section !== null && ALL_SECTION_IDS.has(section)) return section as SectionId;
  // Backward-compat: legacy tab param
  const tab = params.get("tab");
  if (tab === "general" || tab === "agente") return "perfil";
  if (tab === "conexiones") return "whatsapp";
  if (tab === "recordatorios" || tab === "ajustes") return "recordatorios-config";
  return DEFAULT_SECTION;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function buildConnectionStatusBadge(status: string | undefined): JSX.Element {
  if (status === undefined) {
    return <statusBadgeModule.StatusBadge label="cargando" tone="neutral" />;
  }
  if (status === "CONNECTED") {
    return <statusBadgeModule.StatusBadge label="CONNECTED" tone="success" />;
  }
  if (status === "PENDING") {
    return <statusBadgeModule.StatusBadge label="PENDING" tone="warning" />;
  }
  return <statusBadgeModule.StatusBadge label="DISCONNECTED" tone="danger" />;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export function ConfiguracionesPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const navigate = reactRouterDomModule.useNavigate();
  const location = reactRouterDomModule.useLocation();

  const searchParams = reactModule.useMemo(
    () => new URLSearchParams(location.search),
    [location.search]
  );

  const [activeSection, setActiveSection] = reactModule.useState<SectionId>(() =>
    resolveSectionFromParams(new URLSearchParams(window.location.search))
  );

  // Mobile: "list" shows the sidebar; "detail" shows the selected section.
  const [mobileView, setMobileView] = reactModule.useState<"list" | "detail">("list");

  reactModule.useEffect(() => {
    const resolved = resolveSectionFromParams(searchParams);
    setActiveSection(resolved);
  }, [searchParams]);

  const handleSelectSection = (id: string) => {
    setActiveSection(id as SectionId);
    setMobileView("detail");
  };

  // -------------------------------------------------------------------
  // Queries — connections & onboarding
  // -------------------------------------------------------------------
  const whatsappConnectionQuery = reactQueryModule.useQuery({
    queryKey: whatsappConnectionQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getWhatsappConnectionStatus()
  });

  const googleCalendarConnectionQuery = reactQueryModule.useQuery({
    queryKey: googleCalendarConnectionQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getGoogleCalendarConnectionStatus()
  });

  const onboardingStatusQuery = reactQueryModule.useQuery({
    queryKey: onboardingStatusQueryKey,
    queryFn: () => appContainer.onboardingUseCase.getOnboardingStatus()
  });

  const [registrationPin, setRegistrationPin] = reactModule.useState("");
  const queryClient = reactQueryModule.useQueryClient();

  const whatsappSessionMutation = reactQueryModule.useMutation({
    mutationFn: async () => {
      const session = await appContainer.whatsappOnboardingUseCase.createEmbeddedSignupSession(
        registrationPin.trim() || undefined
      );
      await fbSdkModule.loadFacebookSdk();
      const result = await fbSdkModule.launchEmbeddedSignup(session.configId, session.appId);
      if (!result.code && !result.accessToken) throw new Error("No code or token received");
      const pin = registrationPin.trim();
      const base = {
        ...(result.code ? { code: result.code } : {}),
        ...(result.accessToken ? { accessToken: result.accessToken } : {}),
        state: session.state,
        ...(result.sessionInfo.phoneNumberId
          ? { phoneNumberId: result.sessionInfo.phoneNumberId }
          : {}),
        ...(result.sessionInfo.wabaId ? { wabaId: result.sessionInfo.wabaId } : {})
      };
      return appContainer.whatsappOnboardingUseCase.completeEmbeddedSignup(
        pin ? { ...base, registrationPin: pin } : base
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: whatsappConnectionQueryKey });
      void queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey });
    }
  });

  const whatsappOAuthMutation = reactQueryModule.useMutation({
    mutationFn: async () => {
      const session = await appContainer.whatsappOnboardingUseCase.createEmbeddedSignupSession(
        registrationPin.trim() || undefined
      );
      window.location.assign(session.connectUrl);
    }
  });

  const googleSessionMutation = reactQueryModule.useMutation({
    mutationFn: () => appContainer.onboardingUseCase.createGoogleSession(),
    onSuccess: (session) => {
      window.location.assign(session.connectUrl);
    }
  });

  const statusBadgeElement =
    onboardingStatusQuery.data?.ready === true ? (
      <statusBadgeModule.StatusBadge label="READY" tone="success" />
    ) : (
      <statusBadgeModule.StatusBadge label="PENDIENTE" tone="warning" />
    );

  const onboardingErrorMessage = uiErrorModule.resolveUiErrorMessage([
    whatsappSessionMutation.error,
    googleSessionMutation.error,
    whatsappConnectionQuery.error,
    googleCalendarConnectionQuery.error,
    onboardingStatusQuery.error
  ]);

  const metaOAuthStatus = searchParams.get("meta_oauth");
  const googleOAuthStatus = searchParams.get("google_oauth");
  const callbackReason = searchParams.get("reason");
  const callbackCode = searchParams.get("status");

  // -------------------------------------------------------------------
  // Queries — agent settings
  // -------------------------------------------------------------------
  const promptQuery = reactQueryModule.useQuery({
    queryKey: promptQueryKey,
    queryFn: () => appContainer.agentUseCase.getSystemPrompt()
  });

  const settingsQuery = reactQueryModule.useQuery({
    queryKey: settingsQueryKey,
    queryFn: () => appContainer.agentUseCase.getAgentSettings()
  });

  const [debounceDelay, setDebounceDelay] = reactModule.useState(0);
  const [reminderDaysBefore, setReminderDaysBefore] = reactModule.useState(1);
  const [paymentDetailsText, setPaymentDetailsText] = reactModule.useState("");
  const [officeAddress, setOfficeAddress] = reactModule.useState("");
  const [officeArrivalInstructions, setOfficeArrivalInstructions] = reactModule.useState("");
  const [paymentTiming, setPaymentTiming] = reactModule.useState<PaymentTiming>("BEFORE_SESSION");
  const [activationStep, setActivationStep] = reactModule.useState<"idle" | "disclosure">("idle");

  reactModule.useEffect(() => {
    if (settingsQuery.data !== undefined) {
      setDebounceDelay(settingsQuery.data.messageDebounceDelaySeconds);
      setReminderDaysBefore(settingsQuery.data.appointmentReminderDaysBefore ?? 1);
      setPaymentDetailsText(settingsQuery.data.paymentDetailsText ?? "");
      setOfficeAddress(settingsQuery.data.officeLocation?.address ?? "");
      setOfficeArrivalInstructions(settingsQuery.data.officeLocation?.arrivalInstructions ?? "");
      setPaymentTiming(settingsQuery.data.paymentTiming);
    }
  }, [settingsQuery.data]);

  // -------------------------------------------------------------------
  // Queries — official template status & reminders
  // -------------------------------------------------------------------
  const officialTemplateStatusQuery = reactQueryModule.useQuery({
    queryKey: officialTemplateStatusQueryKey,
    queryFn: () => appContainer.whatsappTemplateUseCase.listOfficialTemplateStatus()
  });

  const attendanceStatus = (officialTemplateStatusQuery.data ?? []).find(
    (s) => s.kind === "ATTENDANCE"
  );
  const paymentStatus = (officialTemplateStatusQuery.data ?? []).find((s) => s.kind === "PAYMENT");

  const reminderSetupState: "loading" | "not_configured" | "preparing" | "active" | "broken" =
    (() => {
      if (
        attendanceStatus === undefined ||
        paymentStatus === undefined ||
        settingsQuery.data === undefined
      ) {
        return "loading";
      }
      if (attendanceStatus.metaStatus === "PENDING" || paymentStatus.metaStatus === "PENDING") {
        return "preparing";
      }
      if (
        attendanceStatus.metaStatus === "REJECTED" ||
        attendanceStatus.metaStatus === "DISABLED"
      ) {
        return "broken";
      }
      if (
        attendanceStatus.metaStatus === "APPROVED" &&
        settingsQuery.data.appointmentReminderEnabled
      ) {
        return "active";
      }
      return "not_configured";
    })();

  const retryKindMutation = reactQueryModule.useMutation({
    mutationFn: (kind: "ATTENDANCE" | "PAYMENT") =>
      appContainer.whatsappTemplateUseCase.activateOfficialTemplate(kind),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: officialTemplateStatusQueryKey });
    }
  });

  const activateAllMutation = reactQueryModule.useMutation({
    mutationFn: async () => {
      await appContainer.whatsappTemplateUseCase.activateOfficialTemplate("ATTENDANCE");
      try {
        await appContainer.whatsappTemplateUseCase.activateOfficialTemplate("PAYMENT");
      } catch {
        // PAYMENT es opcional.
      }
      const fresh = await appContainer.agentUseCase.getAgentSettings();
      return appContainer.agentUseCase.updateAgentSettings({
        messageDebounceDelaySeconds: fresh.messageDebounceDelaySeconds,
        appointmentReminderEnabled: true,
        appointmentReminderDaysBefore: fresh.appointmentReminderDaysBefore ?? 1,
        appointmentReminderAttendanceTemplateName: fresh.appointmentReminderAttendanceTemplateName,
        appointmentReminderPaymentTemplateName: fresh.appointmentReminderPaymentTemplateName,
        paymentDetailsText: fresh.paymentDetailsText,
        officeLocation: fresh.officeLocation,
        paymentTiming: fresh.paymentTiming
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: officialTemplateStatusQueryKey });
      await queryClient.invalidateQueries({ queryKey: settingsQueryKey });
    }
  });

  const deactivateAllMutation = reactQueryModule.useMutation({
    mutationFn: async () => {
      try {
        await appContainer.whatsappTemplateUseCase.deactivateOfficialTemplate("ATTENDANCE");
      } catch {
        // Best-effort.
      }
      try {
        await appContainer.whatsappTemplateUseCase.deactivateOfficialTemplate("PAYMENT");
      } catch {
        // Best-effort.
      }
      const fresh = await appContainer.agentUseCase.getAgentSettings();
      return appContainer.agentUseCase.updateAgentSettings({
        messageDebounceDelaySeconds: fresh.messageDebounceDelaySeconds,
        appointmentReminderEnabled: false,
        appointmentReminderDaysBefore: fresh.appointmentReminderDaysBefore,
        appointmentReminderAttendanceTemplateName: null,
        appointmentReminderPaymentTemplateName: null,
        paymentDetailsText: fresh.paymentDetailsText,
        officeLocation: fresh.officeLocation,
        paymentTiming: fresh.paymentTiming
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: officialTemplateStatusQueryKey });
      await queryClient.invalidateQueries({ queryKey: settingsQueryKey });
    }
  });

  const isReminderActive = reminderSetupState === "active";

  const settingsMutation = reactQueryModule.useMutation({
    mutationFn: () =>
      appContainer.agentUseCase.updateAgentSettings({
        messageDebounceDelaySeconds: debounceDelay,
        appointmentReminderEnabled: isReminderActive,
        appointmentReminderDaysBefore: isReminderActive ? reminderDaysBefore : null,
        appointmentReminderAttendanceTemplateName:
          settingsQuery.data?.appointmentReminderAttendanceTemplateName ?? null,
        appointmentReminderPaymentTemplateName:
          settingsQuery.data?.appointmentReminderPaymentTemplateName ?? null,
        paymentDetailsText: paymentDetailsText.trim() === "" ? null : paymentDetailsText,
        officeLocation: settingsQuery.data?.officeLocation ?? null,
        paymentTiming
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: settingsQueryKey });
    }
  });

  // -------------------------------------------------------------------
  // Office settings
  // -------------------------------------------------------------------
  const buildOfficeLocationInput = () => {
    const trimmedAddress = officeAddress.trim();
    if (trimmedAddress === "") return null;
    return {
      address: trimmedAddress,
      arrivalInstructions:
        officeArrivalInstructions.trim() === "" ? null : officeArrivalInstructions.trim()
    };
  };

  const [officeSuccessMessage, setOfficeSuccessMessage] = reactModule.useState<string | null>(null);

  const officeSettingsMutation = reactQueryModule.useMutation({
    mutationFn: () =>
      appContainer.agentUseCase.updateAgentSettings({
        messageDebounceDelaySeconds: settingsQuery.data?.messageDebounceDelaySeconds ?? 0,
        appointmentReminderEnabled: settingsQuery.data?.appointmentReminderEnabled ?? false,
        appointmentReminderDaysBefore: settingsQuery.data?.appointmentReminderDaysBefore ?? null,
        appointmentReminderAttendanceTemplateName:
          settingsQuery.data?.appointmentReminderAttendanceTemplateName ?? null,
        appointmentReminderPaymentTemplateName:
          settingsQuery.data?.appointmentReminderPaymentTemplateName ?? null,
        paymentDetailsText: settingsQuery.data?.paymentDetailsText ?? null,
        officeLocation: buildOfficeLocationInput(),
        paymentTiming: settingsQuery.data?.paymentTiming ?? "BEFORE_SESSION"
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: settingsQueryKey });
      setOfficeSuccessMessage("Datos del consultorio guardados.");
    }
  });

  const officeErrorMessage = uiErrorModule.resolveUiErrorMessage([
    officeSettingsMutation.error,
    settingsQuery.error
  ]);

  const savedOfficeAddress = settingsQuery.data?.officeLocation?.address ?? "";
  const savedOfficeArrivalInstructions =
    settingsQuery.data?.officeLocation?.arrivalInstructions ?? "";
  const isOfficeDirty =
    officeAddress.trim() !== savedOfficeAddress.trim() ||
    officeArrivalInstructions.trim() !== savedOfficeArrivalInstructions.trim();

  // -------------------------------------------------------------------
  // Payment timing
  // -------------------------------------------------------------------
  const paymentTimingMutation = reactQueryModule.useMutation({
    mutationFn: (newTiming: PaymentTiming) =>
      appContainer.agentUseCase.updateAgentSettings({
        messageDebounceDelaySeconds: settingsQuery.data?.messageDebounceDelaySeconds ?? 0,
        appointmentReminderEnabled: settingsQuery.data?.appointmentReminderEnabled ?? false,
        appointmentReminderDaysBefore: settingsQuery.data?.appointmentReminderDaysBefore ?? null,
        appointmentReminderAttendanceTemplateName:
          settingsQuery.data?.appointmentReminderAttendanceTemplateName ?? null,
        appointmentReminderPaymentTemplateName:
          settingsQuery.data?.appointmentReminderPaymentTemplateName ?? null,
        paymentDetailsText: settingsQuery.data?.paymentDetailsText ?? null,
        officeLocation: settingsQuery.data?.officeLocation ?? null,
        paymentTiming: newTiming
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: settingsQueryKey });
    }
  });

  const handlePaymentTimingChange = (newTiming: PaymentTiming): void => {
    setPaymentTiming(newTiming);
    paymentTimingMutation.mutate(newTiming);
  };

  // -------------------------------------------------------------------
  // Tenant profile
  // -------------------------------------------------------------------
  const profileQuery = reactQueryModule.useQuery({
    queryKey: tenantProfileQueryKey,
    queryFn: () => appContainer.tenantUseCase.getProfile()
  });

  const [profileDraft, setProfileDraft] = reactModule.useState({ professionalName: "" });
  const [profileSuccessMessage, setProfileSuccessMessage] = reactModule.useState<string | null>(
    null
  );

  reactModule.useEffect(() => {
    if (profileQuery.data !== undefined) {
      setProfileDraft({ professionalName: profileQuery.data.professionalName ?? "" });
    }
  }, [profileQuery.data]);

  const profileMutation = reactQueryModule.useMutation({
    mutationFn: () =>
      appContainer.tenantUseCase.updateProfile({
        professionalName: profileDraft.professionalName.trim() || null
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: tenantProfileQueryKey });
      setProfileSuccessMessage("Perfil actualizado.");
    }
  });

  const profileErrorMessage = uiErrorModule.resolveUiErrorMessage([
    profileMutation.error,
    profileQuery.error
  ]);

  const savedProfessionalName = profileQuery.data?.professionalName ?? null;
  const profileDraftTrimmed = profileDraft.professionalName.trim() || null;
  const isProfileDirty = profileDraftTrimmed !== savedProfessionalName;

  // -------------------------------------------------------------------
  // Debounced inputs
  // -------------------------------------------------------------------
  const daysBeforeTimeoutRef = reactModule.useRef<number | null>(null);
  const handleDaysBeforeChange = (event: reactModule.ChangeEvent<HTMLInputElement>) => {
    const parsed = Number(event.target.value);
    setReminderDaysBefore(parsed);
    if (Number.isNaN(parsed) || parsed < 1 || parsed > 7) return;
    if (daysBeforeTimeoutRef.current !== null) window.clearTimeout(daysBeforeTimeoutRef.current);
    daysBeforeTimeoutRef.current = window.setTimeout(() => {
      settingsMutation.mutate();
    }, 800);
  };

  const debounceDelayTimeoutRef = reactModule.useRef<number | null>(null);
  const handleDebounceDelayChange = (event: reactModule.ChangeEvent<HTMLInputElement>) => {
    const parsed = Number(event.target.value);
    setDebounceDelay(parsed);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > 30) return;
    if (debounceDelayTimeoutRef.current !== null)
      window.clearTimeout(debounceDelayTimeoutRef.current);
    debounceDelayTimeoutRef.current = window.setTimeout(() => {
      settingsMutation.mutate();
    }, 800);
  };

  const settingsErrorMessage = uiErrorModule.resolveUiErrorMessage([
    settingsMutation.error,
    paymentTimingMutation.error,
    settingsQuery.error,
    activateAllMutation.error,
    deactivateAllMutation.error,
    retryKindMutation.error,
    officialTemplateStatusQuery.error
  ]);

  // -------------------------------------------------------------------
  // Section detail panels
  // -------------------------------------------------------------------
  function renderDetail(): JSX.Element {
    // ----- GENERAL -----
    if (activeSection === "perfil") {
      return (
        <div className="max-w-3xl space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-brand-ink">Perfil del profesional</h2>
            <p className="mt-1 text-sm text-slate-500">
              Este nombre aparece en los títulos de los eventos de Google Calendar cuando agendas
              una cita.
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700" htmlFor="professional-name">
              Nombre del profesional
            </label>
            <input
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal disabled:cursor-not-allowed disabled:opacity-60"
              disabled={profileQuery.isLoading}
              id="professional-name"
              maxLength={80}
              onChange={(e) => {
                setProfileDraft((prev) => ({ ...prev, professionalName: e.target.value }));
                setProfileSuccessMessage(null);
              }}
              placeholder="Ej. Dra. Ana Garcia"
              type="text"
              value={profileDraft.professionalName}
            />
            <p className="mt-1.5 text-xs text-slate-500">
              Formato del titulo en Calendar: {"{tu nombre}"}/{"{nombre del paciente}"}. Si dejas
              este campo vacio se usara "Profesional" por defecto.
            </p>
          </div>
          {profileSuccessMessage !== null ? (
            <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {profileSuccessMessage}
            </div>
          ) : null}
          {profileErrorMessage !== null ? (
            <errorBannerModule.ErrorBanner className="mt-3" message={profileErrorMessage} />
          ) : null}
          <div className="flex justify-end">
            <button
              className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
              disabled={profileMutation.isPending || profileQuery.isLoading || !isProfileDirty}
              onClick={() => {
                profileMutation.mutate();
              }}
              type="button"
            >
              {profileMutation.isPending ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </div>
      );
    }

    if (activeSection === "consultorio") {
      return (
        <div className="max-w-3xl space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-brand-ink">Datos del consultorio</h2>
            <p className="mt-1 text-sm text-slate-500">
              Esta informacion se incluye automaticamente en los mensajes de confirmacion de citas
              presenciales y en los eventos de Google Calendar.
            </p>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700" htmlFor="office-address">
                Direccion del consultorio
              </label>
              <p className="mt-0.5 text-xs text-slate-500">
                Si dejas este campo vacio, no se guardaran datos presenciales ni indicaciones de
                llegada. Puedes incluir edificio, piso, parqueadero y referencias en el mismo campo.
              </p>
              <textarea
                className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={settingsQuery.isLoading}
                id="office-address"
                onChange={(e) => {
                  setOfficeAddress(e.target.value);
                  setOfficeSuccessMessage(null);
                }}
                placeholder="Ej. Avenida Siempre Viva 1234, Edificio Azul, piso 5, parqueadero en sotano"
                rows={3}
                value={officeAddress}
              />
            </div>
            <div>
              <label
                className="block text-sm font-medium text-slate-700"
                htmlFor="office-arrival-instructions"
              >
                Indicaciones de llegada
              </label>
              <textarea
                className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={settingsQuery.isLoading}
                id="office-arrival-instructions"
                onChange={(e) => {
                  setOfficeArrivalInstructions(e.target.value);
                  setOfficeSuccessMessage(null);
                }}
                placeholder="Ej. Llegar 20 minutos antes con cedula fisica"
                rows={2}
                value={officeArrivalInstructions}
              />
            </div>
          </div>
          {officeSuccessMessage !== null ? (
            <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {officeSuccessMessage}
            </div>
          ) : null}
          {officeErrorMessage !== null ? (
            <errorBannerModule.ErrorBanner className="mt-3" message={officeErrorMessage} />
          ) : null}
          <div className="flex justify-end">
            <button
              className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
              disabled={
                officeSettingsMutation.isPending || settingsQuery.isLoading || !isOfficeDirty
              }
              onClick={() => {
                officeSettingsMutation.mutate();
              }}
              type="button"
            >
              {officeSettingsMutation.isPending ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </div>
      );
    }

    // ----- AGENTE -----
    if (activeSection === "identidad") {
      return <agentIdentityDetailSectionModule.AgentIdentityDetailSection />;
    }

    if (activeSection === "servicios") {
      return <agentServicesDetailSectionModule.AgentServicesDetailSection />;
    }

    if (activeSection === "medios-pago") {
      return <agentPaymentsDetailSectionModule.AgentPaymentsDetailSection />;
    }

    // ----- CONEXIONES -----
    if (activeSection === "whatsapp") {
      return (
        <div className="max-w-3xl space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-brand-ink">WhatsApp Business</h2>
            <p className="mt-1 text-sm text-slate-500">
              Conecta la linea de negocio para recibir y responder chats.
            </p>
          </div>
          <div className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-slate-700">Estado actual:</span>
              {buildConnectionStatusBadge(whatsappConnectionQuery.data?.status)}
            </div>
            {whatsappConnectionQuery.data !== undefined ? (
              <div className="space-y-2 text-sm text-slate-700">
                <p>
                  <strong>Tenant:</strong> {whatsappConnectionQuery.data.tenantId}
                </p>
                <p>
                  <strong>Phone Number ID:</strong>{" "}
                  {whatsappConnectionQuery.data.phoneNumberId ?? "-"}
                </p>
                <p>
                  <strong>Business Account ID:</strong>{" "}
                  {whatsappConnectionQuery.data.businessAccountId ?? "-"}
                </p>
              </div>
            ) : null}
            <div>
              <label
                className="block text-sm font-medium text-slate-700"
                htmlFor="registration-pin"
              >
                PIN de registro (solo si tienes 2FA)
              </label>
              <input
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal"
                id="registration-pin"
                maxLength={6}
                onChange={(e) => {
                  setRegistrationPin(e.target.value);
                }}
                placeholder="6 dígitos (opcional)"
                type="password"
                value={registrationPin}
              />
            </div>
            <div className="space-y-3">
              <button
                className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                disabled={whatsappSessionMutation.isPending}
                onClick={() => {
                  whatsappSessionMutation.mutate();
                }}
                type="button"
              >
                {whatsappSessionMutation.isPending ? "Conectando..." : "Conectar con Meta"}
              </button>
              <button
                className="block text-sm text-slate-500 underline hover:text-slate-700"
                disabled={whatsappOAuthMutation.isPending}
                onClick={() => {
                  whatsappOAuthMutation.mutate();
                }}
                type="button"
              >
                {whatsappOAuthMutation.isPending
                  ? "Redirigiendo..."
                  : "Conectar via redirect (sin coexistencia)"}
              </button>
              {whatsappSessionMutation.isSuccess ? (
                <p className="text-sm text-emerald-600">WhatsApp conectado correctamente.</p>
              ) : null}
            </div>
          </div>
          {onboardingErrorMessage !== null ? (
            <errorBannerModule.ErrorBanner message={onboardingErrorMessage} />
          ) : null}
        </div>
      );
    }

    if (activeSection === "google-calendar") {
      return (
        <div className="max-w-3xl space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-brand-ink">Google Calendar</h2>
            <p className="mt-1 text-sm text-slate-500">
              Conecta el calendario principal del profesional para disponibilidad y agenda.
            </p>
          </div>
          <div className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-slate-700">Estado actual:</span>
              {buildConnectionStatusBadge(googleCalendarConnectionQuery.data?.status)}
            </div>
            {googleCalendarConnectionQuery.data !== undefined ? (
              <div className="space-y-2 text-sm text-slate-700">
                <p>
                  <strong>Tenant:</strong> {googleCalendarConnectionQuery.data.tenantId}
                </p>
                <p>
                  <strong>Calendar ID:</strong>{" "}
                  {googleCalendarConnectionQuery.data.calendarId ?? "-"}
                </p>
                <p>
                  <strong>Timezone:</strong>{" "}
                  {googleCalendarConnectionQuery.data.professionalTimezone ?? "-"}
                </p>
                <p>
                  <strong>Connected At:</strong>{" "}
                  {googleCalendarConnectionQuery.data.connectedAt !== null
                    ? dateUtilsModule.formatDateTime(googleCalendarConnectionQuery.data.connectedAt)
                    : "-"}
                </p>
              </div>
            ) : null}
            <button
              className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
              disabled={googleSessionMutation.isPending}
              onClick={() => {
                googleSessionMutation.mutate();
              }}
              type="button"
            >
              {googleSessionMutation.isPending ? "Abriendo Google..." : "Conectar Google Calendar"}
            </button>
          </div>

          {/* Onboarding status */}
          <div className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card space-y-3">
            <h3 className="text-base font-semibold text-brand-ink">Estado general</h3>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-slate-700">Estado:</span>
              {statusBadgeElement}
            </div>
            <div className="space-y-1 text-sm text-slate-700">
              <p>
                WhatsApp conectado:{" "}
                {onboardingStatusQuery.data?.whatsappConnected === true ? "si" : "no"}
              </p>
              <p>
                Google Calendar conectado:{" "}
                {onboardingStatusQuery.data?.googleCalendarConnected === true ? "si" : "no"}
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                onClick={() => {
                  void queryClient.invalidateQueries({ queryKey: whatsappConnectionQueryKey });
                  void queryClient.invalidateQueries({
                    queryKey: googleCalendarConnectionQueryKey
                  });
                  void queryClient.invalidateQueries({ queryKey: onboardingStatusQueryKey });
                }}
                type="button"
              >
                Refrescar estado
              </button>
              <button
                className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                disabled={onboardingStatusQuery.data?.ready !== true}
                onClick={() => {
                  void navigate("/inbox");
                }}
                type="button"
              >
                Ir a Inbox
              </button>
            </div>
          </div>
          {onboardingErrorMessage !== null ? (
            <errorBannerModule.ErrorBanner message={onboardingErrorMessage} />
          ) : null}
        </div>
      );
    }

    // ----- RECORDATORIOS -----
    if (activeSection === "recordatorios-config") {
      return (
        <div className="max-w-3xl space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-brand-ink">Recordatorios automáticos</h2>
            <p className="mt-1 text-sm text-slate-500">
              Enviamos un mensaje de WhatsApp al paciente antes de su cita.
            </p>
          </div>
          <div className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
            {reminderSetupState === "loading" ? (
              <p className="text-xs text-slate-400">Cargando…</p>
            ) : null}

            {reminderSetupState === "not_configured" ? (
              <div>
                <button
                  className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={activateAllMutation.isPending}
                  onClick={() => {
                    setActivationStep("disclosure");
                  }}
                  type="button"
                >
                  {activateAllMutation.isPending ? "Activando…" : "Activar recordatorios"}
                </button>
                <p className="mt-2 text-xs text-slate-500">
                  WhatsApp debe aprobar los mensajes antes de empezar a enviarlos. Suele tardar unos
                  minutos.
                </p>
              </div>
            ) : null}

            <billingDisclosureModalModule.BillingDisclosureModal
              isOpen={activationStep === "disclosure"}
              onCancel={() => {
                setActivationStep("idle");
              }}
              onContinue={() => {
                setActivationStep("idle");
                activateAllMutation.mutate();
              }}
            />

            {reminderSetupState === "preparing" ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <p className="text-sm font-medium text-amber-900">Preparando los recordatorios…</p>
                <p className="mt-1 text-xs text-amber-800">
                  WhatsApp está revisando los mensajes. Puede tardar unos minutos. Podés cerrar esta
                  página y volver más tarde.
                </p>
                <button
                  className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={deactivateAllMutation.isPending}
                  onClick={() => {
                    deactivateAllMutation.mutate();
                  }}
                  type="button"
                >
                  {deactivateAllMutation.isPending ? "Cancelando…" : "Cancelar"}
                </button>
              </div>
            ) : null}

            {reminderSetupState === "active" ? (
              <div className="space-y-4">
                <div>
                  <label
                    className="block text-sm font-medium text-slate-700"
                    htmlFor="reminder-days"
                  >
                    ¿Cuántos días antes enviamos el recordatorio?
                  </label>
                  <input
                    className="mt-1 w-24 rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    id="reminder-days"
                    max={7}
                    min={1}
                    onChange={handleDaysBeforeChange}
                    step={1}
                    type="number"
                    value={reminderDaysBefore}
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    Se guarda automáticamente. Entre 1 y 7 días.
                  </p>
                </div>

                <div className="rounded-xl border border-border-subtle bg-slate-50 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                    Así lo recibe el paciente que ya pagó
                  </p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                    Hola Juan García feliz día, te envío la confirmación de la sesión de mañana
                    miércoles 22 de abril a la 1 pm de forma virtual por Google Meet, más detalles
                    en el correo de agendamiento de google calendar.
                  </p>
                </div>

                {paymentStatus?.metaStatus === "APPROVED" ? (
                  <div className="rounded-xl border border-border-subtle bg-slate-50 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Así lo recibe el paciente que aún no pagó
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                      {`Hola Juan García feliz día, recuerda que para la confirmación de tu sesión el lunes 8 de noviembre de 2026 a las 10 am debes realizar el pago por los siguientes canales: ${
                        paymentDetailsText.trim() === ""
                          ? "(configura tus datos de pago abajo)"
                          : paymentDetailsText
                      }. Envía tu comprobante al chat antes de tu sesión.`}
                    </p>
                  </div>
                ) : null}

                <div>
                  <label
                    className="block text-sm font-medium text-slate-700"
                    htmlFor="payment-details"
                  >
                    Datos de pago
                  </label>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Se incluyen en el recordatorio cuando la cita aún no fue pagada. Ej.: Nequi,
                    Bancolombia, un link.
                  </p>
                  <textarea
                    className="mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
                    id="payment-details"
                    onBlur={() => {
                      settingsMutation.mutate();
                    }}
                    onChange={(e) => {
                      setPaymentDetailsText(e.target.value);
                    }}
                    placeholder="Nequi: 300 123 4567&#10;Bancolombia ahorros 1234-5678-9012"
                    rows={3}
                    value={paymentDetailsText}
                  />
                  <p className="mt-1 text-xs text-slate-500">Se guarda cuando sales del campo.</p>
                </div>

                {paymentStatus?.metaStatus === "REJECTED" ||
                paymentStatus?.metaStatus === "DISABLED" ? (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                    <p className="font-medium">
                      No podemos recordarle a quien aún no pagó su cita.
                    </p>
                    <p className="mt-1 text-xs text-amber-800">
                      WhatsApp rechazó ese mensaje.
                      {paymentStatus.rejectionReason !== null
                        ? ` Motivo: ${paymentStatus.rejectionReason}`
                        : ""}
                    </p>
                    <button
                      className="mt-3 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={retryKindMutation.isPending}
                      onClick={() => {
                        retryKindMutation.mutate("PAYMENT");
                      }}
                      type="button"
                    >
                      {retryKindMutation.isPending ? "Reintentando…" : "Reintentar"}
                    </button>
                  </div>
                ) : null}

                <div>
                  <button
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={deactivateAllMutation.isPending}
                    onClick={() => {
                      deactivateAllMutation.mutate();
                    }}
                    type="button"
                  >
                    {deactivateAllMutation.isPending ? "Desactivando…" : "Desactivar recordatorios"}
                  </button>
                </div>
              </div>
            ) : null}

            {reminderSetupState === "broken" ? (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
                <p className="font-medium">No pudimos activar los recordatorios.</p>
                <p className="mt-1 text-xs text-red-800">
                  WhatsApp rechazó el mensaje principal.
                  {attendanceStatus?.rejectionReason !== null &&
                  attendanceStatus?.rejectionReason !== undefined
                    ? ` Motivo: ${attendanceStatus.rejectionReason}`
                    : ""}
                </p>
                <div className="mt-3 flex gap-2">
                  <button
                    className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={retryKindMutation.isPending}
                    onClick={() => {
                      retryKindMutation.mutate("ATTENDANCE");
                    }}
                    type="button"
                  >
                    {retryKindMutation.isPending ? "Reintentando…" : "Reintentar"}
                  </button>
                  <button
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={deactivateAllMutation.isPending}
                    onClick={() => {
                      deactivateAllMutation.mutate();
                    }}
                    type="button"
                  >
                    {deactivateAllMutation.isPending ? "Desactivando…" : "Desactivar"}
                  </button>
                </div>
              </div>
            ) : null}

            {settingsErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner className="mt-3" message={settingsErrorMessage} />
            ) : null}
          </div>
        </div>
      );
    }

    if (activeSection === "plantillas") {
      return (
        <div className="max-w-4xl space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-brand-ink">Plantillas de mensajes</h2>
            <p className="mt-1 text-sm text-slate-500">
              Mensajes oficiales de WhatsApp aprobados por Meta.
            </p>
          </div>
          <plantillasSectionModule.PlantillasSection />
        </div>
      );
    }

    // ----- AVANZADAS -----
    if (activeSection === "momento-cobro") {
      return (
        <div className="max-w-3xl space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-brand-ink">Momento del cobro</h2>
            <p className="mt-1 text-sm text-slate-500">
              Define si el bot exige pago antes de confirmar la cita o si el cobro se hace en
              persona al terminar la sesión.
            </p>
          </div>
          <div className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
            <fieldset className="space-y-3">
              <legend className="sr-only">Momento del cobro</legend>
              <label className="flex cursor-pointer items-start gap-3">
                <input
                  checked={paymentTiming === "BEFORE_SESSION"}
                  className="mt-0.5 h-4 w-4 cursor-pointer accent-brand-teal"
                  id="payment-timing-before"
                  name="payment-timing"
                  onChange={() => {
                    handlePaymentTimingChange("BEFORE_SESSION");
                  }}
                  type="radio"
                  value="BEFORE_SESSION"
                />
                <span className="flex flex-col">
                  <span className="text-sm font-medium text-slate-700">
                    Antes de la sesión (pago anticipado)
                  </span>
                  <span className="mt-0.5 text-xs text-slate-500">
                    El bot exige comprobante de pago para confirmar la cita y envía recordatorios de
                    pago a quienes aún no pagaron.
                  </span>
                </span>
              </label>
              <label className="flex cursor-pointer items-start gap-3">
                <input
                  checked={paymentTiming === "IN_PERSON"}
                  className="mt-0.5 h-4 w-4 cursor-pointer accent-brand-teal"
                  id="payment-timing-in-person"
                  name="payment-timing"
                  onChange={() => {
                    handlePaymentTimingChange("IN_PERSON");
                  }}
                  type="radio"
                  value="IN_PERSON"
                />
                <span className="flex flex-col">
                  <span className="text-sm font-medium text-slate-700">
                    Al terminar la sesión (cobro en persona)
                  </span>
                  <span className="mt-0.5 text-xs text-slate-500">
                    El bot confirma la cita sin pedir comprobante de pago. Los recordatorios solo
                    notifican la asistencia — nunca cobros.
                  </span>
                </span>
              </label>
            </fieldset>
            <p className="mt-3 text-xs text-slate-500">Se guarda automáticamente.</p>
            {settingsErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner className="mt-3" message={settingsErrorMessage} />
            ) : null}
          </div>
        </div>
      );
    }

    if (activeSection === "delay") {
      return (
        <div className="max-w-3xl space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-brand-ink">Delay de respuesta</h2>
            <p className="mt-1 text-sm text-slate-500">
              Tiempo de espera después de procesar un mensaje antes de responder. Permite capturar
              mensajes adicionales enviados en ráfaga. 0 = sin espera.
            </p>
          </div>
          <div className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
            <label className="block text-sm font-medium text-slate-700" htmlFor="debounce-delay">
              Segundos
            </label>
            <input
              className="mt-1 w-24 rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
              id="debounce-delay"
              max={30}
              min={0}
              onChange={handleDebounceDelayChange}
              step={1}
              type="number"
              value={debounceDelay}
            />
            <p className="mt-1 text-xs text-slate-500">
              Se guarda automáticamente. Entre 0 y 30 segundos.
            </p>
            {settingsErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner className="mt-3" message={settingsErrorMessage} />
            ) : null}
          </div>

          {/* Vista previa del prompt generado (solo dev) */}
          {import.meta.env.DEV ? (
            <div className="rounded-2xl border border-border-subtle bg-white p-6 shadow-card">
              <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
                Vista previa del prompt generado (solo en dev)
              </h4>
              <pre className="max-h-96 overflow-auto rounded-lg bg-slate-50 p-4 text-xs text-slate-600 whitespace-pre-wrap">
                {promptQuery.data?.systemPrompt ?? "(cargando...)"}
              </pre>
            </div>
          ) : null}
        </div>
      );
    }

    // Fallback (should never reach)
    return <div />;
  }

  // -------------------------------------------------------------------
  // Sidebar label for mobile header
  // -------------------------------------------------------------------
  const activeSectionLabel =
    SIDEBAR_GROUPS.flatMap((g) => g.items).find((i) => i.id === activeSection)?.label ?? "";

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------
  return (
    <appShellModule.AppShell>
      {/* OAuth callback banners */}
      {metaOAuthStatus !== null || googleOAuthStatus !== null ? (
        <section className="mb-4 space-y-2">
          {metaOAuthStatus === "connected" ? (
            <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              WhatsApp conectado correctamente.
            </div>
          ) : null}
          {googleOAuthStatus === "connected" ? (
            <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              Google Calendar conectado correctamente.
            </div>
          ) : null}
          {metaOAuthStatus === "error" || googleOAuthStatus === "error" ? (
            <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
              Error en callback OAuth.
              {callbackCode !== null ? ` status=${callbackCode}.` : ""}
              {callbackReason !== null ? ` ${callbackReason}` : ""}
            </div>
          ) : null}
        </section>
      ) : null}

      {/* Master-detail layout */}
      <div className="md:grid md:grid-cols-[220px_1fr] md:gap-8">
        {/* ---- Sidebar (always visible on md+; list view on mobile) ---- */}
        <aside className={["md:block", mobileView === "list" ? "block" : "hidden"].join(" ")}>
          <settingsSidebarModule.SettingsSidebar
            activeItem={activeSection}
            groups={SIDEBAR_GROUPS}
            onSelect={handleSelectSection}
          />
        </aside>

        {/* ---- Detail pane (always visible on md+; detail view on mobile) ---- */}
        <main className={["md:block", mobileView === "detail" ? "block" : "hidden"].join(" ")}>
          {/* Mobile: back button */}
          <button
            className="mb-4 flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700 md:hidden"
            onClick={() => {
              setMobileView("list");
            }}
            type="button"
          >
            <svg
              aria-hidden="true"
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {activeSectionLabel}
          </button>

          {renderDetail()}
        </main>
      </div>
    </appShellModule.AppShell>
  );
}

import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";
import * as reactRouterDomModule from "react-router-dom";

import type * as agentModel from "@domain/models/agent";

type PaymentTiming = agentModel.PaymentTiming;
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

// ---------------------------------------------------------------------------
// Section routing
// ---------------------------------------------------------------------------
type SectionId =
  | "consultorio"
  | "identidad"
  | "servicios"
  | "medios-pago"
  | "prompt-preview"
  | "whatsapp"
  | "google-calendar"
  | "recordatorios-config"
  | "plantillas"
  | "momento-cobro"
  | "delay";

// Heroicon outline 24x24 paths for each sidebar group.
const ICON_USER =
  "M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z";
const ICON_SPARKLES =
  "M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.847.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z";
const ICON_LINK =
  "M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244";
const ICON_BELL =
  "M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0";
const ICON_COG =
  "M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281zM15 12a3 3 0 11-6 0 3 3 0 016 0z";

const SIDEBAR_GROUPS: settingsSidebarModule.SidebarGroup[] = [
  // 1. CONEXIONES — primero porque sin esto nada funciona (onboarding paso 1).
  {
    id: "conexiones",
    label: "Conexiones",
    iconPath: ICON_LINK,
    items: [
      { id: "whatsapp", label: "WhatsApp Business" },
      { id: "google-calendar", label: "Google Calendar" }
    ]
  },
  // 2. AGENTE — corazón del producto, lo más editado día a día.
  {
    id: "agente",
    label: "Agente",
    iconPath: ICON_SPARKLES,
    items: [
      { id: "identidad", label: "Identidad del asistente" },
      { id: "servicios", label: "Servicios y práctica" },
      { id: "medios-pago", label: "Medios de pago" },
      // Dev-only: read-only preview of the generated XML prompt.
      ...(import.meta.env.DEV
        ? [{ id: "prompt-preview", label: "Vista previa del prompt (dev)" }]
        : [])
    ]
  },
  // 3. GENERAL — datos del consultorio (input para Calendar y mensajes).
  {
    id: "general",
    label: "General",
    iconPath: ICON_USER,
    items: [{ id: "consultorio", label: "Datos del consultorio" }]
  },
  // 4. RECORDATORIOS — feature secundaria, depende de payment_methods de AGENTE.
  {
    id: "recordatorios",
    label: "Recordatorios",
    iconPath: ICON_BELL,
    items: [
      { id: "recordatorios-config", label: "Activación y configuración" },
      { id: "plantillas", label: "Plantillas de mensajes" }
    ]
  },
  {
    id: "avanzadas",
    label: "Avanzadas",
    iconPath: ICON_COG,
    items: [
      { id: "momento-cobro", label: "Momento del cobro" },
      { id: "delay", label: "Delay de respuesta" }
    ]
  }
];

const ALL_SECTION_IDS = new Set<string>(SIDEBAR_GROUPS.flatMap((g) => g.items.map((i) => i.id)));

const DEFAULT_SECTION: SectionId = "identidad";

/** Resolves legacy ?tab= values and new ?section= values to a SectionId. */
function resolveSectionFromParams(params: URLSearchParams): SectionId {
  const section = params.get("section");
  if (section !== null && ALL_SECTION_IDS.has(section)) return section as SectionId;
  // Backward-compat: legacy tab param
  const tab = params.get("tab");
  if (tab === "general" || tab === "agente") return "identidad";
  if (tab === "conexiones") return "whatsapp";
  if (tab === "recordatorios" || tab === "ajustes") return "recordatorios-config";
  return DEFAULT_SECTION;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
/**
 * Mirror of `payment_methods_formatter.format_payment_methods_for_template`
 * (backend). Renders the structured payment methods as a single inline string
 * suitable for the WhatsApp reminder template.
 */
function formatPaymentMethodsInline(methods: agentModel.PaymentMethod[]): string {
  if (methods.length === 0) return "";
  const rendered = methods
    .map((m) => {
      const parts: string[] = [];
      if (m.methodName !== "" && m.instructions !== null && m.instructions !== "") {
        parts.push(`${m.methodName}: ${m.instructions}`);
      } else if (m.methodName !== "") {
        parts.push(m.methodName);
      } else if (m.instructions !== null && m.instructions !== "") {
        parts.push(m.instructions);
      }
      if (parts.length === 0) return "";
      if (m.holder !== null && m.holder !== "") {
        parts.push(`a nombre de ${m.holder}`);
      }
      return parts.join(" · ");
    })
    .filter((s) => s !== "");
  return rendered.join(" · ");
}

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

  // Same key as ProfessionalProfileForm so the cache is shared. Used here to
  // derive the "Datos de pago" preview from the structured payment_methods.
  const professionalProfileQuery = reactQueryModule.useQuery({
    queryKey: ["professional-profile"] as const,
    queryFn: () => appContainer.agentUseCase.getProfessionalProfile()
  });

  const [debounceDelay, setDebounceDelay] = reactModule.useState(0);
  const [reminderDaysBefore, setReminderDaysBefore] = reactModule.useState(1);
  // Legacy free-text payment details. No longer edited from the UI; we keep
  // the state in sync with the persisted value so the save mutations pass it
  // through unchanged. The reminder section now displays a derived preview
  // from `paymentMethods` instead.
  const [paymentDetailsText, setPaymentDetailsText] = reactModule.useState("");
  const derivedPaymentDetails = formatPaymentMethodsInline(
    professionalProfileQuery.data?.paymentMethods ?? []
  );
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
        assistantEnabled: fresh.assistantEnabled,
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
        assistantEnabled: fresh.assistantEnabled,
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
        assistantEnabled: settingsQuery.data?.assistantEnabled ?? true,
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
        assistantEnabled: settingsQuery.data?.assistantEnabled ?? true,
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
        assistantEnabled: settingsQuery.data?.assistantEnabled ?? true,
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
  // Tenant.professional_name is no longer edited from this UI: the calendar
  // event title now reads from AgentProfile.identity (title + name combined).
  // The legacy field stays in the backend as a fallback for tenants that
  // haven't migrated to the form yet.

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
    if (activeSection === "consultorio") {
      return (
        <div className="max-w-3xl space-y-6">
          <div>
            <h2 className="text-xl font-semibold font-display text-brand-ink">
              Datos del consultorio
            </h2>
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
                className="mt-1 w-full rounded-xl bg-surface-low border-none px-3 py-2.5 text-sm transition-colors placeholder:text-sidebar-text/50 focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60"
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
                className="mt-1 w-full rounded-xl bg-surface-low border-none px-3 py-2.5 text-sm transition-colors placeholder:text-sidebar-text/50 focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60"
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
            <h2 className="text-xl font-semibold font-display text-brand-ink">WhatsApp Business</h2>
            <p className="mt-1 text-sm text-slate-500">
              Conecta la linea de negocio para recibir y responder chats.
            </p>
          </div>
          <div className="rounded-2xl bg-surface-white p-6 shadow-card space-y-4">
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
                className="mt-1 block w-full rounded-xl bg-surface-low border-none px-3 py-2.5 text-sm placeholder:text-sidebar-text/50 focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
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
            <h2 className="text-xl font-semibold font-display text-brand-ink">Google Calendar</h2>
            <p className="mt-1 text-sm text-slate-500">
              Conecta el calendario principal del profesional para disponibilidad y agenda.
            </p>
          </div>
          <div className="rounded-2xl bg-surface-white p-6 shadow-card space-y-4">
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
          <div className="rounded-2xl bg-surface-white p-6 shadow-card space-y-3">
            <h3 className="text-base font-semibold font-display text-brand-ink">Estado general</h3>
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
            <h2 className="text-xl font-semibold font-display text-brand-ink">
              Recordatorios automáticos
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Enviamos un mensaje de WhatsApp al paciente antes de su cita.
            </p>
          </div>
          <div className="rounded-2xl bg-surface-white p-6 shadow-card">
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
                    className="mt-1 w-24 rounded-xl bg-surface-low border-none px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-teal/20"
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

                <div className="rounded-xl bg-surface-low p-4">
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
                  <div className="rounded-xl bg-surface-low p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      Así lo recibe el paciente que aún no pagó
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                      {`Hola Juan García feliz día, recuerda que para la confirmación de tu sesión el lunes 8 de noviembre de 2026 a las 10 am debes realizar el pago por los siguientes canales: ${
                        derivedPaymentDetails === ""
                          ? "(configura los métodos en Agente → Medios de pago)"
                          : derivedPaymentDetails
                      }. Envía tu comprobante al chat antes de tu sesión.`}
                    </p>
                  </div>
                ) : null}

                <div className="rounded-xl bg-surface-low p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                    Datos de pago
                  </p>
                  <p className="mt-1.5 text-xs text-slate-500">
                    Se toman automáticamente de{" "}
                    <button
                      className="text-brand-teal underline-offset-2 hover:underline"
                      onClick={() => {
                        setActiveSection("medios-pago");
                      }}
                      type="button"
                    >
                      Agente → Medios de pago
                    </button>
                    . Edítalos ahí para que se actualicen aquí.
                  </p>
                  <p className="mt-2 text-sm text-slate-700">
                    {derivedPaymentDetails === "" ? (
                      <span className="italic text-slate-400">
                        Aún no hay métodos de pago configurados.
                      </span>
                    ) : (
                      derivedPaymentDetails
                    )}
                  </p>
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
            <h2 className="text-xl font-semibold font-display text-brand-ink">
              Plantillas de mensajes
            </h2>
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
            <h2 className="text-xl font-semibold font-display text-brand-ink">Momento del cobro</h2>
            <p className="mt-1 text-sm text-slate-500">
              Define si el bot exige pago antes de confirmar la cita o si el cobro se hace en
              persona al terminar la sesión.
            </p>
          </div>
          <div className="rounded-2xl bg-surface-white p-6 shadow-card">
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
                  checked={paymentTiming === "AFTER_SESSION"}
                  className="mt-0.5 h-4 w-4 cursor-pointer accent-brand-teal"
                  id="payment-timing-after-session"
                  name="payment-timing"
                  onChange={() => {
                    handlePaymentTimingChange("AFTER_SESSION");
                  }}
                  type="radio"
                  value="AFTER_SESSION"
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
            <h2 className="text-xl font-semibold font-display text-brand-ink">
              Delay de respuesta
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Tiempo de espera después de procesar un mensaje antes de responder. Permite capturar
              mensajes adicionales enviados en ráfaga. 0 = sin espera.
            </p>
          </div>
          <div className="rounded-2xl bg-surface-white p-6 shadow-card">
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
        </div>
      );
    }

    if (activeSection === "prompt-preview" && import.meta.env.DEV) {
      return (
        <div className="max-w-5xl space-y-6">
          <div>
            <h2 className="text-xl font-semibold font-display text-brand-ink">
              Vista previa del prompt generado
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Solo visible en dev. Es el XML producido por el renderer a partir de los campos de
              Identidad, Servicios y Medios de pago. Read-only.
            </p>
          </div>
          <div className="rounded-2xl bg-surface-white p-6 shadow-card">
            <pre className="max-h-[70vh] overflow-auto rounded-lg bg-slate-50 p-4 text-xs whitespace-pre-wrap text-slate-700">
              {promptQuery.data?.systemPrompt ?? "(cargando...)"}
            </pre>
          </div>
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

import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as sectionCardModule from "@adapters/inbound/react/components/form/SectionCard";
import * as identitySectionModule from "@adapters/inbound/react/components/ProfessionalProfileForm/IdentitySection";
import * as servicesAndPracticeSectionModule from "@adapters/inbound/react/components/ProfessionalProfileForm/ServicesAndPracticeSection";
import * as paymentMethodsSectionModule from "@adapters/inbound/react/components/ProfessionalProfileForm/PaymentMethodsSection";
import * as uiErrorModule from "@shared/http/ui_error";
import type * as agentModel from "@domain/models/agent";

const professionalProfileQueryKey = ["professional-profile"] as const;

const EMPTY_IDENTITY: agentModel.AssistantIdentity = {
  assistantName: null,
  professionalTitle: null,
  professionalName: null,
  professionalAddressTerm: null,
  mainCity: null,
  tone: null,
  languages: []
};

const EMPTY_PROFESSIONAL_CONTEXT: agentModel.ProfessionalContext = {
  approach: null,
  commonTopics: [],
  servicesNotOffered: [],
  coverageNotes: null
};

function buildEmptyProfile(): agentModel.UpdateProfessionalProfileInput {
  return {
    identity: EMPTY_IDENTITY,
    professionalContext: EMPTY_PROFESSIONAL_CONTEXT,
    services: [],
    paymentMethods: []
  };
}

function buildIdentityPreview(identity: agentModel.AssistantIdentity | null): string {
  if (identity === null) return "Sin configurar";
  const parts: string[] = [];
  if (identity.assistantName !== null && identity.assistantName.trim() !== "") {
    parts.push(identity.assistantName.trim());
  }
  if (identity.professionalTitle !== null && identity.professionalTitle.trim() !== "") {
    parts.push(identity.professionalTitle.trim());
  }
  if (identity.mainCity !== null && identity.mainCity.trim() !== "") {
    parts.push(identity.mainCity.trim());
  }
  if (parts.length === 0) return "Sin configurar";
  return parts.join(" · ");
}

function buildServicesPreview(
  services: agentModel.ServiceOffering[],
  professionalContext: agentModel.ProfessionalContext | null
): string {
  const totalTopics = professionalContext?.commonTopics.length ?? 0;
  if (services.length === 0 && totalTopics === 0) {
    return "Sin configurar";
  }
  const parts: string[] = [];
  parts.push(`${services.length} ${services.length === 1 ? "servicio" : "servicios"}`);
  if (totalTopics > 0) {
    parts.push(`${totalTopics} ${totalTopics === 1 ? "tema" : "temas"}`);
  }
  return parts.join(" · ");
}

function buildPaymentMethodsPreview(methods: agentModel.PaymentMethod[]): string {
  if (methods.length === 0) return "Sin configurar";
  return methods
    .map((m) => `${m.methodName} (${m.currency})`)
    .slice(0, 3)
    .join(" · ");
}

function profileToInput(
  profile: agentModel.ProfessionalProfile
): agentModel.UpdateProfessionalProfileInput {
  return {
    identity: profile.identity ?? EMPTY_IDENTITY,
    professionalContext: profile.professionalContext ?? EMPTY_PROFESSIONAL_CONTEXT,
    services: profile.services,
    paymentMethods: profile.paymentMethods
  };
}

export function ProfessionalProfileForm() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const profileQuery = reactQueryModule.useQuery({
    queryKey: professionalProfileQueryKey,
    queryFn: () => appContainer.agentUseCase.getProfessionalProfile()
  });

  const [draft, setDraft] =
    reactModule.useState<agentModel.UpdateProfessionalProfileInput>(buildEmptyProfile());
  const [successMessage, setSuccessMessage] = reactModule.useState<string | null>(null);
  const [isDirty, setIsDirty] = reactModule.useState(false);

  reactModule.useEffect(() => {
    if (profileQuery.data !== undefined) {
      setDraft(profileToInput(profileQuery.data));
      setIsDirty(false);
    }
  }, [profileQuery.data]);

  const updateDraft = (next: agentModel.UpdateProfessionalProfileInput) => {
    setDraft(next);
    setIsDirty(true);
    setSuccessMessage(null);
  };

  const saveMutation = reactQueryModule.useMutation({
    mutationFn: () => appContainer.agentUseCase.updateProfessionalProfile(draft),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: professionalProfileQueryKey });
      setSuccessMessage("Perfil guardado correctamente.");
      setIsDirty(false);
    }
  });

  const errorMessage = uiErrorModule.resolveUiErrorMessage([
    saveMutation.error,
    profileQuery.error
  ]);

  const isLoading = profileQuery.isLoading;
  const isSaving = saveMutation.isPending;

  return (
    <div className="max-w-3xl space-y-4">
      {/* Identidad */}
      <sectionCardModule.SectionCard
        collapsible
        defaultOpen={false}
        previewWhenCollapsed={buildIdentityPreview(draft.identity)}
        storageKey="cfg.section.identity"
        subtitle="Configura como se presenta el asistente y que tono usa."
        title="Identidad del asistente"
      >
        <identitySectionModule.IdentitySection
          disabled={isLoading || isSaving}
          onChange={(nextIdentity) => {
            updateDraft({ ...draft, identity: nextIdentity });
          }}
          value={draft.identity ?? EMPTY_IDENTITY}
        />
      </sectionCardModule.SectionCard>

      {/* Servicios y practica */}
      <sectionCardModule.SectionCard
        collapsible
        defaultOpen={false}
        previewWhenCollapsed={buildServicesPreview(draft.services, draft.professionalContext)}
        storageKey="cfg.section.services"
        subtitle="Contexto profesional, horarios y servicios ofrecidos."
        title="Servicios y práctica"
      >
        <servicesAndPracticeSectionModule.ServicesAndPracticeSection
          disabled={isLoading || isSaving}
          onContextChange={(nextCtx) => {
            updateDraft({ ...draft, professionalContext: nextCtx });
          }}
          onServicesChange={(next) => {
            updateDraft({ ...draft, services: next });
          }}
          professionalContext={draft.professionalContext ?? EMPTY_PROFESSIONAL_CONTEXT}
          services={draft.services}
        />
      </sectionCardModule.SectionCard>

      {/* Medios de pago */}
      <sectionCardModule.SectionCard
        collapsible
        defaultOpen={false}
        previewWhenCollapsed={buildPaymentMethodsPreview(draft.paymentMethods)}
        storageKey="cfg.section.payments"
        subtitle="Configura los canales de pago que el asistente puede informar a los pacientes."
        title="Medios de pago"
      >
        <paymentMethodsSectionModule.PaymentMethodsSection
          disabled={isLoading || isSaving}
          onChange={(next) => {
            updateDraft({ ...draft, paymentMethods: next });
          }}
          value={draft.paymentMethods}
        />
      </sectionCardModule.SectionCard>

      {/* Banners */}
      {successMessage !== null ? (
        <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {successMessage}
        </div>
      ) : null}

      {errorMessage !== null ? (
        <errorBannerModule.ErrorBanner className="mt-3" message={errorMessage} />
      ) : null}

      {/* Guardar */}
      <div className="flex justify-end">
        <button
          className="rounded-lg bg-brand-teal px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isLoading || isSaving || !isDirty}
          onClick={() => {
            saveMutation.mutate();
          }}
          type="button"
        >
          {isSaving ? "Guardando..." : "Guardar"}
        </button>
      </div>
    </div>
  );
}

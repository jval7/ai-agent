import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
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

export function AgentPaymentsDetailSection() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const profileQuery = reactQueryModule.useQuery({
    queryKey: professionalProfileQueryKey,
    queryFn: () => appContainer.agentUseCase.getProfessionalProfile()
  });

  const [paymentMethods, setPaymentMethods] = reactModule.useState<agentModel.PaymentMethod[]>([]);
  const [successMessage, setSuccessMessage] = reactModule.useState<string | null>(null);
  const [isDirty, setIsDirty] = reactModule.useState(false);

  reactModule.useEffect(() => {
    if (profileQuery.data !== undefined) {
      setPaymentMethods(profileQuery.data.paymentMethods);
      setIsDirty(false);
    }
  }, [profileQuery.data]);

  const saveMutation = reactQueryModule.useMutation({
    mutationFn: () =>
      appContainer.agentUseCase.updateProfessionalProfile({
        identity: profileQuery.data?.identity ?? EMPTY_IDENTITY,
        professionalContext: profileQuery.data?.professionalContext ?? EMPTY_PROFESSIONAL_CONTEXT,
        services: profileQuery.data?.services ?? [],
        presencialSchedule: profileQuery.data?.presencialSchedule ?? [],
        virtualSchedule: profileQuery.data?.virtualSchedule ?? [],
        paymentMethods
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: professionalProfileQueryKey });
      setSuccessMessage("Medios de pago guardados correctamente.");
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
    <div className="max-w-3xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold font-display text-brand-ink">Medios de pago</h2>
        <p className="mt-1 text-sm text-slate-500">
          Configura los canales de pago que el asistente puede informar a los pacientes.
        </p>
      </div>

      <paymentMethodsSectionModule.PaymentMethodsSection
        disabled={isLoading || isSaving}
        onChange={(next) => {
          setPaymentMethods(next);
          setIsDirty(true);
          setSuccessMessage(null);
        }}
        value={paymentMethods}
      />

      {successMessage !== null ? (
        <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {successMessage}
        </div>
      ) : null}

      {errorMessage !== null ? (
        <errorBannerModule.ErrorBanner className="mt-3" message={errorMessage} />
      ) : null}

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

import type * as agentModel from "@domain/models/agent";
import * as chipListModule from "@adapters/inbound/react/components/form/ChipList";
import * as dynamicListModule from "@adapters/inbound/react/components/form/DynamicList";
import * as formFieldModule from "@adapters/inbound/react/components/form/FormField";
import * as serviceOfferingItemModule from "@adapters/inbound/react/components/ProfessionalProfileForm/ServiceOfferingItem";

const TEXTAREA_CLASS =
  "mt-1 w-full rounded-xl bg-surface-low border-none px-3 py-2.5 text-sm transition-colors placeholder:text-sidebar-text/50 focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60";

function newServiceOffering(): agentModel.ServiceOffering {
  return {
    name: null,
    description: null,
    modalities: [],
    targetPatients: ["NEW", "RETURNING"],
    tariffs: [],
    enabled: true
  };
}

interface ServicesAndPracticeSectionProps {
  professionalContext: agentModel.ProfessionalContext;
  onContextChange: (next: agentModel.ProfessionalContext) => void;
  services: agentModel.ServiceOffering[];
  onServicesChange: (next: agentModel.ServiceOffering[]) => void;
  disabled: boolean;
}

export function ServicesAndPracticeSection(props: ServicesAndPracticeSectionProps) {
  const { professionalContext: ctx, onContextChange, disabled } = props;

  const handleContextField =
    (field: keyof agentModel.ProfessionalContext) =>
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const raw = event.target.value;
      onContextChange({ ...ctx, [field]: raw === "" ? null : raw });
    };

  return (
    <div className="space-y-8">
      {/* Contexto general */}
      <div className="space-y-4">
        <h4 className="text-base font-semibold font-display text-brand-ink">Contexto general</h4>

        <formFieldModule.FormField
          helperText="Descripcion del enfoque profesional o modelo de trabajo."
          htmlFor="approach"
          label="Enfoque / approach"
        >
          <textarea
            className={TEXTAREA_CLASS}
            disabled={disabled}
            id="approach"
            onChange={handleContextField("approach")}
            placeholder="Ej. Enfoque humanista centrado en la persona..."
            rows={3}
            value={ctx.approach ?? ""}
          />
        </formFieldModule.FormField>

        <formFieldModule.FormField
          helperText="Temas frecuentes que el profesional atiende."
          htmlFor="common-topics-input"
          label="Temas comunes"
        >
          <chipListModule.ChipList
            disabled={disabled}
            items={ctx.commonTopics}
            onChange={(next) => {
              onContextChange({ ...ctx, commonTopics: next });
            }}
            placeholder="Ej. ansiedad, duelo"
          />
        </formFieldModule.FormField>

        <formFieldModule.FormField
          helperText="Servicios que el profesional NO ofrece."
          htmlFor="services-not-offered-input"
          label="Servicios que no se ofrecen"
        >
          <chipListModule.ChipList
            disabled={disabled}
            items={ctx.servicesNotOffered}
            onChange={(next) => {
              onContextChange({ ...ctx, servicesNotOffered: next });
            }}
            placeholder="Ej. terapia de pareja"
          />
        </formFieldModule.FormField>

        <formFieldModule.FormField
          helperText="Notas adicionales sobre cobertura geografica u otras restricciones."
          htmlFor="coverage-notes"
          label="Notas de cobertura"
        >
          <textarea
            className={TEXTAREA_CLASS}
            disabled={disabled}
            id="coverage-notes"
            onChange={handleContextField("coverageNotes")}
            placeholder="Ej. Atiende pacientes en Colombia y en el exterior via videollamada."
            rows={2}
            value={ctx.coverageNotes ?? ""}
          />
        </formFieldModule.FormField>
      </div>

      {/* Servicios */}
      <div className="space-y-4 pt-6">
        <h4 className="text-base font-semibold font-display text-brand-ink">Servicios</h4>
        <dynamicListModule.DynamicList
          addLabel="Agregar servicio"
          emptyMessage="No hay servicios configurados."
          items={props.services}
          newItemFactory={newServiceOffering}
          onChange={props.onServicesChange}
          renderItem={(item, _i, onItemChange) => (
            <serviceOfferingItemModule.ServiceOfferingItem
              disabled={disabled}
              onChange={onItemChange}
              value={item}
            />
          )}
        />
      </div>
    </div>
  );
}

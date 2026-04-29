import type * as agentModel from "@domain/models/agent";
import * as chipListModule from "@adapters/inbound/react/components/form/ChipList";
import * as formFieldModule from "@adapters/inbound/react/components/form/FormField";

const INPUT_CLASS =
  "mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal disabled:cursor-not-allowed disabled:opacity-60";
const TEXTAREA_CLASS =
  "mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60";

interface IdentitySectionProps {
  value: agentModel.AssistantIdentity;
  onChange: (next: agentModel.AssistantIdentity) => void;
  disabled: boolean;
}

export function IdentitySection(props: IdentitySectionProps) {
  const { value, onChange, disabled } = props;

  const handleField =
    (field: keyof agentModel.AssistantIdentity) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      onChange({ ...value, [field]: event.target.value === "" ? null : event.target.value });
    };

  return (
    <div className="space-y-4">
      <formFieldModule.FormField
        helperText='Nombre con el que el asistente se presenta. Ej.: "Sofia"'
        htmlFor="assistant-name"
        label="Nombre del asistente"
      >
        <input
          className={INPUT_CLASS}
          disabled={disabled}
          id="assistant-name"
          onChange={handleField("assistantName")}
          placeholder="Ej. Sofia"
          type="text"
          value={value.assistantName ?? ""}
        />
      </formFieldModule.FormField>

      <formFieldModule.FormField
        helperText='Titulo profesional. Ej.: "Psicóloga", "Nutricionista"'
        htmlFor="professional-title"
        label="Titulo profesional"
      >
        <input
          className={INPUT_CLASS}
          disabled={disabled}
          id="professional-title"
          onChange={handleField("professionalTitle")}
          placeholder="Ej. Psicóloga"
          type="text"
          value={value.professionalTitle ?? ""}
        />
      </formFieldModule.FormField>

      <formFieldModule.FormField
        helperText='Como el asistente llama al profesional. Ej.: "la Doc", "el Lic."'
        htmlFor="professional-address-term"
        label="Como se le llama al profesional"
      >
        <input
          className={INPUT_CLASS}
          disabled={disabled}
          id="professional-address-term"
          onChange={handleField("professionalAddressTerm")}
          placeholder="Ej. la Doc"
          type="text"
          value={value.professionalAddressTerm ?? ""}
        />
      </formFieldModule.FormField>

      <formFieldModule.FormField
        helperText="Ciudad principal donde opera el profesional."
        htmlFor="main-city"
        label="Ciudad principal"
      >
        <input
          className={INPUT_CLASS}
          disabled={disabled}
          id="main-city"
          onChange={handleField("mainCity")}
          placeholder="Ej. Medellín"
          type="text"
          value={value.mainCity ?? ""}
        />
      </formFieldModule.FormField>

      <formFieldModule.FormField
        helperText="Descripcion del tono de comunicacion del asistente."
        htmlFor="tone"
        label="Tono de comunicacion"
      >
        <textarea
          className={TEXTAREA_CLASS}
          disabled={disabled}
          id="tone"
          onChange={handleField("tone")}
          placeholder="Ej. Profesional y cálida, empática con los pacientes."
          rows={3}
          value={value.tone ?? ""}
        />
      </formFieldModule.FormField>

      <formFieldModule.FormField
        helperText="Idiomas en los que puede atender el asistente."
        htmlFor="languages-input"
        label="Idiomas"
      >
        <chipListModule.ChipList
          disabled={disabled}
          items={value.languages}
          onChange={(next) => {
            onChange({ ...value, languages: next });
          }}
          placeholder="Ej. español, inglés"
        />
      </formFieldModule.FormField>
    </div>
  );
}

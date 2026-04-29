import type * as agentModel from "@domain/models/agent";
import * as collapsibleCardModule from "@adapters/inbound/react/components/form/CollapsibleCard";
import * as currencyInputModule from "@adapters/inbound/react/components/form/CurrencyInput";
import * as dynamicListModule from "@adapters/inbound/react/components/form/DynamicList";
import * as formFieldModule from "@adapters/inbound/react/components/form/FormField";

const INPUT_CLASS =
  "mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal disabled:cursor-not-allowed disabled:opacity-60";
const TEXTAREA_CLASS =
  "mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60";

function newTariffOption(): agentModel.TariffOption {
  return { label: "", amount: 0, currency: "COP", description: null };
}

function formatTariffSummary(t: agentModel.TariffOption): string {
  const label = t.label.trim() === "" ? "Tarifa nueva" : t.label;
  if (t.amount === 0) return label;
  const formatted = t.amount.toLocaleString("es-CO");
  return `${label} · ${formatted} ${t.currency}`;
}

interface TariffItemProps {
  value: agentModel.TariffOption;
  onChange: (next: agentModel.TariffOption) => void;
  disabled: boolean;
}

function TariffItem(props: TariffItemProps) {
  const { value, onChange, disabled } = props;
  return (
    <collapsibleCardModule.CollapsibleCard
      className="border border-slate-200/70 shadow-none"
      summary={
        <span className="text-sm text-slate-700">
          <span className="font-medium">{formatTariffSummary(value)}</span>
        </span>
      }
    >
      <div className="space-y-3">
        <formFieldModule.FormField htmlFor="" label="Etiqueta">
          <input
            className={INPUT_CLASS}
            disabled={disabled}
            onChange={(e) => {
              onChange({ ...value, label: e.target.value });
            }}
            placeholder="Ej. Sesión individual"
            type="text"
            value={value.label}
          />
        </formFieldModule.FormField>
        <formFieldModule.FormField htmlFor="" label="Monto">
          <currencyInputModule.CurrencyInput
            amount={value.amount}
            currency={value.currency}
            disabled={disabled}
            onChange={(next) => {
              onChange({ ...value, amount: next.amount, currency: next.currency });
            }}
          />
        </formFieldModule.FormField>
        <formFieldModule.FormField
          helperText="Texto libre. Ej. '5% descuento' o 'Pacientes fuera de Colombia'."
          htmlFor=""
          label="Descripción de la tarifa"
        >
          <textarea
            className={TEXTAREA_CLASS}
            disabled={disabled}
            onChange={(e) => {
              const v = e.target.value === "" ? null : e.target.value;
              onChange({ ...value, description: v });
            }}
            placeholder="Descripción opcional"
            rows={2}
            value={value.description ?? ""}
          />
        </formFieldModule.FormField>
      </div>
    </collapsibleCardModule.CollapsibleCard>
  );
}

interface ServiceOfferingItemProps {
  value: agentModel.ServiceOffering;
  onChange: (next: agentModel.ServiceOffering) => void;
  disabled: boolean;
}

const MODALITIES: agentModel.Modality[] = ["PRESENCIAL", "VIRTUAL"];

function modalityLabel(m: agentModel.Modality): string {
  return m === "PRESENCIAL" ? "Presencial" : "Virtual";
}

export function ServiceOfferingItem(props: ServiceOfferingItemProps) {
  const { value, onChange, disabled } = props;

  const handleField =
    (field: keyof agentModel.ServiceOffering) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const raw = event.target.value;
      onChange({ ...value, [field]: raw === "" ? null : raw });
    };

  const toggleModality = (modality: agentModel.Modality) => {
    const has = value.modalities.includes(modality);
    const next = has
      ? value.modalities.filter((m) => m !== modality)
      : [...value.modalities, modality];
    onChange({ ...value, modalities: next });
  };

  const summaryName =
    value.name === null || value.name.trim() === "" ? "Servicio nuevo" : value.name;

  return (
    <collapsibleCardModule.CollapsibleCard
      className="border border-slate-200"
      summary={
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-slate-800">{summaryName}</span>
          {value.modalities.map((m) => (
            <span
              className="rounded-full bg-brand-teal/10 px-2 py-0.5 text-xs font-medium text-brand-teal"
              key={m}
            >
              {modalityLabel(m)}
            </span>
          ))}
        </div>
      }
    >
      <div className="space-y-4">
        <formFieldModule.FormField htmlFor="" label="Nombre del servicio">
          <input
            className={INPUT_CLASS}
            disabled={disabled}
            onChange={handleField("name")}
            placeholder="Ej. Consulta Individual Adultos"
            type="text"
            value={value.name ?? ""}
          />
        </formFieldModule.FormField>

        <formFieldModule.FormField htmlFor="" label="Descripción">
          <textarea
            className={TEXTAREA_CLASS}
            disabled={disabled}
            onChange={handleField("description")}
            placeholder="Descripción breve del servicio..."
            rows={2}
            value={value.description ?? ""}
          />
        </formFieldModule.FormField>

        <div>
          <p className="text-sm font-medium text-slate-700">Modalidades</p>
          <div className="mt-1.5 flex gap-4">
            {MODALITIES.map((modality) => (
              <label
                className="inline-flex items-center gap-2 text-sm text-slate-700"
                key={modality}
              >
                <input
                  checked={value.modalities.includes(modality)}
                  className="accent-brand-teal"
                  disabled={disabled}
                  onChange={() => {
                    toggleModality(modality);
                  }}
                  type="checkbox"
                />
                {modalityLabel(modality)}
              </label>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-slate-700">Tarifas</p>
          <dynamicListModule.DynamicList
            addLabel="Agregar tarifa"
            emptyMessage="No hay tarifas configuradas."
            items={value.tariffs}
            newItemFactory={newTariffOption}
            onChange={(next) => {
              onChange({ ...value, tariffs: next });
            }}
            renderItem={(item, _i, onItemChange) => (
              <TariffItem disabled={disabled} onChange={onItemChange} value={item} />
            )}
          />
        </div>
      </div>
    </collapsibleCardModule.CollapsibleCard>
  );
}

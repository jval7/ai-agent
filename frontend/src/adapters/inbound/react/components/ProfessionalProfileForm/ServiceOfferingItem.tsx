import type * as agentModel from "@domain/models/agent";
import * as currencyInputModule from "@adapters/inbound/react/components/form/CurrencyInput";
import * as dynamicListModule from "@adapters/inbound/react/components/form/DynamicList";
import * as formFieldModule from "@adapters/inbound/react/components/form/FormField";

const INPUT_CLASS =
  "mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal disabled:cursor-not-allowed disabled:opacity-60";
const TEXTAREA_CLASS =
  "mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60";

function newTariffOption(defaultCurrency: string): agentModel.TariffOption {
  return { label: "", amount: 0, currency: defaultCurrency, discountPercent: null };
}

interface TariffItemProps {
  value: agentModel.TariffOption;
  onChange: (next: agentModel.TariffOption) => void;
  disabled: boolean;
}

function TariffItem(props: TariffItemProps) {
  const { value, onChange, disabled } = props;
  return (
    <div className="space-y-2">
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
        helperText="Dejar en blanco si no hay descuento."
        htmlFor=""
        label="Descuento (%)"
      >
        <input
          className={`${INPUT_CLASS} w-28`}
          disabled={disabled}
          max={100}
          min={0}
          onChange={(e) => {
            const v = e.target.value === "" ? null : Number(e.target.value);
            onChange({ ...value, discountPercent: v });
          }}
          placeholder="Ej. 10"
          step={1}
          type="number"
          value={value.discountPercent ?? ""}
        />
      </formFieldModule.FormField>
    </div>
  );
}

interface ServiceOfferingItemProps {
  value: agentModel.ServiceOffering;
  onChange: (next: agentModel.ServiceOffering) => void;
  disabled: boolean;
}

const MODALITIES: agentModel.Modality[] = ["PRESENCIAL", "VIRTUAL"];

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

  return (
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

      <formFieldModule.FormField htmlFor="" label="Audiencia">
        <input
          className={INPUT_CLASS}
          disabled={disabled}
          onChange={handleField("audience")}
          placeholder="Ej. Adultos, Niños"
          type="text"
          value={value.audience ?? ""}
        />
      </formFieldModule.FormField>

      <formFieldModule.FormField htmlFor="" label="Descripcion">
        <textarea
          className={TEXTAREA_CLASS}
          disabled={disabled}
          onChange={handleField("description")}
          placeholder="Descripcion breve del servicio..."
          rows={2}
          value={value.description ?? ""}
        />
      </formFieldModule.FormField>

      <div>
        <p className="text-sm font-medium text-slate-700">Modalidades</p>
        <div className="mt-1.5 flex gap-4">
          {MODALITIES.map((modality) => (
            <label className="inline-flex items-center gap-2 text-sm text-slate-700" key={modality}>
              <input
                checked={value.modalities.includes(modality)}
                className="accent-brand-teal"
                disabled={disabled}
                onChange={() => {
                  toggleModality(modality);
                }}
                type="checkbox"
              />
              {modality === "PRESENCIAL" ? "Presencial" : "Virtual"}
            </label>
          ))}
        </div>
      </div>

      <div>
        <p className="mb-2 text-sm font-medium text-slate-700">Tarifas locales (COP)</p>
        <dynamicListModule.DynamicList
          addLabel="Agregar tarifa local"
          emptyMessage="No hay tarifas locales."
          items={value.tariffsLocal}
          newItemFactory={() => newTariffOption("COP")}
          onChange={(next) => {
            onChange({ ...value, tariffsLocal: next });
          }}
          renderItem={(item, _i, onItemChange) => (
            <TariffItem disabled={disabled} onChange={onItemChange} value={item} />
          )}
        />
      </div>

      <div>
        <p className="mb-2 text-sm font-medium text-slate-700">
          Tarifas para pacientes en el extranjero (USD)
        </p>
        <dynamicListModule.DynamicList
          addLabel="Agregar tarifa extranjero"
          emptyMessage="No hay tarifas para extranjero."
          items={value.tariffsForeign}
          newItemFactory={() => newTariffOption("USD")}
          onChange={(next) => {
            onChange({ ...value, tariffsForeign: next });
          }}
          renderItem={(item, _i, onItemChange) => (
            <TariffItem disabled={disabled} onChange={onItemChange} value={item} />
          )}
        />
      </div>
    </div>
  );
}

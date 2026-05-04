import type * as agentModel from "@domain/models/agent";
import * as collapsibleCardModule from "@adapters/inbound/react/components/form/CollapsibleCard";
import * as currencyInputModule from "@adapters/inbound/react/components/form/CurrencyInput";
import * as dynamicListModule from "@adapters/inbound/react/components/form/DynamicList";
import * as formFieldModule from "@adapters/inbound/react/components/form/FormField";

const INPUT_CLASS =
  "mt-1 block w-full rounded-xl bg-surface-low border-none px-3 py-2.5 text-sm placeholder:text-sidebar-text/50 focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60";
const TEXTAREA_CLASS =
  "mt-1 w-full rounded-xl bg-surface-low border-none px-3 py-2.5 text-sm transition-colors placeholder:text-sidebar-text/50 focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60";

function newTariffOption(): agentModel.TariffOption {
  // Default: a tariff with two price slots so the professional can fill COP
  // and USD side by side without having to add a row first.
  return {
    label: "",
    description: null,
    prices: [
      { currency: "COP", amount: 0 },
      { currency: "USD", amount: 0 }
    ]
  };
}

function formatTariffSummary(t: agentModel.TariffOption): string {
  const label = t.label.trim() === "" ? "Tarifa nueva" : t.label;
  const meaningful = t.prices.filter((p) => p.amount > 0);
  if (meaningful.length === 0) return label;
  const parts = meaningful.map((p) => `${p.amount.toLocaleString("es-CO")} ${p.currency}`);
  return `${label} · ${parts.join(" / ")}`;
}

interface TariffItemProps {
  value: agentModel.TariffOption;
  onChange: (next: agentModel.TariffOption) => void;
  disabled: boolean;
}

function TariffItem(props: TariffItemProps) {
  const { value, onChange, disabled } = props;

  const updatePrice = (index: number, next: agentModel.TariffPrice) => {
    const updated = value.prices.map((p, i) => (i === index ? next : p));
    onChange({ ...value, prices: updated });
  };

  const removePrice = (index: number) => {
    const updated = value.prices.filter((_, i) => i !== index);
    onChange({ ...value, prices: updated });
  };

  const addPrice = () => {
    onChange({ ...value, prices: [...value.prices, { currency: "COP", amount: 0 }] });
  };

  return (
    <collapsibleCardModule.CollapsibleCard
      className="bg-surface-container shadow-none"
      summary={
        <span className="text-sm text-brand-ink">
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
        <div>
          <p className="text-sm font-medium text-slate-700">Precios</p>
          <p className="mt-0.5 text-xs text-slate-500">
            Un valor por moneda. Agrega los que apliquen para tus pacientes.
          </p>
          <div className="mt-2 space-y-2">
            {value.prices.map((price, index) => (
              <div className="flex items-end gap-2" key={index}>
                <div className="flex-1">
                  <currencyInputModule.CurrencyInput
                    amount={price.amount}
                    currency={price.currency}
                    disabled={disabled}
                    onChange={(next) => {
                      updatePrice(index, { currency: next.currency, amount: next.amount });
                    }}
                  />
                </div>
                <button
                  aria-label="Eliminar precio"
                  className="mb-1 rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:cursor-not-allowed"
                  disabled={disabled}
                  onClick={() => {
                    removePrice(index);
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
                    <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
          <button
            className="mt-2 rounded-lg border border-dashed border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:border-brand-teal hover:text-brand-teal disabled:cursor-not-allowed"
            disabled={disabled}
            onClick={addPrice}
            type="button"
          >
            + Agregar precio
          </button>
        </div>
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
const TARGET_PATIENTS: agentModel.TargetPatient[] = ["NEW", "RETURNING"];

function modalityLabel(m: agentModel.Modality): string {
  return m === "PRESENCIAL" ? "Presencial" : "Virtual";
}

function targetPatientLabel(t: agentModel.TargetPatient): string {
  return t === "NEW" ? "Pacientes nuevos" : "Pacientes recurrentes";
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

  const toggleTargetPatient = (target: agentModel.TargetPatient) => {
    const has = value.targetPatients.includes(target);
    const next = has
      ? value.targetPatients.filter((t) => t !== target)
      : [...value.targetPatients, target];
    onChange({ ...value, targetPatients: next });
  };

  const summaryName =
    value.name === null || value.name.trim() === "" ? "Servicio nuevo" : value.name;

  return (
    <collapsibleCardModule.CollapsibleCard
      summary={
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-brand-ink">{summaryName}</span>
          {value.modalities.map((m) => (
            <span
              className="rounded-full bg-brand-accent-light/60 px-2 py-0.5 text-xs font-semibold text-brand-teal uppercase tracking-wide"
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
          <p className="text-sm font-medium text-slate-700">Disponible para</p>
          <p className="mt-0.5 text-xs text-slate-500">
            El bot solo ofrece este servicio a los grupos seleccionados.
          </p>
          <div className="mt-1.5 flex gap-4">
            {TARGET_PATIENTS.map((target) => (
              <label className="inline-flex items-center gap-2 text-sm text-slate-700" key={target}>
                <input
                  checked={value.targetPatients.includes(target)}
                  className="accent-brand-teal"
                  disabled={disabled}
                  onChange={() => {
                    toggleTargetPatient(target);
                  }}
                  type="checkbox"
                />
                {targetPatientLabel(target)}
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

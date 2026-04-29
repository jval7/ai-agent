import type * as agentModel from "@domain/models/agent";
import * as collapsibleCardModule from "@adapters/inbound/react/components/form/CollapsibleCard";
import * as formFieldModule from "@adapters/inbound/react/components/form/FormField";

const INPUT_CLASS =
  "mt-1 block w-full rounded-xl bg-surface-low border-none px-3 py-2.5 text-sm placeholder:text-sidebar-text/50 focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60";
const TEXTAREA_CLASS =
  "mt-1 w-full rounded-xl bg-surface-low border-none px-3 py-2.5 text-sm transition-colors placeholder:text-sidebar-text/50 focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60";

interface PaymentMethodItemProps {
  value: agentModel.PaymentMethod;
  onChange: (next: agentModel.PaymentMethod) => void;
  disabled: boolean;
}

export function PaymentMethodItem(props: PaymentMethodItemProps) {
  const { value, onChange, disabled } = props;

  const handleField =
    (field: keyof agentModel.PaymentMethod) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const raw = event.target.value;
      onChange({ ...value, [field]: raw === "" ? null : raw });
    };

  const summaryName = value.methodName.trim() === "" ? "Medio de pago nuevo" : value.methodName;

  return (
    <collapsibleCardModule.CollapsibleCard
      summary={
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-brand-ink">{summaryName}</span>
          {value.currency !== "" ? (
            <span className="rounded-full bg-brand-accent-light/60 px-2 py-0.5 text-xs font-semibold text-brand-teal uppercase tracking-wide">
              {value.currency}
            </span>
          ) : null}
        </div>
      }
    >
      <div className="space-y-3">
        <div className="flex gap-3">
          <formFieldModule.FormField htmlFor={`pm-currency-${value.methodName}`} label="Moneda">
            <input
              className={`${INPUT_CLASS} w-24`}
              disabled={disabled}
              id={`pm-currency-${value.methodName}`}
              maxLength={3}
              onChange={(e) => {
                onChange({ ...value, currency: e.target.value.toUpperCase() });
              }}
              placeholder="COP"
              type="text"
              value={value.currency}
            />
          </formFieldModule.FormField>

          <div className="flex-1">
            <formFieldModule.FormField
              htmlFor={`pm-method-name-${value.methodName}`}
              label="Medio de pago"
            >
              <input
                className={INPUT_CLASS}
                disabled={disabled}
                id={`pm-method-name-${value.methodName}`}
                onChange={(e) => {
                  onChange({ ...value, methodName: e.target.value });
                }}
                placeholder="Ej. Nequi, Zelle, Transferencia"
                type="text"
                value={value.methodName}
              />
            </formFieldModule.FormField>
          </div>
        </div>

        <formFieldModule.FormField
          htmlFor={`pm-holder-${value.methodName}`}
          label="Titular de la cuenta"
        >
          <input
            className={INPUT_CLASS}
            disabled={disabled}
            id={`pm-holder-${value.methodName}`}
            onChange={handleField("holder")}
            placeholder="Ej. María López"
            type="text"
            value={value.holder ?? ""}
          />
        </formFieldModule.FormField>

        <formFieldModule.FormField
          helperText="Numero de cuenta, celular u otros datos para realizar el pago."
          htmlFor={`pm-instructions-${value.methodName}`}
          label="Instrucciones / datos de pago"
        >
          <textarea
            className={TEXTAREA_CLASS}
            disabled={disabled}
            id={`pm-instructions-${value.methodName}`}
            onChange={handleField("instructions")}
            placeholder="Ej. 300 000 0000"
            rows={2}
            value={value.instructions ?? ""}
          />
        </formFieldModule.FormField>

        <formFieldModule.FormField
          helperText="Cuando aplica este metodo. Ej.: pacientes en Colombia."
          htmlFor={`pm-applies-${value.methodName}`}
          label="Aplica cuando"
        >
          <input
            className={INPUT_CLASS}
            disabled={disabled}
            id={`pm-applies-${value.methodName}`}
            onChange={handleField("appliesWhen")}
            placeholder="Ej. Colombia (COP)"
            type="text"
            value={value.appliesWhen ?? ""}
          />
        </formFieldModule.FormField>
      </div>
    </collapsibleCardModule.CollapsibleCard>
  );
}

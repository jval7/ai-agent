import * as reactModule from "react";

interface CurrencyValue {
  amount: number;
  currency: string;
}

interface CurrencyInputProps {
  amount: number;
  currency: string;
  onChange: (next: CurrencyValue) => void;
  currencyOptions?: string[];
  disabled: boolean;
}

const DEFAULT_CURRENCY_OPTIONS = ["COP", "USD"];

function formatDisplay(amount: number): string {
  if (isNaN(amount)) return "";
  return amount.toLocaleString("es-CO");
}

function parseRaw(display: string): number {
  // Remove thousands separators (. or ,) but keep the numeric value
  const cleaned = display.replace(/[.,\s]/g, "");
  const parsed = Number(cleaned);
  return isNaN(parsed) ? 0 : parsed;
}

export function CurrencyInput(props: CurrencyInputProps) {
  const currencyOptions = props.currencyOptions ?? DEFAULT_CURRENCY_OPTIONS;

  const [displayValue, setDisplayValue] = reactModule.useState(
    props.amount > 0 ? formatDisplay(props.amount) : ""
  );

  // Sync display when external amount changes (e.g., data loaded from server)
  reactModule.useEffect(() => {
    setDisplayValue(props.amount > 0 ? formatDisplay(props.amount) : "");
  }, [props.amount]);

  const handleAmountChange = (event: reactModule.ChangeEvent<HTMLInputElement>) => {
    const raw = event.target.value;
    setDisplayValue(raw);
    const numericValue = parseRaw(raw);
    props.onChange({ amount: numericValue, currency: props.currency });
  };

  const handleAmountBlur = () => {
    const numericValue = parseRaw(displayValue);
    setDisplayValue(numericValue > 0 ? formatDisplay(numericValue) : "");
    props.onChange({ amount: numericValue, currency: props.currency });
  };

  const handleCurrencyChange = (event: reactModule.ChangeEvent<HTMLSelectElement>) => {
    props.onChange({ amount: props.amount, currency: event.target.value });
  };

  return (
    <div className="flex items-center gap-2">
      <select
        className="rounded-xl bg-surface-low border-none px-2 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={props.disabled}
        onChange={handleCurrencyChange}
        value={props.currency}
      >
        {currencyOptions.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
      <input
        className="block w-full rounded-xl bg-surface-low border-none px-3 py-2.5 text-sm placeholder:text-sidebar-text/50 focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={props.disabled}
        inputMode="numeric"
        onBlur={handleAmountBlur}
        onChange={handleAmountChange}
        placeholder="0"
        type="text"
        value={displayValue}
      />
    </div>
  );
}

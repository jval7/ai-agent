import * as reactModule from "react";

interface ChipListProps {
  items: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  disabled: boolean;
}

export function ChipList(props: ChipListProps) {
  const [inputValue, setInputValue] = reactModule.useState("");

  const addItem = (raw: string) => {
    const trimmed = raw.trim().replace(/,$/, "").trim();
    if (trimmed === "") return;
    const alreadyExists = props.items.some((item) => item.toLowerCase() === trimmed.toLowerCase());
    if (alreadyExists) {
      setInputValue("");
      return;
    }
    props.onChange([...props.items, trimmed]);
    setInputValue("");
  };

  const removeItem = (index: number) => {
    const next = props.items.filter((_, i) => i !== index);
    props.onChange(next);
  };

  const handleKeyDown = (event: reactModule.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addItem(inputValue);
    } else if (event.key === "Backspace" && inputValue === "" && props.items.length > 0) {
      removeItem(props.items.length - 1);
    }
  };

  const handleChange = (event: reactModule.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    if (value.endsWith(",")) {
      addItem(value);
    } else {
      setInputValue(value);
    }
  };

  return (
    <div className="mt-1">
      <div className="flex min-h-[2.5rem] flex-wrap gap-1.5 rounded-lg border border-slate-300 px-3 py-2 focus-within:border-brand-teal focus-within:ring-1 focus-within:ring-brand-teal">
        {props.items.map((item, index) => (
          <span
            className="inline-flex items-center gap-1 rounded-full bg-brand-teal/10 px-2.5 py-0.5 text-xs font-medium text-brand-teal"
            key={index}
          >
            {item}
            {props.disabled !== true ? (
              <button
                aria-label={`Eliminar ${item}`}
                className="ml-0.5 rounded-full text-brand-teal/70 hover:text-brand-teal focus:outline-none"
                onClick={() => {
                  removeItem(index);
                }}
                type="button"
              >
                &times;
              </button>
            ) : null}
          </span>
        ))}
        {props.disabled !== true ? (
          <input
            className="min-w-[120px] flex-1 border-none bg-transparent text-sm outline-none placeholder:text-slate-400"
            disabled={props.disabled}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={props.items.length === 0 ? (props.placeholder ?? "Agregar...") : ""}
            type="text"
            value={inputValue}
          />
        ) : null}
      </div>
      <p className="mt-1 text-xs text-slate-400">Presiona Enter o coma para agregar.</p>
    </div>
  );
}

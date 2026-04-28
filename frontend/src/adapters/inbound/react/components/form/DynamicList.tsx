import type * as reactModule from "react";

interface DynamicListProps<T> {
  items: T[];
  onChange: (next: T[]) => void;
  renderItem: (item: T, index: number, onItemChange: (next: T) => void) => reactModule.ReactNode;
  newItemFactory: () => T;
  addLabel?: string;
  emptyMessage?: string;
}

export function DynamicList<T>(props: DynamicListProps<T>) {
  const handleItemChange = (index: number, next: T) => {
    const updated = props.items.map((item, i) => (i === index ? next : item));
    props.onChange(updated);
  };

  const handleRemove = (index: number) => {
    const next = props.items.filter((_, i) => i !== index);
    props.onChange(next);
  };

  const handleAdd = () => {
    props.onChange([...props.items, props.newItemFactory()]);
  };

  return (
    <div className="space-y-3">
      {props.items.length === 0 && props.emptyMessage !== undefined ? (
        <p className="text-sm text-slate-400 italic">{props.emptyMessage}</p>
      ) : null}
      {props.items.map((item, index) => (
        <div
          className="relative rounded-xl border border-border-subtle bg-slate-50 p-4"
          key={index}
        >
          <button
            aria-label="Eliminar"
            className="absolute right-3 top-3 rounded text-slate-400 hover:text-red-500 focus:outline-none"
            onClick={() => {
              handleRemove(index);
            }}
            type="button"
          >
            &times;
          </button>
          {props.renderItem(item, index, (next) => {
            handleItemChange(index, next);
          })}
        </div>
      ))}
      <button
        className="inline-flex items-center gap-1 rounded-lg border border-dashed border-brand-teal px-4 py-2 text-sm font-medium text-brand-teal hover:bg-brand-teal/5 focus:outline-none"
        onClick={handleAdd}
        type="button"
      >
        + {props.addLabel ?? "Agregar"}
      </button>
    </div>
  );
}

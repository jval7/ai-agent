import type * as agentModel from "@domain/models/agent";

const WEEKDAY_OPTIONS: { value: agentModel.Weekday; label: string }[] = [
  { value: "MON", label: "Lunes" },
  { value: "TUE", label: "Martes" },
  { value: "WED", label: "Miércoles" },
  { value: "THU", label: "Jueves" },
  { value: "FRI", label: "Viernes" },
  { value: "SAT", label: "Sábado" },
  { value: "SUN", label: "Domingo" }
];

interface WeekdayRangeValue {
  weekday_from: agentModel.Weekday;
  weekday_to: agentModel.Weekday | null;
  start_time: string;
  end_time: string;
}

interface WeekdayRangeSelectorProps {
  value: WeekdayRangeValue;
  onChange: (next: WeekdayRangeValue) => void;
  disabled: boolean;
}

const SELECT_CLASS =
  "rounded-lg border border-slate-300 px-2 py-2 text-sm focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal disabled:cursor-not-allowed disabled:opacity-60";
const TIME_CLASS =
  "rounded-lg border border-slate-300 px-2 py-2 text-sm focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal disabled:cursor-not-allowed disabled:opacity-60";

export function WeekdayRangeSelector(props: WeekdayRangeSelectorProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        className={SELECT_CLASS}
        disabled={props.disabled}
        onChange={(e) => {
          props.onChange({ ...props.value, weekday_from: e.target.value as agentModel.Weekday });
        }}
        value={props.value.weekday_from}
      >
        {WEEKDAY_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      <span className="text-sm text-slate-500">a</span>

      <select
        className={SELECT_CLASS}
        disabled={props.disabled}
        onChange={(e) => {
          const val = e.target.value;
          props.onChange({
            ...props.value,
            weekday_to: val === "" ? null : (val as agentModel.Weekday)
          });
        }}
        value={props.value.weekday_to ?? ""}
      >
        <option value="">(solo este día)</option>
        {WEEKDAY_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      <span className="text-sm text-slate-500">de</span>

      <input
        className={TIME_CLASS}
        disabled={props.disabled}
        onChange={(e) => {
          props.onChange({ ...props.value, start_time: e.target.value });
        }}
        type="time"
        value={props.value.start_time}
      />

      <span className="text-sm text-slate-500">a</span>

      <input
        className={TIME_CLASS}
        disabled={props.disabled}
        onChange={(e) => {
          props.onChange({ ...props.value, end_time: e.target.value });
        }}
        type="time"
        value={props.value.end_time}
      />
    </div>
  );
}

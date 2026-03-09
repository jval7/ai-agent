export type StatusBadgeTone = "neutral" | "success" | "warning" | "danger" | "info";

export function StatusBadge(props: {
  label: string;
  tone: StatusBadgeTone;
}) {
  const toneClassByType = {
    neutral: "bg-slate-100 text-slate-700",
    success: "bg-emerald-100 text-emerald-700",
    warning: "bg-amber-100 text-amber-700",
    danger: "bg-red-100 text-red-700",
    info: "bg-blue-100 text-blue-700"
  } as const;

  return (
    <span
      className={`rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ${toneClassByType[props.tone]}`}
    >
      {props.label}
    </span>
  );
}

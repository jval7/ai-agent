export function StatusBadge(props: {
  label: string;
  tone: "neutral" | "success" | "warning" | "danger";
}) {
  const toneClassByType = {
    neutral: "bg-slate-100 text-slate-700",
    success: "bg-emerald-100 text-emerald-700",
    warning: "bg-amber-100 text-amber-700",
    danger: "bg-red-100 text-red-700"
  } as const;

  return (
    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${toneClassByType[props.tone]}`}>
      {props.label}
    </span>
  );
}

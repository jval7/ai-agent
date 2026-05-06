interface ChangeModalityPanelProps {
  patientDisplayName: string;
  formattedDate: string;
  currentModality: "VIRTUAL" | "PRESENCIAL";
  targetModality: "VIRTUAL" | "PRESENCIAL";
  isSaving: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  /** Extra wrapper class for variants (inline panel vs drawer) */
  className?: string;
}

export function ChangeModalityPanel({
  patientDisplayName,
  formattedDate,
  currentModality,
  targetModality,
  isSaving,
  onConfirm,
  onCancel,
  className = "rounded-lg border border-border-subtle p-4 space-y-4"
}: ChangeModalityPanelProps) {
  const currentLabel = currentModality === "VIRTUAL" ? "virtual" : "presencial";
  const targetLabel = targetModality === "VIRTUAL" ? "virtual" : "presencial";

  return (
    <div className={className}>
      <div>
        <p className="text-sm font-semibold text-brand-ink">Cambiar modalidad</p>
        <p className="text-xs text-slate-500 mt-0.5">
          {`¿Cambiar la cita de ${patientDisplayName} del ${formattedDate} de ${currentLabel} a ${targetLabel}?`}
        </p>
        <p className="text-xs text-slate-500 mt-1">
          Se enviará automáticamente un correo al paciente con los nuevos datos del evento.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isSaving}
          onClick={onConfirm}
          type="button"
        >
          {isSaving ? "Guardando..." : "Confirmar cambio"}
        </button>
        <button
          className="rounded-lg border border-border-subtle px-4 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
          onClick={onCancel}
          type="button"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}

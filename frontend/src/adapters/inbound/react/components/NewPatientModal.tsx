import * as reactModule from "react";
import type * as patientModel from "@domain/models/patient";

interface NewPatientModalFormState {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  age: string;
  location: string;
  consultationReason: string;
}

function emptyModalForm(): NewPatientModalFormState {
  return {
    firstName: "",
    lastName: "",
    email: "",
    phone: "",
    age: "",
    location: "",
    consultationReason: ""
  };
}

function deriveWhatsappUserId(phone: string): string {
  return phone.replace(/\D/g, "");
}

interface NewPatientModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (whatsappUserId: string) => void;
  onSubmit: (input: patientModel.CreatePatientInput) => Promise<void>;
  isSubmitting: boolean;
}

export function NewPatientModal({
  isOpen,
  onClose,
  onCreated,
  onSubmit,
  isSubmitting
}: NewPatientModalProps) {
  const [formState, setFormState] =
    reactModule.useState<NewPatientModalFormState>(emptyModalForm());
  const [phoneError, setPhoneError] = reactModule.useState<string | null>(null);
  const [submitError, setSubmitError] = reactModule.useState<string | null>(null);

  const handleClose = reactModule.useCallback(() => {
    setFormState(emptyModalForm());
    setPhoneError(null);
    setSubmitError(null);
    onClose();
  }, [onClose]);

  reactModule.useEffect(() => {
    if (!isOpen) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        handleClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, handleClose]);

  const handleBackdropClick = (event: reactModule.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  };

  const handleSubmit = async () => {
    const trimmedFirstName = formState.firstName.trim();
    const trimmedLastName = formState.lastName.trim();
    const trimmedEmail = formState.email.trim();
    const trimmedPhone = formState.phone.trim();
    const trimmedLocation = formState.location.trim();
    const trimmedConsultationReason = formState.consultationReason.trim();
    const ageValue = Number.parseInt(formState.age, 10);

    setPhoneError(null);
    setSubmitError(null);

    if (
      trimmedFirstName === "" ||
      trimmedLastName === "" ||
      trimmedEmail === "" ||
      trimmedPhone === "" ||
      trimmedLocation === "" ||
      trimmedConsultationReason === "" ||
      Number.isNaN(ageValue) ||
      ageValue <= 0
    ) {
      setSubmitError("Completa todos los campos antes de guardar.");
      return;
    }

    const whatsappUserId = deriveWhatsappUserId(trimmedPhone);
    if (whatsappUserId.length < 8) {
      setPhoneError("Incluye el código de país, ej. +57 300 123 4567");
      return;
    }

    try {
      await onSubmit({
        whatsappUserId,
        firstName: trimmedFirstName,
        lastName: trimmedLastName,
        email: trimmedEmail,
        age: ageValue,
        consultationReason: trimmedConsultationReason,
        location: trimmedLocation,
        phone: trimmedPhone
      });
      onCreated(whatsappUserId);
      setFormState(emptyModalForm());
      setPhoneError(null);
      setSubmitError(null);
      onClose();
    } catch {
      setSubmitError("Ocurrió un error al crear el paciente. Intenta de nuevo.");
    }
  };

  if (!isOpen) {
    return null;
  }

  const inputClass =
    "mt-1 w-full rounded-lg border border-border-subtle px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20";
  const labelClass = "text-xs font-semibold uppercase tracking-wide text-slate-500";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={handleBackdropClick}
    >
      <div className="w-full max-w-lg rounded-xl border border-border-subtle bg-white shadow-xl">
        {/* Modal header */}
        <div className="flex items-center justify-between border-b border-border-subtle px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-brand-ink">Nuevo paciente</h2>
            <p className="text-xs text-slate-500">Completa los datos para registrar al paciente.</p>
          </div>
          <button
            className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
            onClick={handleClose}
            type="button"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Modal body */}
        <div className="grid gap-3 px-5 py-4">
          {/* Row 1: Nombre | Apellido */}
          <div className="grid grid-cols-2 gap-3">
            <label className={labelClass}>
              Nombre
              <input
                className={inputClass}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setFormState((current) => ({ ...current, firstName: nextValue }));
                }}
                placeholder="Ana"
                type="text"
                value={formState.firstName}
              />
            </label>
            <label className={labelClass}>
              Apellido
              <input
                className={inputClass}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setFormState((current) => ({ ...current, lastName: nextValue }));
                }}
                placeholder="García"
                type="text"
                value={formState.lastName}
              />
            </label>
          </div>

          {/* Row 2: Email | Teléfono */}
          <div className="grid grid-cols-2 gap-3">
            <label className={labelClass}>
              Email
              <input
                className={inputClass}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setFormState((current) => ({ ...current, email: nextValue }));
                }}
                placeholder="ana@email.com"
                type="email"
                value={formState.email}
              />
            </label>
            <label className={labelClass}>
              Teléfono
              <input
                className={[
                  inputClass,
                  phoneError !== null
                    ? "border-rose-400 focus:border-rose-400 focus:ring-rose-200"
                    : ""
                ].join(" ")}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setFormState((current) => ({ ...current, phone: nextValue }));
                  setPhoneError(null);
                }}
                placeholder="+57 300 123 4567"
                type="text"
                value={formState.phone}
              />
              {phoneError !== null ? (
                <p className="mt-1 text-[11px] text-rose-600">{phoneError}</p>
              ) : null}
            </label>
          </div>

          {/* Row 3: Edad | Ubicación */}
          <div className="grid grid-cols-2 gap-3">
            <label className={labelClass}>
              Edad
              <input
                className={inputClass}
                min={1}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setFormState((current) => ({ ...current, age: nextValue }));
                }}
                placeholder="30"
                type="number"
                value={formState.age}
              />
            </label>
            <label className={labelClass}>
              Ubicación
              <input
                className={inputClass}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setFormState((current) => ({ ...current, location: nextValue }));
                }}
                placeholder="Bogotá"
                type="text"
                value={formState.location}
              />
            </label>
          </div>

          {/* Row 4: Motivo de consulta */}
          <label className={labelClass}>
            Motivo de consulta
            <textarea
              className={inputClass}
              onChange={(event) => {
                const nextValue = event.target.value;
                setFormState((current) => ({ ...current, consultationReason: nextValue }));
              }}
              placeholder="Describe el motivo principal de la consulta"
              rows={3}
              value={formState.consultationReason}
            />
          </label>

          {submitError !== null ? (
            <p className="rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {submitError}
            </p>
          ) : null}
        </div>

        {/* Modal footer */}
        <div className="flex items-center justify-between border-t border-border-subtle px-5 py-4">
          <button
            className="rounded-lg border border-border-subtle px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
            onClick={handleClose}
            type="button"
          >
            Cancelar
          </button>
          <button
            className="rounded-lg bg-brand-teal px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSubmitting}
            onClick={() => {
              void handleSubmit();
            }}
            type="button"
          >
            {isSubmitting ? "Creando..." : "Crear paciente"}
          </button>
        </div>
      </div>
    </div>
  );
}

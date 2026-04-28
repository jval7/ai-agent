import * as reactModule from "react";
import * as reactDomModule from "react-dom";
import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import { NewPatientModal } from "@adapters/inbound/react/components/NewPatientModal";
import type * as patientModel from "@domain/models/patient";

interface PatientComboboxProps {
  value: string | null;
  onChange: (patient: patientModel.Patient | null) => void;
  disabled?: boolean;
  placeholder?: string;
}

const DEBOUNCE_MS = 250;

export function PatientCombobox({
  value,
  onChange,
  disabled = false,
  placeholder = "Buscar paciente..."
}: PatientComboboxProps) {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const [inputValue, setInputValue] = reactModule.useState("");
  const [debouncedSearch, setDebouncedSearch] = reactModule.useState("");
  const [isOpen, setIsOpen] = reactModule.useState(false);
  const [activeIndex, setActiveIndex] = reactModule.useState(-1);
  const [isNewPatientOpen, setIsNewPatientOpen] = reactModule.useState(false);
  const [selectedPatient, setSelectedPatient] = reactModule.useState<patientModel.Patient | null>(
    null
  );

  const containerRef = reactModule.useRef<HTMLDivElement>(null);
  const inputRef = reactModule.useRef<HTMLInputElement>(null);
  const listboxId = reactModule.useId();

  const createPatientMutation = reactQueryModule.useMutation({
    mutationFn: (input: patientModel.CreatePatientInput) =>
      appContainer.patientUseCase.createPatient(input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["patients"] });
    }
  });

  // Debounce the search input
  reactModule.useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(inputValue);
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [inputValue]);

  const searchQuery = reactQueryModule.useQuery({
    queryKey: ["patients-combobox", debouncedSearch],
    queryFn: () =>
      appContainer.patientUseCase.listPatients(
        debouncedSearch === "" ? undefined : { search: debouncedSearch }
      ),
    enabled: isOpen
  });

  const patients = searchQuery.data ?? [];

  // Close on outside click
  reactModule.useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (containerRef.current !== null && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setActiveIndex(-1);
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, []);

  const handleSelect = (patient: patientModel.Patient) => {
    setSelectedPatient(patient);
    setInputValue("");
    setDebouncedSearch("");
    setIsOpen(false);
    setActiveIndex(-1);
    onChange(patient);
  };

  const handleClear = () => {
    setSelectedPatient(null);
    setInputValue("");
    setDebouncedSearch("");
    onChange(null);
    inputRef.current?.focus();
  };

  const handleInputFocus = () => {
    if (value === null) {
      setIsOpen(true);
    }
  };

  const handleInputChange = (event: reactModule.ChangeEvent<HTMLInputElement>) => {
    setInputValue(event.target.value);
    setIsOpen(true);
    setActiveIndex(-1);
  };

  // Total items: patients + "nuevo paciente" button at end
  const totalItems = patients.length + 1;

  const handleKeyDown = (event: reactModule.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        setIsOpen(true);
      }
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((prev) => (prev + 1) % totalItems);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((prev) => (prev - 1 + totalItems) % totalItems);
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (activeIndex >= 0 && activeIndex < patients.length) {
        const patient = patients.at(activeIndex);
        if (patient !== undefined) {
          handleSelect(patient);
        }
      } else if (activeIndex === patients.length) {
        setIsNewPatientOpen(true);
        setIsOpen(false);
      }
    } else if (event.key === "Escape") {
      setIsOpen(false);
      setActiveIndex(-1);
    }
  };

  const activeDescendantId =
    activeIndex >= 0 && activeIndex < patients.length
      ? `${listboxId}-option-${activeIndex}`
      : undefined;

  const displayValue = (() => {
    if (value !== null && selectedPatient !== null) {
      return `${selectedPatient.firstName} ${selectedPatient.lastName} · ${selectedPatient.phone}`;
    }
    // value provided but no selectedPatient in local state (e.g. externally set)
    if (value !== null && selectedPatient === null) {
      return value;
    }
    return null;
  })();

  return (
    <div className="relative" ref={containerRef}>
      {displayValue !== null ? (
        /* Selected state: read-only display with clear button */
        <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm">
          <span className="flex-1 truncate text-brand-ink">{displayValue}</span>
          {!disabled ? (
            <button
              aria-label="Limpiar selección"
              className="shrink-0 text-slate-400 hover:text-slate-600"
              onClick={handleClear}
              type="button"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          ) : null}
        </div>
      ) : (
        /* Search input */
        <input
          aria-activedescendant={activeDescendantId}
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-expanded={isOpen}
          autoComplete="off"
          className="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm transition-colors focus:border-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-teal/20 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={disabled}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          ref={inputRef}
          role="combobox"
          type="text"
          value={inputValue}
        />
      )}

      {isOpen && !disabled ? (
        <div
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-64 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-lg"
          id={listboxId}
          role="listbox"
        >
          {searchQuery.isLoading ? (
            <p className="px-3 py-2 text-xs text-slate-400">Buscando...</p>
          ) : null}

          {!searchQuery.isLoading && patients.length === 0 && debouncedSearch !== "" ? (
            <p className="px-3 py-2 text-xs text-slate-400">
              Sin resultados para "{debouncedSearch}".
            </p>
          ) : null}

          {patients.map((patient, index) => {
            const isActive = index === activeIndex;
            return (
              <button
                aria-selected={isActive}
                className={[
                  "w-full px-3 py-2 text-left text-sm transition-colors",
                  isActive ? "bg-brand-accent-light text-brand-ink" : "hover:bg-slate-50"
                ].join(" ")}
                id={`${listboxId}-option-${index}`}
                key={patient.whatsappUserId}
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(patient);
                }}
                role="option"
                type="button"
              >
                <span className="font-medium">
                  {patient.firstName} {patient.lastName}
                </span>
                <span className="ml-1.5 text-xs text-slate-500">
                  {"·"} {patient.phone}
                </span>
              </button>
            );
          })}

          {patients.length > 0 ? <div className="mx-3 border-t border-border-subtle" /> : null}

          <button
            className={[
              "w-full px-3 py-2 text-left text-xs font-semibold text-brand-teal transition-colors hover:bg-slate-50",
              activeIndex === patients.length ? "bg-brand-accent-light" : ""
            ].join(" ")}
            onMouseDown={(e) => {
              e.preventDefault();
              setIsNewPatientOpen(true);
              setIsOpen(false);
            }}
            type="button"
          >
            + Nuevo paciente
            {inputValue.trim() !== "" ? ` "${inputValue.trim()}"` : ""}
          </button>
        </div>
      ) : null}

      {reactDomModule.createPortal(
        <NewPatientModal
          isOpen={isNewPatientOpen}
          isSubmitting={createPatientMutation.isPending}
          onClose={() => {
            setIsNewPatientOpen(false);
          }}
          onCreated={(whatsappUserId) => {
            const allPatients =
              queryClient.getQueryData<patientModel.Patient[]>(["patients"]) ?? [];
            const created = allPatients.find((p) => p.whatsappUserId === whatsappUserId);
            if (created !== undefined) {
              handleSelect(created);
            } else {
              onChange({ whatsappUserId } as patientModel.Patient);
            }
          }}
          onSubmit={async (input: patientModel.CreatePatientInput) => {
            await createPatientMutation.mutateAsync(input);
          }}
        />,
        document.body
      )}
    </div>
  );
}

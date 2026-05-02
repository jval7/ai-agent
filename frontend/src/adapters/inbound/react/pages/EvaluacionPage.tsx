import * as reactModule from "react";

import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as capabilitiesTabModule from "@adapters/inbound/react/pages/evaluacion/CapabilitiesTab";
import * as personasTabModule from "@adapters/inbound/react/pages/evaluacion/PersonasTab";
import * as runsTabModule from "@adapters/inbound/react/pages/evaluacion/RunsTab";
import * as shapesTabModule from "@adapters/inbound/react/pages/evaluacion/ShapesTab";

type Tab = "shapes" | "personas" | "capabilities" | "runs";

const tabs: { id: Tab; label: string }[] = [
  { id: "shapes", label: "Shapes" },
  { id: "personas", label: "Personas" },
  { id: "capabilities", label: "Capabilities" },
  { id: "runs", label: "Corridas" }
];

export function EvaluacionPage() {
  const [activeTab, setActiveTab] = reactModule.useState<Tab>("runs");

  return (
    <appShellModule.AppShell>
      <div className="flex h-full flex-col overflow-auto p-4 md:p-6">
        <div className="mb-4">
          <h1 className="text-lg font-bold text-slate-800">Evaluación</h1>
          <p className="mt-0.5 text-xs text-slate-500">
            Dashboard de evaluación — solo lectura. Corre evals con{" "}
            <code className="rounded bg-slate-100 px-1">
              uv run python scripts/load_test.py --eval-mode
            </code>
          </p>
        </div>

        {/* Info-box */}
        <details className="mb-4 rounded-lg border border-slate-200 bg-slate-50">
          <summary className="flex cursor-pointer select-none items-center gap-2 px-4 py-2.5 text-xs font-medium text-slate-600 hover:bg-slate-100">
            <svg
              className="h-4 w-4 shrink-0 text-slate-400"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4M12 8h.01" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Como se ejecutan las corridas (click para detalles)
          </summary>
          <div className="border-t border-slate-200 px-4 py-3 text-xs text-slate-600">
            <p className="mb-2">
              Cada corrida (<code className="rounded bg-slate-100 px-1">--eval-mode</code>) crea N
              tenants efimeros, uno por cada shape, secuencialmente:
            </p>
            <pre className="mb-2 overflow-x-auto rounded bg-slate-100 px-3 py-2 text-xs text-slate-700">
              {`  shape_1 → crea tenant → corre N personas → borra tenant
  shape_2 → crea tenant → corre N personas → borra tenant
  ...`}
            </pre>
            <p className="mb-2">
              Las personas dentro de un shape corren en el mismo tenant (secuencialmente). La
              cantidad de personas por shape se decide con{" "}
              <code className="rounded bg-slate-100 px-1">select_personas_for_shape</code> (
              <code className="rounded bg-slate-100 px-1">per_combo=1</code> por default,
              dedupeado).
            </p>
            <p>
              Lanza una corrida con:{" "}
              <code className="rounded bg-slate-100 px-1">
                uv run python scripts/load_test.py --eval-mode
              </code>
            </p>
          </div>
        </details>

        {/* Tabs */}
        <div className="mb-4 border-b border-slate-200">
          <div className="flex gap-1">
            {tabs.map((tab) => (
              <button
                className={[
                  "px-4 py-2 text-sm font-medium transition-colors",
                  activeTab === tab.id
                    ? "border-b-2 border-brand-teal text-brand-teal"
                    : "text-slate-500 hover:text-slate-700"
                ].join(" ")}
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                }}
                type="button"
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1">
          {activeTab === "shapes" ? <shapesTabModule.ShapesTab /> : null}
          {activeTab === "personas" ? <personasTabModule.PersonasTab /> : null}
          {activeTab === "capabilities" ? <capabilitiesTabModule.CapabilitiesTab /> : null}
          {activeTab === "runs" ? <runsTabModule.RunsTab /> : null}
        </div>
      </div>
    </appShellModule.AppShell>
  );
}

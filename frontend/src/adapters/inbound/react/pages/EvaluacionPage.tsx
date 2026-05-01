import * as reactModule from "react";

import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as personasTabModule from "@adapters/inbound/react/pages/evaluacion/PersonasTab";
import * as runsTabModule from "@adapters/inbound/react/pages/evaluacion/RunsTab";
import * as shapesTabModule from "@adapters/inbound/react/pages/evaluacion/ShapesTab";

type Tab = "shapes" | "personas" | "runs";

const tabs: { id: Tab; label: string }[] = [
  { id: "shapes", label: "Shapes" },
  { id: "personas", label: "Personas" },
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
          {activeTab === "runs" ? <runsTabModule.RunsTab /> : null}
        </div>
      </div>
    </appShellModule.AppShell>
  );
}

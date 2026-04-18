import * as reactModule from "react";
import * as reactQueryModule from "@tanstack/react-query";

import * as appContainerContextModule from "@adapters/inbound/react/app/AppContainerContext";
import * as appShellModule from "@adapters/inbound/react/components/AppShell";
import * as errorBannerModule from "@adapters/inbound/react/components/ErrorBanner";
import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import * as apiErrorModule from "@shared/http/api_error";
import * as uiErrorModule from "@shared/http/ui_error";

const templatesQueryKey = ["whatsapp-templates"] as const;

const OFFICIAL_TEMPLATE_NAMES = new Set([
  "appointment_reminder_attendance",
  "appointment_reminder_payment"
]);

const CATEGORIES = ["MARKETING", "UTILITY", "AUTHENTICATION"] as const;
const LANGUAGES = [
  { value: "es", label: "Español" },
  { value: "en", label: "English" },
  { value: "pt_BR", label: "Português (BR)" }
] as const;

function buildStatusBadge(status: string): JSX.Element {
  let colorClasses = "bg-slate-100 text-slate-700";
  if (status === "APPROVED") {
    colorClasses = "bg-emerald-100 text-emerald-700";
  } else if (status === "PENDING") {
    colorClasses = "bg-yellow-100 text-yellow-700";
  } else if (status === "REJECTED") {
    colorClasses = "bg-red-100 text-red-700";
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colorClasses}`}
    >
      {status}
    </span>
  );
}

function buildCategoryBadge(category: string): JSX.Element {
  return (
    <span className="inline-flex items-center rounded-full bg-brand-accent-light px-2.5 py-0.5 text-xs font-medium text-brand-teal">
      {category}
    </span>
  );
}

function DocumentTextIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-12 w-12 text-slate-300"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      viewBox="0 0 24 24"
    >
      <path
        d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function PlantillasPage() {
  const appContainer = appContainerContextModule.useAppContainer();
  const queryClient = reactQueryModule.useQueryClient();

  const [isModalOpen, setIsModalOpen] = reactModule.useState(false);
  const [deleteConflictMessage, setDeleteConflictMessage] = reactModule.useState<string | null>(
    null
  );
  const [formName, setFormName] = reactModule.useState("");
  const [formCategory, setFormCategory] = reactModule.useState<string>("MARKETING");
  const [formLanguage, setFormLanguage] = reactModule.useState<string>("es");
  const [formBody, setFormBody] = reactModule.useState("");
  const [formExamples, setFormExamples] = reactModule.useState<string[]>([]);

  const detectedVariables = reactModule.useMemo(() => {
    const matches = formBody.match(/\{\{(\d+)\}\}/g);
    if (!matches) return [];
    const unique = [...new Set(matches)].sort();
    return unique;
  }, [formBody]);

  reactModule.useEffect(() => {
    setFormExamples((prev) => {
      const newExamples = detectedVariables.map((_, i) => {
        const existing: string | undefined = prev[Number(i)];
        return existing ?? "";
      });
      return newExamples;
    });
  }, [detectedVariables]);

  const templatesQuery = reactQueryModule.useQuery({
    queryKey: templatesQueryKey,
    queryFn: () => appContainer.whatsappTemplateUseCase.listTemplates()
  });

  const createMutation = reactQueryModule.useMutation({
    mutationFn: () =>
      appContainer.whatsappTemplateUseCase.createTemplate({
        name: formName.trim(),
        category: formCategory,
        language: formLanguage,
        components: [
          {
            type: "BODY",
            text: formBody.trim(),
            ...(formExamples.length > 0 ? { exampleValues: formExamples } : {})
          }
        ]
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: templatesQueryKey });
      setIsModalOpen(false);
      setFormName("");
      setFormCategory("MARKETING");
      setFormLanguage("es");
      setFormBody("");
      setFormExamples([]);
    }
  });

  const deleteMutation = reactQueryModule.useMutation({
    mutationFn: (name: string) => appContainer.whatsappTemplateUseCase.deleteTemplate(name),
    onSuccess: async () => {
      setDeleteConflictMessage(null);
      await queryClient.invalidateQueries({ queryKey: templatesQueryKey });
    },
    onError: (error: unknown) => {
      if (error instanceof apiErrorModule.ApiError && error.statusCode === 409) {
        setDeleteConflictMessage(error.message);
      }
    }
  });

  const deleteNonConflictError =
    deleteMutation.error instanceof apiErrorModule.ApiError &&
    deleteMutation.error.statusCode === 409
      ? null
      : deleteMutation.error;

  const listErrorMessage = uiErrorModule.resolveUiErrorMessage([
    templatesQuery.error,
    deleteNonConflictError
  ]);

  const createErrorMessage = uiErrorModule.resolveUiErrorMessage([createMutation.error]);

  function handleOpenModal() {
    setFormName("");
    setFormCategory("MARKETING");
    setFormLanguage("es");
    setFormBody("");
    setFormExamples([]);
    createMutation.reset();
    setIsModalOpen(true);
  }

  function handleCloseModal() {
    setIsModalOpen(false);
  }

  const templates = templatesQuery.data ?? [];

  return (
    <appShellModule.AppShell>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brand-ink">Plantillas de mensajes</h1>
          <p className="mt-1 text-sm text-slate-500">
            Gestiona las plantillas de mensajes de WhatsApp Business.
          </p>
        </div>
        <button
          className="rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover"
          onClick={handleOpenModal}
          type="button"
        >
          Crear plantilla
        </button>
      </div>

      {listErrorMessage !== null ? (
        <errorBannerModule.ErrorBanner className="mb-4" message={listErrorMessage} />
      ) : null}

      {deleteConflictMessage !== null ? (
        <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {deleteConflictMessage} — Desactívala desde Ajustes antes de eliminarla.
        </div>
      ) : null}

      {templatesQuery.isLoading ? (
        <div className="flex items-center justify-center py-16 text-sm text-slate-500">
          Cargando plantillas...
        </div>
      ) : templates.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16">
          <DocumentTextIcon />
          <p className="mt-4 text-sm font-medium text-slate-600">No hay plantillas creadas</p>
          <p className="mt-1 text-xs text-slate-400">
            Crea tu primera plantilla para empezar a enviar mensajes.
          </p>
          <button
            className="mt-5 rounded-lg bg-brand-teal px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover"
            onClick={handleOpenModal}
            type="button"
          >
            Crear plantilla
          </button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border-subtle bg-white shadow-card">
          <table className="min-w-full divide-y divide-border-subtle">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Nombre
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Categoria
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Idioma
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Estado
                </th>
                <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {templates.map((template) => {
                const isOfficial = OFFICIAL_TEMPLATE_NAMES.has(template.name);
                return (
                  <tr key={template.id} className="transition-colors hover:bg-slate-50">
                    <td className="px-6 py-4 text-sm font-medium text-brand-ink">
                      <span className="mr-2">{template.name}</span>
                      {isOfficial ? (
                        <statusBadgeModule.StatusBadge label="OFICIAL" tone="info" />
                      ) : null}
                    </td>
                    <td className="px-6 py-4 text-sm">{buildCategoryBadge(template.category)}</td>
                    <td className="px-6 py-4 text-sm text-slate-600">{template.language}</td>
                    <td className="px-6 py-4 text-sm">{buildStatusBadge(template.status)}</td>
                    <td className="px-6 py-4 text-right">
                      {isOfficial ? (
                        <span
                          className="cursor-default text-sm text-slate-400"
                          title="Desactívala desde Ajustes"
                        >
                          Eliminar
                        </span>
                      ) : (
                        <button
                          className="text-sm font-medium text-red-600 transition-colors hover:text-red-800 disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={deleteMutation.isPending}
                          onClick={() => {
                            deleteMutation.mutate(template.name);
                          }}
                          type="button"
                        >
                          Eliminar
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {isModalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-brand-ink">Crear plantilla</h2>
            <p className="mt-1 text-sm text-slate-500">
              Completa los datos para crear una nueva plantilla en WhatsApp Business.
            </p>

            <div className="mt-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700" htmlFor="template-name">
                  Nombre
                </label>
                <input
                  className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal"
                  id="template-name"
                  onChange={(e) => {
                    setFormName(e.target.value);
                  }}
                  placeholder="ej. bienvenida_nuevos_clientes"
                  type="text"
                  value={formName}
                />
              </div>

              <div>
                <label
                  className="block text-sm font-medium text-slate-700"
                  htmlFor="template-category"
                >
                  Categoria
                </label>
                <select
                  className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal"
                  id="template-category"
                  onChange={(e) => {
                    setFormCategory(e.target.value);
                  }}
                  value={formCategory}
                >
                  {CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  className="block text-sm font-medium text-slate-700"
                  htmlFor="template-language"
                >
                  Idioma
                </label>
                <select
                  className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal"
                  id="template-language"
                  onChange={(e) => {
                    setFormLanguage(e.target.value);
                  }}
                  value={formLanguage}
                >
                  {LANGUAGES.map((lang) => (
                    <option key={lang.value} value={lang.value}>
                      {lang.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700" htmlFor="template-body">
                  Cuerpo del mensaje
                </label>
                <textarea
                  className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal"
                  id="template-body"
                  onChange={(e) => {
                    setFormBody(e.target.value);
                  }}
                  placeholder="Hola {{1}}, tu cita es el {{2}} a las {{3}}"
                  rows={4}
                  value={formBody}
                />
              </div>

              {detectedVariables.length > 0 ? (
                <div>
                  <label className="block text-sm font-medium text-slate-700">
                    Ejemplos para las variables
                  </label>
                  <p className="mt-0.5 text-xs text-slate-400">
                    Meta requiere valores de ejemplo para aprobar la plantilla.
                  </p>
                  <div className="mt-2 space-y-2">
                    {detectedVariables.map((variable, index) => (
                      <div key={variable} className="flex items-center gap-2">
                        <span className="w-12 text-right text-xs font-medium text-slate-500">
                          {variable}
                        </span>
                        <input
                          className="block w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-teal focus:outline-none focus:ring-1 focus:ring-brand-teal"
                          onChange={(e) => {
                            const idx = Number(index);
                            const val = e.target.value;
                            setFormExamples((prev) => {
                              const updated = [...prev];
                              updated.splice(idx, 1, val);
                              return updated;
                            });
                          }}
                          placeholder={`Ejemplo para ${variable}`}
                          type="text"
                          value={formExamples[Number(index)] ?? ""}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            {createErrorMessage !== null ? (
              <errorBannerModule.ErrorBanner className="mt-4" message={createErrorMessage} />
            ) : null}

            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-lg border border-border-subtle px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
                disabled={createMutation.isPending}
                onClick={handleCloseModal}
                type="button"
              >
                Cancelar
              </button>
              <button
                className="rounded-lg bg-brand-teal px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover disabled:cursor-not-allowed disabled:opacity-60"
                disabled={
                  createMutation.isPending || formName.trim() === "" || formBody.trim() === ""
                }
                onClick={() => {
                  createMutation.mutate();
                }}
                type="button"
              >
                {createMutation.isPending ? "Creando..." : "Crear"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </appShellModule.AppShell>
  );
}

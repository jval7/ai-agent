interface ErrorFallbackProps {
  error: Error;
  onReset: () => void;
}

export function ErrorFallback(props: ErrorFallbackProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="max-w-md rounded-lg bg-white p-8 text-center shadow-md">
        <svg
          className="mx-auto h-12 w-12 text-red-400"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
          />
        </svg>

        <h2 className="mt-4 text-lg font-semibold text-brand-ink">Algo salió mal</h2>
        <p className="mt-2 text-sm text-slate-500">
          Ocurrió un error inesperado. Puedes intentar de nuevo.
        </p>

        <details className="mt-3 text-left">
          <summary className="cursor-pointer text-xs text-slate-400">Detalles del error</summary>
          <pre className="mt-1 overflow-auto rounded bg-slate-100 p-2 text-xs text-slate-500">
            {props.error.message}
          </pre>
        </details>

        <div className="mt-6 flex justify-center gap-3">
          <button
            onClick={props.onReset}
            className="rounded-lg bg-brand-teal px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-teal-hover"
          >
            Reintentar
          </button>
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            Recargar página
          </button>
        </div>
      </div>
    </div>
  );
}

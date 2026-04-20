import * as reactModule from "react";

interface AppointmentDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  children: reactModule.ReactNode;
}

export function AppointmentDrawer({ isOpen, onClose, children }: AppointmentDrawerProps) {
  const handleClose = reactModule.useCallback(() => {
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

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30" onClick={handleClose} />
      {/* Panel */}
      <div className="absolute right-0 top-0 flex h-full w-full flex-col bg-white shadow-xl sm:max-w-[440px] sm:rounded-l-xl">
        {/* Close button */}
        <div className="flex shrink-0 items-center justify-end border-b border-border-subtle px-4 py-3">
          <button
            aria-label="Cerrar"
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
        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

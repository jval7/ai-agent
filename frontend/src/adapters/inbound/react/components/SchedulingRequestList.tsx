import * as statusBadgeModule from "@adapters/inbound/react/components/StatusBadge";
import { approvalStatusLabels } from "@adapters/inbound/react/hooks/useSchedulingRequests";
import { resolvePatientDisplayName } from "@adapters/inbound/react/hooks/useBookedAppointments";
import type * as patientModel from "@domain/models/patient";
import type * as schedulingModel from "@domain/models/scheduling";
import * as dateUtilsModule from "@shared/utils/date";

interface SchedulingRequestListProps {
  requests: schedulingModel.SchedulingRequestSummary[];
  selectedRequestId: string | null;
  patientsByWhatsappUserId: Map<string, patientModel.Patient>;
  isLoading: boolean;
  activeTab: schedulingModel.SchedulingRequestStatus;
  onSelectRequest: (requestId: string) => void;
}

export function SchedulingRequestList({
  requests,
  selectedRequestId,
  patientsByWhatsappUserId,
  isLoading,
  activeTab,
  onSelectRequest
}: SchedulingRequestListProps) {
  return (
    <article className="rounded-xl border border-border-subtle bg-white shadow-card">
      <header className="border-b border-border-subtle px-3 py-3 sm:p-4">
        <h3 className="text-sm font-semibold sm:text-base">Solicitudes</h3>
        <p className="text-[11px] text-slate-500 sm:text-xs">{`Estado actual: ${activeTab}`}</p>
      </header>
      <div className="max-h-[calc(100vh-12rem)] space-y-2 overflow-auto p-2 sm:p-3">
        {isLoading ? <p className="text-sm text-slate-500">Cargando...</p> : null}
        {requests.length === 0 ? (
          <p className="text-sm text-slate-500">No hay solicitudes en este estado.</p>
        ) : null}
        {requests.map((request) => {
          const isSelected = request.requestId === selectedRequestId;
          const statusConfig = approvalStatusLabels[request.status];
          return (
            <button
              className={[
                "w-full rounded-lg border p-3 text-left",
                isSelected
                  ? "border-brand-teal bg-brand-accent-light"
                  : "border-slate-200 bg-white hover:border-slate-300"
              ].join(" ")}
              key={request.requestId}
              onClick={() => onSelectRequest(request.requestId)}
              type="button"
            >
              <div className="mb-1 flex items-center justify-between gap-2">
                <p className="truncate text-sm font-semibold text-brand-ink">
                  {resolvePatientDisplayName(request, patientsByWhatsappUserId)}
                </p>
                <statusBadgeModule.StatusBadge
                  label={statusConfig?.label ?? request.status}
                  tone={statusConfig?.tone ?? "neutral"}
                />
              </div>
              {request.audienceType !== null ? (
                <span className="text-xs font-medium text-violet-600">
                  {request.audienceType === "CHILDREN" ? "Infantil" : "Adulto"}
                </span>
              ) : null}
              {request.consultationReason !== null ? (
                <p className="truncate text-xs text-slate-600">{request.consultationReason}</p>
              ) : null}
              <p className="mt-1 text-xs text-slate-500">
                {dateUtilsModule.formatDateTime(request.updatedAt)}
              </p>
            </button>
          );
        })}
      </div>
    </article>
  );
}

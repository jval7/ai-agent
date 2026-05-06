import * as reactModule from "react";

import type * as schedulingModel from "@domain/models/scheduling";

export const agendaStatuses: {
  status: schedulingModel.SchedulingRequestStatus;
  label: string;
}[] = [
  { status: "BOOKED", label: "Agendadas" },
  { status: "SESSION_CLOSED", label: "Cerradas" },
  { status: "CANCELLED", label: "Canceladas" },
  { status: "HUMAN_HANDOFF", label: "Human Handoff" }
];

export const approvalStatusLabels: Record<
  string,
  { label: string; tone: "neutral" | "success" | "warning" | "danger" }
> = {
  AWAITING_CONSULTATION_REVIEW: { label: "Pendiente revisión", tone: "warning" },
  AWAITING_CONSULTATION_DETAILS: { label: "Esperando detalles", tone: "neutral" },
  AWAITING_PATIENT_CHOICE: { label: "Esperando paciente", tone: "neutral" },
  AWAITING_PAYMENT_CONFIRMATION: { label: "Pendiente pago", tone: "warning" },
  CONSULTATION_REJECTED: { label: "Rechazado", tone: "danger" }
};

export interface UseSchedulingRequestsResult {
  activeTab: schedulingModel.SchedulingRequestStatus;
  setActiveTab: (tab: schedulingModel.SchedulingRequestStatus) => void;
  isBookedTab: boolean;
  selectedRequestId: string | null;
  setSelectedRequestId: (id: string | null) => void;
  filteredRequests: schedulingModel.SchedulingRequestSummary[];
  requestCountByStatus: Map<schedulingModel.SchedulingRequestStatus, number>;
  selectedRequest: schedulingModel.SchedulingRequestSummary | undefined;
}

export function useSchedulingRequests(
  allRequests: schedulingModel.SchedulingRequestSummary[],
  options?: {
    initialActiveTab?: schedulingModel.SchedulingRequestStatus;
    externalSelectedRequestId?: string | null;
    externalSetSelectedRequestId?: (id: string | null) => void;
  }
): UseSchedulingRequestsResult {
  const [activeTab, setActiveTab] = reactModule.useState<schedulingModel.SchedulingRequestStatus>(
    options?.initialActiveTab ?? "BOOKED"
  );
  const [internalSelectedRequestId, setInternalSelectedRequestId] = reactModule.useState<
    string | null
  >(null);

  const selectedRequestId = options?.externalSelectedRequestId ?? internalSelectedRequestId;
  const setSelectedRequestId =
    options?.externalSetSelectedRequestId ?? setInternalSelectedRequestId;

  const isBookedTab = activeTab === "BOOKED";

  const requestCountByStatus = reactModule.useMemo(() => {
    const countMap = new Map<schedulingModel.SchedulingRequestStatus, number>();
    allRequests.forEach((request) => {
      const currentCount = countMap.get(request.status) ?? 0;
      countMap.set(request.status, currentCount + 1);
    });
    return countMap;
  }, [allRequests]);

  const filteredRequests = reactModule.useMemo(() => {
    return allRequests.filter((request) => request.status === activeTab);
  }, [allRequests, activeTab]);

  // Auto-select first request when tab changes (non-booked tabs)
  reactModule.useEffect(() => {
    if (isBookedTab) {
      return;
    }
    if (filteredRequests.length === 0) {
      setSelectedRequestId(null);
      return;
    }
    const selectedExists = filteredRequests.some(
      (request) => request.requestId === selectedRequestId
    );
    if (!selectedExists) {
      const firstRequest = filteredRequests[0];
      if (firstRequest !== undefined) {
        setSelectedRequestId(firstRequest.requestId);
      }
    }
  }, [filteredRequests, isBookedTab, selectedRequestId]);

  const selectedRequest = allRequests.find((request) => request.requestId === selectedRequestId);

  return {
    activeTab,
    setActiveTab,
    isBookedTab,
    selectedRequestId,
    setSelectedRequestId,
    filteredRequests,
    requestCountByStatus,
    selectedRequest
  };
}

import * as reactModule from "react";
import * as luxonModule from "luxon";

import type * as manualAppointmentModel from "@domain/models/manual_appointment";
import type * as patientModel from "@domain/models/patient";
import type * as schedulingModel from "@domain/models/scheduling";

const colombiaTimezone = "America/Bogota";

export interface BookedAppointment {
  itemKey: string;
  source: "BOT" | "MANUAL";
  requestId: string | null;
  manualAppointmentId: string | null;
  patientDisplayName: string;
  patientPhone: string;
  summary: string;
  dayIso: string;
  startAt: luxonModule.DateTime;
  endAt: luxonModule.DateTime;
  request: schedulingModel.SchedulingRequestSummary | null;
  manualAppointment: manualAppointmentModel.ManualAppointment | null;
}

export function resolvePatientDisplayName(
  request: schedulingModel.SchedulingRequestSummary,
  patientMap?: Map<string, patientModel.Patient>
): string {
  const names = [request.patientFirstName, request.patientLastName]
    .map((value) => value?.trim() ?? "")
    .filter((value) => value !== "");
  if (names.length > 0) {
    return names.join(" ");
  }
  if (patientMap !== undefined) {
    const patient = patientMap.get(request.whatsappUserId);
    if (patient !== undefined) {
      const patientName = `${patient.firstName} ${patient.lastName}`.trim();
      if (patientName !== "") {
        return patientName;
      }
    }
  }
  return request.whatsappUserId;
}

export function resolveBookedSlot(
  request: schedulingModel.SchedulingRequestSummary
): schedulingModel.SchedulingSlot | null {
  if (request.selectedSlotId !== null) {
    const selectedSlot = request.slots.find((slot) => slot.slotId === request.selectedSlotId);
    if (selectedSlot !== undefined) {
      return selectedSlot;
    }
  }
  const bookedSlot = request.slots.find((slot) => slot.status === "BOOKED");
  if (bookedSlot !== undefined) {
    return bookedSlot;
  }
  return null;
}

interface UseBookedAppointmentsParams {
  allRequests: schedulingModel.SchedulingRequestSummary[];
  allManualAppointments: manualAppointmentModel.ManualAppointment[];
  patientsByWhatsappUserId: Map<string, patientModel.Patient>;
  isBookedTab: boolean;
  timezone: string;
}

export function useBookedAppointments({
  allRequests,
  allManualAppointments,
  patientsByWhatsappUserId,
  isBookedTab,
  timezone
}: UseBookedAppointmentsParams) {
  const FINALIZED_STATUSES = reactModule.useMemo(
    () => new Set<string>(["BOOKED", "SESSION_CLOSED", "HUMAN_HANDOFF"]),
    []
  );

  const bookedAppointments = reactModule.useMemo<BookedAppointment[]>(() => {
    if (!isBookedTab) {
      return [];
    }
    const combinedAppointments: BookedAppointment[] = [];

    allRequests
      .filter((r) => FINALIZED_STATUSES.has(r.status))
      // RESCHEDULE child SRs reach SESSION_CLOSED with a selected slot but no
      // calendar event — the actual booking lives on the source SR. Filtering
      // by calendarEventId hides those synthetic records so the calendar does
      // not render duplicates.
      .filter((r) => r.calendarEventId !== null)
      .forEach((request) => {
        const selectedSlot = resolveBookedSlot(request);
        if (selectedSlot === null) {
          return;
        }
        const appointmentTimezone =
          selectedSlot.timezone.trim() === "" ? timezone : selectedSlot.timezone;
        const startAt = luxonModule.DateTime.fromISO(selectedSlot.startAt, {
          zone: appointmentTimezone
        }).setZone(timezone);
        const endAt = luxonModule.DateTime.fromISO(selectedSlot.endAt, {
          zone: appointmentTimezone
        }).setZone(timezone);
        const dayIso = startAt.toISODate();
        if (!startAt.isValid || !endAt.isValid || dayIso === null) {
          return;
        }
        const patientDisplayName = resolvePatientDisplayName(request, patientsByWhatsappUserId);
        combinedAppointments.push({
          itemKey: `bot:${request.requestId}`,
          source: "BOT",
          requestId: request.requestId,
          manualAppointmentId: null,
          patientDisplayName,
          patientPhone: request.whatsappUserId,
          summary:
            patientDisplayName.trim() === "" ? "Cita bot" : `Cita bot - ${patientDisplayName}`,
          dayIso,
          startAt,
          endAt,
          request,
          manualAppointment: null
        });
      });

    allManualAppointments
      .filter((manualAppointment) => manualAppointment.status === "SCHEDULED")
      .forEach((manualAppointment) => {
        const appointmentTimezone =
          manualAppointment.timezone.trim() === "" ? colombiaTimezone : manualAppointment.timezone;
        const startAt = luxonModule.DateTime.fromISO(manualAppointment.startAt, {
          zone: appointmentTimezone
        }).setZone(timezone);
        const endAt = luxonModule.DateTime.fromISO(manualAppointment.endAt, {
          zone: appointmentTimezone
        }).setZone(timezone);
        const dayIso = startAt.toISODate();
        if (!startAt.isValid || !endAt.isValid || dayIso === null) {
          return;
        }
        const patient = patientsByWhatsappUserId.get(manualAppointment.patientWhatsappUserId);
        const patientDisplayName =
          patient === undefined
            ? manualAppointment.patientWhatsappUserId
            : `${patient.firstName} ${patient.lastName}`;
        combinedAppointments.push({
          itemKey: `manual:${manualAppointment.appointmentId}`,
          source: "MANUAL",
          requestId: null,
          manualAppointmentId: manualAppointment.appointmentId,
          patientDisplayName,
          patientPhone: manualAppointment.patientWhatsappUserId,
          summary: manualAppointment.summary,
          dayIso,
          startAt,
          endAt,
          request: null,
          manualAppointment
        });
      });

    return combinedAppointments.sort((left, right) => {
      return left.startAt.toMillis() - right.startAt.toMillis();
    });
  }, [
    FINALIZED_STATUSES,
    allManualAppointments,
    allRequests,
    isBookedTab,
    patientsByWhatsappUserId,
    timezone
  ]);

  const bookedAppointmentsByDay = reactModule.useMemo(() => {
    const appointmentsByDay = new Map<string, BookedAppointment[]>();
    bookedAppointments.forEach((appointment) => {
      const dayAppointments = appointmentsByDay.get(appointment.dayIso);
      if (dayAppointments === undefined) {
        appointmentsByDay.set(appointment.dayIso, [appointment]);
        return;
      }
      appointmentsByDay.set(appointment.dayIso, [...dayAppointments, appointment]);
    });
    return appointmentsByDay;
  }, [bookedAppointments]);

  return { bookedAppointments, bookedAppointmentsByDay };
}

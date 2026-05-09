import * as luxonModule from "luxon";

import type { BookedAppointment } from "@adapters/inbound/react/hooks/useBookedAppointments";
import * as calendarUtilsModule from "@shared/utils/calendar";

interface AppointmentCalendarProps {
  visibleMonthStart: luxonModule.DateTime;
  dayGrid: (luxonModule.DateTime | null)[];
  bookedAppointmentsByDay: Map<string, BookedAppointment[]>;
  selectedDayIso: string;
  selectedBookedItemKey: string | null;
  desktopDrawerOpen: boolean;
  nowDate: luxonModule.DateTime;
  timezone: string;
  mobileBookedStep: "calendar" | "dayList" | "detail";
  selectedDayAppointments: BookedAppointment[];
  onPreviousMonth: () => void;
  onNextMonth: () => void;
  onDayClick: (isoDate: string, firstAppointment: BookedAppointment | undefined) => void;
  /** Called when a desktop calendar chip is clicked — opens the desktop drawer */
  onDesktopAppointmentClick: (appointment: BookedAppointment) => void;
  /** Called when a mobile day-list item is clicked — navigates to mobile detail step */
  onMobileAppointmentClick: (appointment: BookedAppointment) => void;
  onNewManualAppointment: () => void;
  onMobileBackToCalendar: () => void;
}

export function AppointmentCalendar({
  visibleMonthStart,
  dayGrid,
  bookedAppointmentsByDay,
  selectedDayIso,
  selectedBookedItemKey,
  desktopDrawerOpen,
  nowDate,
  timezone,
  mobileBookedStep,
  selectedDayAppointments,
  onPreviousMonth,
  onNextMonth,
  onDayClick,
  onDesktopAppointmentClick,
  onMobileAppointmentClick,
  onNewManualAppointment,
  onMobileBackToCalendar
}: AppointmentCalendarProps) {
  return (
    <article
      className={[
        "rounded-xl border border-border-subtle bg-white shadow-card",
        mobileBookedStep === "detail" ? "hidden sm:block" : ""
      ].join(" ")}
    >
      <header
        className={[
          "border-b border-border-subtle px-3 py-3 sm:p-4",
          mobileBookedStep !== "calendar" ? "hidden sm:block" : ""
        ].join(" ")}
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold sm:text-base">Calendario de citas agendadas</h3>
            <p className="text-[11px] text-slate-500 sm:text-xs">
              Integra citas del chatbot y manuales. Toca un día para ver detalle.
            </p>
          </div>
          <button
            className="hidden shrink-0 rounded-lg bg-brand-teal px-3 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-brand-teal-hover sm:block"
            onClick={onNewManualAppointment}
            type="button"
          >
            + Nueva cita manual
          </button>
        </div>
      </header>
      <div className="space-y-3 p-2 sm:p-3">
        {/* Month navigation — hidden when in dayList or detail on mobile */}
        <div
          className={[
            "flex items-center justify-between gap-2",
            mobileBookedStep !== "calendar" ? "hidden sm:flex" : ""
          ].join(" ")}
        >
          <p className="text-sm font-semibold capitalize text-brand-ink">
            {visibleMonthStart.toFormat("LLLL yyyy")}
          </p>
          <div className="flex gap-1.5 sm:gap-2">
            <button
              className="rounded-lg border border-border-subtle px-2.5 py-1 text-xs text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 sm:px-3 sm:text-sm"
              onClick={onPreviousMonth}
              type="button"
            >
              Anterior
            </button>
            <button
              className="rounded-lg border border-border-subtle px-2.5 py-1 text-xs text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 sm:px-3 sm:text-sm"
              onClick={onNextMonth}
              type="button"
            >
              Siguiente
            </button>
          </div>
        </div>

        {/* Mobile compact calendar — only visible in calendar step */}
        <div className={mobileBookedStep === "calendar" ? "sm:hidden" : "hidden"}>
          <div className="grid grid-cols-7 gap-0.5 text-center text-[10px] font-semibold text-slate-500">
            {calendarUtilsModule.weekDayLabels.map((label) => (
              <span key={`mobile-${label}`}>{label}</span>
            ))}
          </div>
          <div className="mt-1 grid grid-cols-7 gap-0.5">
            {dayGrid.map((dateCell, index) => {
              if (dateCell === null) {
                return <div className="aspect-square rounded-md" key={`mobile-empty-${index}`} />;
              }
              const isoDate = dateCell.toISODate();
              const dayAppointments =
                isoDate === null ? [] : (bookedAppointmentsByDay.get(isoDate) ?? []);
              const isSelectedDay = isoDate === selectedDayIso;
              const hasAppointments = dayAppointments.length > 0;
              return (
                <button
                  className={[
                    "relative flex aspect-square flex-col items-center justify-center rounded-md text-xs font-medium transition-colors",
                    isSelectedDay
                      ? "bg-brand-teal font-bold text-white"
                      : hasAppointments
                        ? "bg-brand-accent-light font-semibold text-brand-teal"
                        : "text-slate-700 hover:bg-slate-100"
                  ].join(" ")}
                  key={dateCell.toISODate() ?? `mobile-day-${dateCell.day}-${index}`}
                  onClick={() => {
                    if (isoDate === null) {
                      return;
                    }
                    onDayClick(isoDate, dayAppointments[0]);
                  }}
                  type="button"
                >
                  {dateCell.day}
                  {hasAppointments ? (
                    <span
                      className={[
                        "absolute bottom-0.5 h-1 w-1 rounded-full",
                        isSelectedDay ? "bg-white" : "bg-brand-teal"
                      ].join(" ")}
                    />
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>

        {/* Mobile day list — visible when a day with appointments is selected */}
        <div className={mobileBookedStep === "dayList" ? "sm:hidden" : "hidden"}>
          <button
            className="mb-2 flex items-center gap-1 text-xs font-semibold text-brand-teal"
            onClick={onMobileBackToCalendar}
            type="button"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                d="M15 19l-7-7 7-7"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
              />
            </svg>
            Volver al calendario
          </button>
          <h4 className="text-sm font-semibold text-brand-ink">
            {selectedDayIso !== ""
              ? `Citas del ${luxonModule.DateTime.fromISO(selectedDayIso, {
                  zone: timezone
                }).toFormat("dd LLL yyyy")}`
              : "Citas del día"}
          </h4>
          {selectedDayAppointments.length === 0 ? (
            <p className="mt-2 text-xs text-slate-500">No hay citas para este día.</p>
          ) : (
            <div className="mt-2 space-y-1.5">
              {selectedDayAppointments.map((appointment) => {
                const isSelectedAppointment = appointment.itemKey === selectedBookedItemKey;
                const isVirtualAppointment =
                  appointment.source === "MANUAL"
                    ? (appointment.manualAppointment?.isVirtual ?? false)
                    : appointment.request?.appointmentModality === "VIRTUAL";
                return (
                  <button
                    className={[
                      "w-full rounded-md border px-2.5 py-2 text-left",
                      isSelectedAppointment
                        ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                    ].join(" ")}
                    key={`mobile-day-${appointment.itemKey}`}
                    onClick={() => onMobileAppointmentClick(appointment)}
                    type="button"
                  >
                    <p className="text-xs font-semibold">
                      {appointment.startAt.toFormat("HH:mm")} -{" "}
                      {appointment.endAt.toFormat("HH:mm")}
                    </p>
                    {appointment.patientDisplayName !== appointment.patientPhone ? (
                      <p className="text-xs">{appointment.patientDisplayName}</p>
                    ) : null}
                    <p className="text-xs text-slate-500">{appointment.patientPhone}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className="text-[11px] uppercase text-slate-500">
                        {appointment.source === "MANUAL" ? "Manual" : "Chatbot"}
                      </span>
                      <span
                        className={[
                          "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                          isVirtualAppointment
                            ? "bg-brand-accent-light text-brand-teal"
                            : "bg-slate-100 text-slate-600"
                        ].join(" ")}
                      >
                        {isVirtualAppointment ? "Google Meet" : "Presencial"}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Mobile FAB — only in calendar step */}
        {mobileBookedStep === "calendar" ? (
          <button
            aria-label="Nueva cita manual"
            className="fixed bottom-4 right-4 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-brand-teal text-white shadow-lg transition-colors hover:bg-brand-teal-hover sm:hidden"
            onClick={onNewManualAppointment}
            type="button"
          >
            <svg
              className="h-7 w-7"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          </button>
        ) : null}

        {/* Desktop full calendar */}
        <div className="hidden sm:block">
          <div className="overflow-x-auto pb-1">
            <div className="min-w-[42rem]">
              <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-600">
                {calendarUtilsModule.weekDayLabels.map((label) => (
                  <span key={label}>{label}</span>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-1">
                {dayGrid.map((dateCell, index) => {
                  if (dateCell === null) {
                    return (
                      <div className="min-h-32 rounded-md bg-slate-50" key={`empty-${index}`} />
                    );
                  }
                  const isoDate = dateCell.toISODate();
                  const dayAppointments =
                    isoDate === null ? [] : (bookedAppointmentsByDay.get(isoDate) ?? []);
                  const isSelectedDay = isoDate === selectedDayIso;
                  const isPastDay = isoDate !== null && isoDate < (nowDate.toISODate() ?? "");
                  return (
                    <div
                      className={[
                        "min-h-32 rounded-md border p-1.5",
                        isSelectedDay
                          ? "border-brand-teal bg-brand-accent-light/40"
                          : isPastDay
                            ? "border-slate-200 bg-slate-50 opacity-70"
                            : "border-slate-200 bg-white"
                      ].join(" ")}
                      key={dateCell.toISODate() ?? `day-${dateCell.day}-${index}`}
                    >
                      <button
                        className={[
                          "w-full rounded px-1 text-left text-xs font-semibold",
                          isSelectedDay
                            ? "bg-brand-accent-light text-brand-teal"
                            : "text-slate-700 hover:bg-slate-100"
                        ].join(" ")}
                        onClick={() => {
                          if (isoDate === null) {
                            return;
                          }
                          onDayClick(isoDate, dayAppointments[0]);
                        }}
                        type="button"
                      >
                        {dateCell.day}
                      </button>

                      <div className="mt-1 space-y-1">
                        {dayAppointments.slice(0, 2).map((appointment) => {
                          const isChatbot = appointment.source === "BOT";
                          return (
                            <button
                              className={[
                                "w-full rounded border px-1.5 py-1.5 text-left text-[11px] font-semibold transition-colors",
                                isChatbot
                                  ? "border-brand-teal/40 bg-brand-accent-light text-brand-teal hover:bg-brand-accent-light/70"
                                  : "border-slate-300 bg-slate-100 text-slate-700 hover:bg-slate-200"
                              ].join(" ")}
                              key={appointment.itemKey}
                              onClick={() => onDesktopAppointmentClick(appointment)}
                              title={`${appointment.startAt.toFormat(
                                "HH:mm"
                              )} - ${appointment.endAt.toFormat("HH:mm")} | ${
                                appointment.patientDisplayName
                              } | ${appointment.source === "MANUAL" ? "Manual" : "Chatbot"}`}
                              type="button"
                            >
                              <span className="block leading-tight">
                                {appointment.startAt.toFormat("HH:mm")} -{" "}
                                {appointment.endAt.toFormat("HH:mm")}
                              </span>
                              <span className="block truncate leading-tight opacity-80">
                                {appointment.patientDisplayName}
                              </span>
                            </button>
                          );
                        })}
                        {dayAppointments.length > 2 ? (
                          <p className="px-1 text-[11px] font-semibold text-slate-500">
                            +{dayAppointments.length - 2} más
                          </p>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
          {/* Legend */}
          <div className="mt-2 hidden items-center gap-4 sm:flex">
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-brand-teal" />
              <span className="text-[11px] text-slate-500">Chatbot</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-slate-400" />
              <span className="text-[11px] text-slate-500">Manual</span>
            </div>
          </div>
        </div>

        {/* Desktop day detail list */}
        <section className="hidden rounded-lg border border-border-subtle p-2.5 sm:block sm:p-3">
          <h4 className="text-xs font-semibold text-brand-ink sm:text-sm">
            {selectedDayIso !== ""
              ? `Citas del ${luxonModule.DateTime.fromISO(selectedDayIso, {
                  zone: timezone
                }).toFormat("dd LLL yyyy")}`
              : "Citas del día seleccionado"}
          </h4>
          {selectedDayAppointments.length === 0 ? (
            <p className="mt-2 text-xs text-slate-500">No hay citas para este día.</p>
          ) : (
            <div className="mt-2 space-y-1.5 sm:space-y-2">
              {selectedDayAppointments.map((appointment) => {
                const isSelectedAppointment = appointment.itemKey === selectedBookedItemKey;
                const isChatbot = appointment.source === "BOT";
                const isVirtualAppointment =
                  appointment.source === "MANUAL"
                    ? (appointment.manualAppointment?.isVirtual ?? false)
                    : appointment.request?.appointmentModality === "VIRTUAL";
                return (
                  <button
                    className={[
                      "w-full rounded-md border px-2.5 py-2 text-left sm:px-3",
                      isSelectedAppointment && desktopDrawerOpen
                        ? "border-brand-teal bg-brand-accent-light text-brand-teal"
                        : isChatbot
                          ? "border-brand-teal/30 bg-brand-accent-light/50 text-brand-teal hover:border-brand-teal"
                          : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                    ].join(" ")}
                    key={`day-${appointment.itemKey}`}
                    onClick={() => onDesktopAppointmentClick(appointment)}
                    type="button"
                  >
                    <p className="text-xs font-semibold sm:text-sm">
                      {appointment.startAt.toFormat("HH:mm")} -{" "}
                      {appointment.endAt.toFormat("HH:mm")}
                    </p>
                    {appointment.patientDisplayName !== appointment.patientPhone ? (
                      <p className="text-xs">{appointment.patientDisplayName}</p>
                    ) : null}
                    <p className="text-xs text-slate-500">{appointment.patientPhone}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className="text-[11px] uppercase text-slate-500">
                        {appointment.source === "MANUAL" ? "Manual" : "Chatbot"}
                      </span>
                      <span
                        className={[
                          "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                          isVirtualAppointment
                            ? "bg-brand-accent-light text-brand-teal"
                            : "bg-slate-100 text-slate-600"
                        ].join(" ")}
                      >
                        {isVirtualAppointment ? "Google Meet" : "Presencial"}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <p className="text-[11px] text-slate-500 sm:text-xs">
          Zona horaria de visualización: {timezone}
        </p>
      </div>
    </article>
  );
}

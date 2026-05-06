"""Scheduling sub-modules package.

Each sub-module owns a coherent slice of the scheduling domain:
  - helpers.py        — pure utility functions (normalisers, finders, DTO builder).
  - slot_proposals.py — consultation submission, review, slot selection, escalation.
  - booking.py        — book + calendar event, archive subsession, cancel, update payment, change modality.
  - reschedule.py     — bot-driven reschedule flow (submit + confirm).
  - payment_approval.py — approve_payment (normal flow + reminder-reply branch).
  - transitions.py    — handoff, close session, attendance confirmation, auto-close.

The public API surface lives on SchedulingService in the parent module
(scheduling_service.py).  Sub-modules expose module-level functions only —
no classes — and receive all dependencies as arguments.
"""

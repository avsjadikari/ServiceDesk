# Experiments

Every shipped change carries a pre-committed metric. Measured before/after; judged after the window.

## Status-change feedback (K1/K6)

- **Shipped:** 2026-10-09 — status/assign dropdowns now require explicit Apply; human label in flash.
- **Metric:** accidental status hops per resolved ticket (status_change audit events >1 in 24h, counted from `audit_log`). Target: no regression vs pre-fix baseline. Pre-commit rationale: instant-submit made brush-over selects land wrong statuses; explicit Apply is the recovery surface.
- **Window:** 2 weeks post-ship. Judge: holistically with agent feedback.

## Comment + edit feedback (K4/K5)

- **Shipped:** 2026-10-09 — empty comment flashes an error; edit page shows field errors.
- **Metric:** none mechanical (no telemetry on failed submits). Judge: agent reports — count "silent failures" mentions in support/complaints channel; expect zero.

## Backlog candidate experiments

- K3 stepper vs dropdown label alignment — metric: time on view page for agents in `pending`.
- K7 category forced-value — metric: category correction rate on edit.

## Submit-guard (M1)

- **Shipped:** 2026-10-09 — all form submits disable + spinner (`main.js:initSubmitGuards`); board "Save & move" disabled until settle.
- **Metric:** duplicate comment/audit/email count per 100 status changes (audit_log `status_change` bursts >1 within 10s window). Target: 0. Pre-commit rationale: double-click on 300ms POSTs duplicates data silently.
- **Window:** 2 weeks. Note: no JS test infra in repo; guarded by node --check + smoke.
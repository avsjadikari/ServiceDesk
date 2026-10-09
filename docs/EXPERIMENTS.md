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
- U4 board keyboard a11y, U5 input maxlength — metric: none pre-committed until shipped.

## Ticket search (U1)

- **Shipped:** 2026-10-09 — `q` on index filter bar; ilike over number/title/description/category.
- **Metric:** share of index views that carry `q` (findability pain proxy). Baseline 0 (feature new). Target: plateau above 5% = search adopted by agents in the daily loop.
- **Window:** 2 weeks. Judge with U2/U3 (nav highlight, filter labels) against complaints channel.

## Reassurance copy (Phase 6, made-to-stick)

- **Shipped:** 2026-10-09 — created/status emails rewritten to handover + plain-language gloss; portal empty states, submission flash now name the deadline; Fixed latent bug: `_notify` never passed `ticket`, so ALL ticket emails silently never sent; portal submission now sends the created email.
- Against SUCCESs (Quick Diagnostic ~23/60 → target ≥35/60): Simple/Concrete via deadline + track link; Credible via honest deadline + "we'll tell you why"; Emotional via handover framing; no Unexpected/Stories forced on transactional mail.
- **Metric:** creator visits the portal ticket within 24h of a status email (reassurance = proof check-in). Measured from `TicketAudit`/page access signals; baseline 0 (emails were dead). Target: ≥30%.
- **Outcome metric (2 wk):** resolved-ticket reopen rate (<7d) — confidence that "resolved" reads as real, not silence.
- **Judge with:** complaints channel + reopen-rate before/after.

## Submit-guard (M1)

- **Shipped:** 2026-10-09 — all form submits disable + spinner (`main.js:initSubmitGuards`); board "Save & move" disabled until settle.
- **Metric:** duplicate comment/audit/email count per 100 status changes (audit_log `status_change` bursts >1 within 10s window). Target: 0. Pre-commit rationale: double-click on 300ms POSTs duplicates data silently.
- **Window:** 2 weeks. Note: no JS test infra in repo; guarded by node --check + smoke.
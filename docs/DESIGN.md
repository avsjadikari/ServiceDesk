# Design

## UX Audit Findings

Source: improve-app Phase 2/3 audits (design-everyday-things, then ux-heuristics deferred after Phase 3). Scoring per DOET Quick Diagnostic.

### Score: 5/10 → 7/10 (post-fix)

Failing rows: feedback/evaluation ❌, error recovery ◐, constraints ◐.

| # | Severity | Finding | Status |
|---|---|---|---|
| K1 | 3 | Status + assign dropdowns auto-submit on `onchange` — browsing = instant commit, no undo; slip lands in audit trail and pollutes `resolved_at`/`closed_at` | **shipped** (explicit Apply buttons) |
| K4 | 3 | Empty comment → silent redirect, typed text lost, no message | **shipped** (danger flash) |
| K5 | 2 | Edit page renders no field errors (create page does) — silent re-render | **shipped** (error blocks) |
| K6 | 1 | Raw status slug leaked in success flash ("updated to in_progress") | **shipped** (STATUS_LABELS) |
| K3 | 2 | Stepper has 5 steps, dropdown 6 statuses; `pending` not a step, shows "In Progress" dot active; board has separate "Pending / Waiting" column | backlog (label-model alignment) |
| K7 | 1 | TicketForm.category forces a value (defaults "Hardware"); no "Uncategorized" | backlog |
| K1b | 2 | Dropdown allows every lifecycle transition incl. resolved→new at a click; no lifecycle gating | backlog (constraint work) |

## Microinteractions (Phase 4)

Scored the agent submit moments (create / comment / upload / status Apply / assign Apply / board Save & move) ≈ 7/10 — failing rows: trigger-state visibility + no double-submit guard.

| # | Fix | Status |
|---|---|---|
| M1 | Global submit guard in `main.js` (`initSubmitGuards`): form submit disables the button + shows spinner — kills duplicate tickets/comments/audits/emails; board modal "Save & move" disabled until `Promise.all` settles | **shipped** |
| M2 | Stepper "just moved" pulse on status change | skipped (needs prev-status plumbing) |
| M3 | Live title/comment char counters | skipped (clutter; add if 200-char limit hit) |

## Heuristic sweep (Phase 2, ux-heuristics)

Scored 5/10 (Quick Diagnostic: search ∅, you-are-here, undo-in-place partial, keyboard partial).

| # | Sev | Finding | Status |
|---|---|---|---|
| U1 | 3 | No free-text ticket search; index copy promises one | **shipped** (`q` field, ilike across number/title/description/category) |
| U2 | 2 | No "you are here" nav highlight | **shipped** (endpoint-based `active`) |
| U3 | 2 | 4 unlabeled filter dropdowns | **shipped** (labels + search box) |
| U4 | 2 | Board drop is mouse-only; keyboard a11y limited | backlog |
| U5 | 1 | No `maxlength` on title/desc inputs (200-char limit bites post-submit) | backlog |

### Strengths (protect)
- Board: optimistic move + confirm modal + mandatory comment + cancel/restore = correct error recovery (`board.html:292-348`).
- Constraint present: assign picker hidden for non-"assigned" columns; assign select hidden on closed tickets.

## Change Log

| Date | Change |
|---|---|
| 2026-10-09 | K1/K4/K5/K6 shipped (269 tests green). Board confirmed as the reference interaction model. |
# Improve App Plan

## Context

- **Date started:** 2026-10-09
- **App:** ServiceDesk — Flask IT ticketing (tickets, SLA, assets, KB, analytics, self-service portal). 50+ active users, real production data, internal team tool.
- **Worst failure:** data loss / wrong SLA (code quality, already hardened — see IMPROVE-CODE-QUALITY-PLAN.md, 10 phases done).
- **This journey:** product experience — what users feel. Code-level causes route back to the code journeys.
- **Hired job (intake, user's words):** "When something breaks, I need the IT team to own my request and show it's being handled, so I can get back to work."
- **Roughest areas (intake):** amateur UI/visual hierarchy · confusing flows/labels · dead-feeling interactions · weak/jargon copy · perceived slowness · unconvincing badge/count surfaces.
- **Evidence (intake):** support tickets/complaints · built-in analytics · (usability recordings/reviews: none held). Continuous-discovery optional phase noted — no weekly user contact yet.
- **Platform:** web only (Flask/Jinja/Bootstrap) → Phase 8 applies; ios-hig-design skipped.
- **Leak focus (intake):** agent ticket workflow (create / update-status / assign).
- **Product docs:** none — CUSTOMER.md, DESIGN.md, POSITIONING.md, PRODUCT.md, EXPERIMENTS.md created fresh as each phase lands.

## Phase Status

| Phase | Skill | Status | Artifact | Date |
|---|---|---|---|---|
| 1 — Re-anchor on the job | jobs-to-be-done | done | CUSTOMER.md (GATE) | 2026-10-09 |
| 2 — Remove friction | ux-heuristics | deferred: user routed to Phase 4; run after Phase 4 | DESIGN.md + EXPERIMENTS.md | 2026-10-09 |
| 3 — Design out errors | design-everyday-things | done | DESIGN.md + EXPERIMENTS.md | 2026-10-09 |
| 4 — Make it delightful | microinteractions | done | DESIGN.md + EXPERIMENTS.md | 2026-10-09 |
| 4 — Look as clear as it works | refactoring-ui | pending | DESIGN.md + EXPERIMENTS.md | |
| 5 — Make actions feel alive | microinteractions | pending | DESIGN.md + EXPERIMENTS.md | |
| 6 — Sharpen the words | made-to-stick | pending | POSITIONING.md + EXPERIMENTS.md | |
| 7 — Persuade honestly | influence-psychology | pending | POSITIONING.md + EXPERIMENTS.md | |
| 8 — Feel fast where touched | high-perf-browser | pending | DESIGN.md + EXPERIMENTS.md | |
| 9 — Brutal end-to-end review | steve-jobs-design-review | pending | PRODUCT.md + DESIGN.md + EXPERIMENTS.md | |

Optional rows: continuous-discovery (evidence is thin: add when a phase needs weekly user contact) · improve-retention (activation friction if audits find it) · web-typography (text-heavy? decide at Phase 6) · lean-ux (risky fix wants a cheap experiment).

Statuses: pending · in-progress · awaiting-evidence · done · deferred: reason · skipped: reason

## Key Decisions

| Date | Phase | Decision | Rationale |
|---|---|---|---|
| 2026-10-09 | Intake | Job = end-user reassurance ("own my request, show it's being handled"), not agent-tool framing | User picked the end-user hire; agent workflow is the leak focus but serves this job |
| 2026-10-09 | Intake | All roughness holds (UI, flows, interactions, copy, speed, badges) → run phases 1-9 in order | Evidence order: re-anchor before polish; no visual change without a Phase 1-3 finding |
| 2026-10-09 | Intake | Phase 8 kept (web surface); ios-hig skipped | Platform is web only |
| 2026-10-09 | Intake | Phase 7 kept, scoped to badges/counts/praise surfaces (helpful counts, view counts, SLA "Overdue" badges) | Intake: "some (badges, praise, counts)" — every claim must be true |
| 2026-10-09 | Intake | Leak target = agent ticket workflow (create/status/assign) | Most complaints; targets Phases 2-3, 5, 8 |
| 2026-10-09 | 1 | Job statement approved (decision 1) — no product name; job survives without the app | GATE passes; CUSTOMER.md written |
| 2026-10-09 | 1 | **Emotional dimension declared worst (decision 2)** — relief/reassurance is the underdelivered hire; functional works, social has a reference number | Sets Phase 2-3 target: reassurance + feedback, not form logic |
| 2026-10-09 | 1 | Leak = **Little Hire** (decision 3) — daily submission/status loop, not adoption | Internal tool: no acquisition problem; complaints sit in the daily agent workflow |
| 2026-10-09 | 1 | No product docs existed → create each file at phase exit from the skeleton | Artifact discipline: extend, never create until named |

## Next Actions

- [x] Phase 1 (GATE, 2026-10-09): done — CUSTOMER.md (job statement, dimensions, forces, hire moments, alternatives). Journey target set: **emotional dimension + Little Hire** → daily loop reassurance.
- [x] Phase 3 (2026-10-09): done — K1/K4/K5/K6 shipped (explicit Apply, error feedback, human labels). DESIGN.md 5/10→7/10.
- [x] Phase 4 (2026-10-09): done — M1 submit-guard shipped (double-submit + loading state).
- [ ] Phase 2 entry decision (ux-heuristics): survey labels/filters/board for Nielsen violations; severity × frequency ordering. DESIGN.md + EXPERIMENTS.md.
- [ ] Phase 5+ entry per journey order, or direct to user's next priority.
- [ ] Every shipped change lands in EXPERIMENTS.md with a pre-committed metric.
- [ ] Optional: continuous-discovery if the audit needs weekly user contact rather than current evidence.
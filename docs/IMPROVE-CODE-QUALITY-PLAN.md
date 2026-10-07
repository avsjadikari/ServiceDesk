# Improve Code Quality Plan

## Context

- **Date started:** 2026-10-08
- **App:** ServiceDesk — Flask IT ticketing (tickets, SLA, assets, KB, analytics, self-service portal). Worst failure: data loss / wrong SLA.
- **Stack:** Flask + SQLAlchemy + WTForms; SQLite (dev) / PostgreSQL (prod).
- **Production:** Yes, 50+ active users, real data.
- **Outbound dependencies:** Email (SMTP) + external APIs.
- **Starting modules (three-axis heuristic):** tickets, auth, analytics, knowledge+portal — Phase 1 begins with **tickets** (core domain, first target).
- **Test baseline:** 11 test files, `pytest` — 130 passed in 26s (venv: `.venv`, created 2026-10-08 via `python3 -m venv --without-pip` + `pip --python`, host lacks `python3.14-venv`).
- **Scope batch 1:** Phases 1-3 first, reassess before 4+. Phase 7 required before further launch work (production users exist) — never skipped.

## Phase Status

| Phase | Skill | Status | Artifact | Date |
|---|---|---|---|---|
| 1 — Build the safety net | working-with-legacy-code | done | TESTING.md + TECH-DEBT.md (GATE) | 2026-10-08 |
| 2 — Make the code readable | clean-code | in-progress | TECH-DEBT.md | |
| 3 — Apply named refactorings | refactoring-patterns | pending | TECH-DEBT.md | |
| 4 — Reduce complexity | software-design-philosophy | pending | TECH-DEBT.md | |
| 5 — Draw the architecture boundary | clean-architecture | pending | ARCHITECTURE.md | |
| 6 — Lock in the habits | pragmatic-programmer | pending | TECH-DEBT.md | |
| 7 — Make it survive production | release-it | pending | RELIABILITY.md | |
| 8 — Size for real load | system-design | pending | ARCHITECTURE.md + RELIABILITY.md | |
| 9 — Get the data layer right | ddia-systems | pending | ARCHITECTURE.md | |
| Optional — Domain language | domain-driven-design | pending | ARCHITECTURE.md | |

Statuses: pending · in-progress · awaiting-evidence · done · deferred: <reason> · skipped: <reason>

## Key Decisions

| Date | Phase | Decision | Rationale |
|---|---|---|---|
| 2026-10-08 | Intake | Risk = data loss / wrong SLA | Frames Phase 9 (concurrency) and SLA logic as high-priority pin targets |
| 2026-10-08 | Intake | Phase 1 starting module: tickets, then auth/analytics/knowledge+portal | Core domain + listed as next-change targets |
| 2026-10-08 | Intake | Scope batch 1 = Phases 1-3 | Safety net before real users' changes; reassess after Phase 3 |
| 2026-10-08 | Intake | venv without ensurepip (host missing python3.14-venv, sudo interactive) | Test baseline must run locally |
| 2026-10-08 | 1 | Phase 1 scope: all four modules (tickets, auth, analytics, knowledge+portal KB) | User choice at intake |
| 2026-10-08 | 1 | Bug policy: pin wrong behavior + Debt Ledger, never silently fix | User accepted; callers may depend on quirks |
| 2026-10-08 | 1 | Result: 252 tests green, coverage 71%→83%; target modules 99-100% | 13 bugs ledgered |

## Next Actions

- [x] Phase 1 entry decision (agent + user, 2026-10-08)
- [ ] Phase 2 entry decision (clean-code)
- [ ] Optional: `sudo apt install python3.14-venv` to make `.venv` fully standard (user, any time)

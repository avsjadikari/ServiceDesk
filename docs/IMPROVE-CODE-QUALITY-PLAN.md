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
| 2 — Make the code readable | clean-code | done | TECH-DEBT.md | 2026-10-08 |
| 3 — Apply named refactorings | refactoring-patterns | done | TECH-DEBT.md | 2026-10-08 |
| 4 — Reduce complexity | software-design-philosophy | done | TECH-DEBT.md | 2026-10-08 |
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
| 2026-10-08 | 2 | tickets.py audit ~6.7/10 → apply fixes 1-5 + int()/email behavior fixes now | Clear wins; user approved |
| 2026-10-08 | 2 | Conventions: `_agent_users()`, guard clauses, `_to_int()`/`type=int`, no `pass`-dead branches, `_notify()` email guard; enums via `app/enums.py` tuples in new code | Reuse/applied; enum migration = Phase 3 |
| 2026-10-08 | 2 | No CI gate now (structure+behavior commits kept separate) | Manual discipline still viable at 1 dev |
| 2026-10-08 | 3 | Refactoring-patterns score (tickets.py): ~6.7 → 8/10; tuition: each step green-committed separately | Named refactorings: Move Method (`promote_status_if_new`), Extract Method (`_create_ticket`, `_apply_form_to_ticket`, `_apply_status_timestamps`), Replace Magic Number (`SNIFF_LENGTH`), enum-driven board columns |
| 2026-10-08 | 3 | Phase 3 does NOT change behavior: defect fixes stay pinned+ledgered (unassign-resets-status, status whitelist) — those surface in Phase 6/7 hardening | Preserved φ arrow: structural change never mixed with behavioral change |
| 2026-10-08 | 4 | Philosophy-of-software-design audit (ticket core): ~5.5 → 8/10. Applied: info-hiding of ticket audit mapping (`log_ticket_audit`), enum-driven metrics/colors, module-header contract for `utils.py` | Diagnostic rows 1-4,6,8 now pass; residual: `utils.py` grab-bag split + `auth.py` 796-line module size belong to Phase 5 (boundaries) |
| 2026-10-08 | 4 | Module depth verdicts: `email_utils` (SMTP+async queue) deep ✓; `models.py` owns DB constraints ✓; `__init__.py` wiring coil — revisit after Phase 5 map | Depth over size: judged by interface-vs-implementation, not line count |

## Next Actions

- [x] Phase 1 entry decision (agent + user, 2026-10-08)
- [x] Phase 2 entry decision (clean-code, 2026-10-08)
- [x] Phase 3 entry decision (refactoring-patterns, 2026-10-08) — status-promote helper, enum constants, route decomposition, SNIFF_LENGTH, corrected docstring; 3 commits, 254 tests green each step
- [x] Phase 4 entry decision (software-design-philosophy, 2026-10-08) — audit mapping centralized, enum-driven utils, module contracts stated; 8/10; settled the deferral of utils/auth size to Phase 5
- [ ] Phase 5 entry decision (clean-architecture) — produce ARCHITECTURE.md: draw module boundaries & dependency direction across app/ (routes ↔ models ↔ utils ↔ email/security/settings); target `utils.py` grab-bag split + `__init__.py` coil
- [ ] Optional: `sudo apt install python3.14-venv` to make `.venv` fully standard (user, any time)

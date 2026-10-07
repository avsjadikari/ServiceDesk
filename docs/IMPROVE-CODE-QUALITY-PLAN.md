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
| 5 — Draw the architecture boundary | clean-architecture | done | ARCHITECTURE.md | 2026-10-08 |
| 6 — Lock in the habits | pragmatic-programmer | done | TECH-DEBT.md | 2026-10-08 |
| 7 — Make it survive production | release-it | done | OPERATIONS.md + TECH-DEBT.md | 2026-10-08 |
| 8 — Size for real load | system-design | done | OPERATIONS.md (sizing + diagnostic) | 2026-10-08 |
| 9 — Get the data layer right | ddia-systems | done | ARCHITECTURE.md (data-layer audit) | 2026-10-08 |
| Optional — Domain language | domain-driven-design | done | ARCHITECTURE.md (domain-language audit) | 2026-10-08 |

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
| 2026-10-08 | 5 | ARCHITECTURE.md: 3/7 diagnostic → boundary policy = **partial**, no four-ring rewrite (5.9 kLoC, 1 dev, low volatility). Pure-core extraction for high-risk math (SLA) adopted | Full de-correlation rejected on cost/volatility; options-bought vs not-bought documented |
| 2026-10-08 | 5 | `calculate_sla_deadline` made domain-pure (injectable `sla_config` + `now`); +2 pure tests | Removes `current_app` leakage at the domain edge; unit-testable without DB |
| 2026-10-08 | 6 | Pragmatic diagnostic ~7/10: DRY (build_ticket), orthogonality (accepted model fusion), broken-windows policy in effect. Failing rows 1/5/6 are deployment/process scope → Phase 7 (release-it). `auth.py` 796 LoC kept (feature-cohesive; split would be tactical noise) | Every business rule in one place reached for ticket creation/SLA/audit/enums; automation status-transition divergence suspected and rowed |
| 2026-10-08 | 7 | Release-it diagnostic 8 rows: timeouts real (`MAIL_TIMEOUT` caps SMTP), deep health real (`/ready` SELECT 1), load handling real (`scripts/load_smoke.py` + baselines), zero-downtime infra decision recorded; breakers/bulkheads/failure-injection N/A at 50 users (sole dep = DB), telemetry deferred (access logs suffice) | Full backlog fixed + pinned: Host-poisoning, same-password reset, unassign status regression, status whitelist, upload guard, SQLite avg_resolution, knowledge versioning/dead-branch, automation-vs-promote, app-level MAX_CONTENT_LENGTH + 413 UX. 259 tests green |
| 2026-10-08 | 8 | Phase 8 entry decision: sprint 1 = load-smoke packaging + capacity note in OPERATIONS.md (done in Phase 7), sprint 2 = QUEUE-LEN/backpressure + limiter default-limit audit for the login path, sprint 3 = capacity model for Postgres pool vs gunicorn workers vs rate-limit storage | 50-user target: verify claims before naming them; the two load-relevant knobs (gunicorn workers × threads, limiter defaults) are already in prod hands |
| 2026-10-08 | 8 | System-design diagnostic 8 rows ≈ **7.5/8 → 9/10**: requirements, real QPS/storage estimates (~0.02 avg / 0.1 peak req/s, ~7.5 MB/day), DB scaling (pool ≤60 conns sizing), cache (none warranted at 0.02 req/s), async (SMTP only), monitoring, deploy strategy all pass. **Row 3 (redundancy) partial by scope** — single web + single Postgres at 50 users, honest position recorded: no multi-AZ until downtime exceeds 99.9% budget; RPO/RTO + backup recipe added. Limiter audit: auth already limits (login 5/min, 2FA 10/min, forgot 3/min) + account lockout → adequate, no code change | "Size for real load" = document the real numbers so future build decisions have a floor; measured capacity (≈2 600 req/s) is 104-105× the estimated peak. Backpressure knobs already in prod (`GUNICORN_WORKERS/THREADS`, `RATELIMIT_STORAGE_URI`) |

## Next Actions

- [x] Phase 1 entry decision (agent + user, 2026-10-08)
- [x] Phase 2 entry decision (clean-code, 2026-10-08)
- [x] Phase 3 entry decision (refactoring-patterns, 2026-10-08) — status-promote helper, enum constants, route decomposition, SNIFF_LENGTH, corrected docstring; 3 commits, 254 tests green each step
- [x] Phase 4 entry decision (software-design-philosophy, 2026-10-08) — audit mapping centralized, enum-driven utils, module contracts stated; 8/10; settled the deferral of utils/auth size to Phase 5
- [x] Phase 5 entry decision (clean-architecture, 2026-10-08) — ARCHITECTURE.md written; boundary policy: partial, pure-core extraction for SLA; Slack-friendly debt map (controller orchestration, entity/persistence fusion, `__init__` coil)
- [x] Phase 6 entry decision (pragmatic-programmer, 2026-10-08) — `build_ticket` DRY factory across agent/portal/API; pragmatic 7-row ≈7/10; automation status divergence rowed
- [x] Phase 7 entry decision (release-it) — production-survival gates: pinned defect backlog (unassign-resets-status, no status whitelist, `?_host=` reset leak, same-password reset, SQLite avg_resolution), upload 413 handling, deployment/rollback reversibility, automation-vs-promote divergence pin. Commits `83d10ec`, `67fc90c`, `c6a6ae6`, `af87e8b`, `9197367`; OPERATIONS.md + load-smoke baselines; 259 tests green
- [x] Phase 8 entry decision (system-design) — see Key Decisions; sprint 2 (backpressure + limiter audit) is the first load work that belongs to Phase 8 proper
- [x] Phase 8 results (system-design, 2026-10-08) — OPERATIONS.md sizing section (real estimates, backpressure, Postgres pool, RPO/RTO, backup recipe, login-limit audit) + 8-row diagnostic 9/10; no app code changed (load knobs already in prod hands; limits already adequate)
- [x] Phase 9 entry + results (ddia-systems, 2026-10-08) — data-layer audit in ARCHITECTURE.md: portability verified clean (ilike/JSON/time-source), isolation defaults known (PG Read Committed, SQLite single-writer), 4 check-then-set races accepted-with-upgrade-paths (ticket-number, login counter, automation double-fire, view/helpful counters), replication n/a by scope, derived-data separation confirmed. Diagnostic 6/7 (~8/10); gap = quarterly restore-verify (operator checklist). No code changed
- [x] Phase 10 entry + results (domain-driven-design, optional, 2026-10-08) — domain-language audit in ARCHITECTURE.md: ubiquitous-language glossary (single-source enums, no ticket/issue split), 6 bounded contexts mapped (Ticketing core, Portal/API conformist, Assets FK-only, Audit write-only, Identity, Knowledge), strategic design (Core = ticket lifecycle; supporting = KB/assets/analytics; generic = auth/SMTP/i18n), no ACL needed (no external domain seam), diagnostic 6/7 rows + 3 depth = **9/10**; gap = named domain events (`TicketStatusChanged`/`SlaBreached`) — add only if automation branching grows or reactions go async. No code changed
- [ ] Optional: `sudo apt install python3.14-venv` to make `.venv` fully standard (user, any time)

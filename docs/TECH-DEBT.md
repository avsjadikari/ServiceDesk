# Technical Debt

## Debt Ledger

| Item | Location | Type | Risk | Effort | Priority | Status |
|---|---|---|---|---|---|---|
| Unassign resets any status to `new` (`in_progress` → `new`) | `routes/tickets.py:199-201` | logic bug | high | S | high | **resolved 2026-10-08** — only `None`/`new`/`assigned` regress to `new`; other statuses preserved (`67fc90c`) |
| No status whitelist; bogus status string → unhandled IntegrityError 500 | `routes/tickets.py:224` | validation | med | S | high | **resolved 2026-10-08** — whitelist vs `TICKET_STATUSES`; JSON 400, form flash "Invalid status." (`67fc90c`) |
| Unguarded `int(asset_id)` → 500 (sibling `assign` guards same input) | `routes/tickets.py:351` | robustness | med | S | med | **resolved 2026-10-08** — `_to_int()` guard + flash "Invalid asset." (`acaaceb`) |
| Unguarded `int(?assigned_to)` query param → 500 | `routes/tickets.py:65` | robustness | med | S | med | **resolved 2026-10-08** — `request.args.get(..., type=int)` coerces to None (`acaaceb`) |
| Email send failure after commit → HTTP 500 (network/SMTP error kills a request that already persisted) | `routes/tickets.py` new / update-status / assign / comment | robustness | med | S | med | **resolved 2026-10-08** — `_notify()` wrapper logs + continues (`acaaceb`) |
| Plain form field named `file` passes WTForms → AttributeError 500 | `routes/tickets.py:411-412` | robustness | med | S | med | **resolved 2026-10-08** — `FileStorage` isinstance guard + flash "Invalid file." (`67fc90c`) |
| Upload size check reads part-level Content-Length; ineffective (real oversize hits Flask 413 first) | `routes/tickets.py:417-419` | security gap | med | M | high | **resolved 2026-10-08** — app-level `MAX_CONTENT_LENGTH` enforcement (`enforce_request_size_limit`) raises 413 before routes; handler gives JSON/friendly-redirect UX. Part-level pre-check kept, pinned (`af87e8b`) |
| Docstring says assignee can view ticket; code checks `created_by` only | `routes/tickets.py:368-375` | doc/code drift | low | S | low | **resolved 2026-10-08** — docstring corrected (`9140c56`, same fix as Smell 32) |
| Reset URL leaks junk `?_host=` query; Host-poisoning guard inert | `routes/auth.py:33-41` | security gap | high | S | high | **resolved 2026-10-08** — `_external_url` drops `_host`; SERVER_NAME secures host when set (`83d10ec`) |
| Same-password reset succeeds: guard compares plaintext vs stored hash, never fires (and is unreachable for real hashes anyway) | `routes/auth.py:264` | logic bug | med | S | med | **resolved 2026-10-08** — `user.check_password(...)` guard; same-password reset rejected (`83d10ec`) |
| Unreachable redirect dead branch (non-agents abort earlier) | `routes/knowledge.py:99` | dead code | low | S | low | **resolved 2026-10-08** — branch removed (`67fc90c`) |
| Version semantics inconsistent: create stores NEW content at v1, edit stores OLD content at bumped number | `routes/knowledge.py:86-93` + edit | logic inconsistency | med | S | med | **resolved 2026-10-08** — edit stores post-edit content at the bumped version (`67fc90c`) |
| `helpful()` open to any authenticated user; edit/delete agent-only | `routes/knowledge.py:160-164` | authz inconsistency | low | S | low | **accepted 2026-10-08** — every authenticated user may mark an article helpful by design; edit/delete stays agent-only. No code change |
| `avg_resolution_hours` garbage on SQLite (`extract('epoch', ...)` compiles to string math → constant `-58574100.0`); DB-side date math not portable | `utils.py:170-183` (surfaces `routes/analytics.py:110`) | portability bug | high (wrong analytics on SQLite) | M | high | **resolved 2026-10-08** — computed in Python from `Ticket.resolution_time` (`67fc90c`) |

## Smell Inventory

| Smell | Location | Refactoring | Status |
|---|---|---|---|
| Ticket audit-row wiring repeated 8× (`log_audit(current_user.id, action, "ticket", id, id, ...)`) | `routes/tickets.py` create/update/status/assign/comment/link-asset/upload/download | Extract `log_ticket_audit(ticket, action, details)` — hides the "a ticket maps to entity_type=ticket, entity_id=ticket_id=ticket.id" decision in one place | **resolved 2026-10-08** (`3c5c611`) |
| `utils.py` = multi-concern grab-bag (numbering, SLA, audit, colors, automation, metrics, upload sniff) | `app/utils.py` | Module header now states its contract; each helper is deep with a simple interface. Further split (e.g. `analytics.py` helpers → analytics) deferred until boundaries firm up | **documented; split deferred → Phase 6** |
| Ticket-creation wiring duplicated ×3: tickets.py `_create_ticket`, portal.py:93, api.py:92 each re-resolve assigned_to + SLA | routes/tickets, portal, api | `build_ticket(...)` domain factory in utils.py — numbering, SLA, field mapping, promote-on-assign in one place | **resolved 2026-10-08** (`4e3dcf2`) |
| Status/priority/ticket literals repeated in metrics & color maps | `app/utils.py` | `TICKET_OPEN_STATUSES` added to enums; metrics/SLA/colors derive from enum tuples | **resolved 2026-10-08** (`3c5c611`) |
| Status-promote duplication `if status == "new": status = "assigned"` ×3 | `routes/tickets.py` new / edit / assign | Extract `Ticket.promote_status_if_new()` (handles None + "new") | **resolved 2026-10-08** (`4ae319d`, `9140c56`) |
| Magic status/priority/type strings | `routes/tickets.py`, `models.py`, forms, templates | Stop using bare literals in logic; reference `app/enums.py` tuples | **resolved (routes+models)** `4ae319d`/`efcda2d` — board columns + SLA check + column defaults now enum-driven. Still inline: `forms.py` choice labels (no label data in enums), templates render status/priority strings passed from routes |
| Wrong docstring on `_can_view_ticket` (claims assignee can view; code checks creator only) | `routes/tickets.py:368` | Fix docstring — assignees are always agents here, so no separate branch exists | **resolved 2026-10-08** (`9140c56`) — behavior unchanged |
| Upload size branch ineffective (part-level Content-Length only; Flask 413 fires first) | `routes/tickets.py` upload_attachment | Revisit with `LimitBytes`/413 handling — robustness, belongs with Phase 7 (release-it) | **resolved 2026-10-08** — app-level size cap + 413 handler (`af87e8b`) |
| Sniff sample length bare literal `512` | `routes/tickets.py` upload_attachment | `SNIFF_LENGTH = 512` constant | **resolved 2026-10-08** (`9140c56`) |
| Duplicated "rejected attachment" warning-log block ×2 | `routes/tickets.py` upload_attachment | Rule of Three: extract `_log_rejected_upload(...)` on 3rd occurrence | open (tolerated at 2) |
| Status-transition knowledge split: `_execute_automation_rule` sets `status="assigned"` unconditionally; `promote_status_if_new` promotes only when None/"new" | `app/utils.py:100` + `models.py` | Suspected behavior divergence (automation assign on an in-progress ticket re-opens it as "assigned"). Decide in Phase 7 hardening; pin with a test first | **resolved 2026-10-08** — automation assign now uses `promote_status_if_new`; pin `TestAutomationAssign` (`c6a6ae6`) |
| CRLF/LF mixed line endings | `tests/test_tickets.py` (pre-existing) | Normalize to LF if repo adopts a formatter | skip unless ruff added |

## Sprout / Wrap Register

None yet.

## Debt Budget & Broken-Windows Policy

(Phase 6)

## Adopted Conventions

- **Characterization policy (2026-10-08):** bugs found while pinning behavior are marked `# CHARACTERIZED` in the test, ledgered here, and never silently fixed — callers may depend on the quirk; fixes are deliberate, separate changes.
- **Naming/structure (2026-10-08, Phase 2):** shared queries → module-level helpers (`_agent_users()`); guard clauses over tangled branches; no bare `int()` conversion on request input (`_to_int()` / `request.args.get(..., type=int)`); no `pass`-dead branches; failing email sends must not fail the request (`_notify()` wrapper, log + continue).
- **Enums (2026-10-08, Phase 2):** new code uses `app/enums.py` tuples (`TICKET_STATUSES`, `TICKET_PRIORITIES`, `TICKET_TYPES`) instead of bare status/priority/type strings; DB columns stay String-typed (`CheckConstraint` built from the tuples) — migrating existing routes to reference them is Phase 3 work.

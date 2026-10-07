# Technical Debt

## Debt Ledger

| Item | Location | Type | Risk | Effort | Priority | Status |
|---|---|---|---|---|---|---|
| Unassign resets any status to `new` (`in_progress` → `new`) | `routes/tickets.py:199-201` | logic bug | high | S | high | open |
| No status whitelist; bogus status string → unhandled IntegrityError 500 | `routes/tickets.py:224` | validation | med | S | high | open |
| Unguarded `int(asset_id)` → 500 (sibling `assign` guards same input) | `routes/tickets.py:351` | robustness | med | S | med | open |
| Unguarded `int(?assigned_to)` query param → 500 | `routes/tickets.py:65` | robustness | med | S | med | open |
| Plain form field named `file` passes WTForms → AttributeError 500 | `routes/tickets.py:411-412` | robustness | med | S | med | open |
| Upload size check reads part-level Content-Length; ineffective (real oversize hits Flask 413 first) | `routes/tickets.py:417-419` | security gap | med | M | high | open |
| Docstring says assignee can view ticket; code checks `created_by` only | `routes/tickets.py:368-375` | doc/code drift | low | S | low | open |
| Reset URL leaks junk `?_host=` query; Host-poisoning guard inert | `routes/auth.py:33-41` | security gap | high | S | high | open |
| Same-password reset succeeds: guard compares plaintext vs stored hash, never fires (and is unreachable for real hashes anyway) | `routes/auth.py:264` | logic bug | med | S | med | open |
| Unreachable redirect dead branch (non-agents abort earlier) | `routes/knowledge.py:99` | dead code | low | S | low | open |
| Version semantics inconsistent: create stores NEW content at v1, edit stores OLD content at bumped number | `routes/knowledge.py:86-93` + edit | logic inconsistency | med | S | med | open |
| `helpful()` open to any authenticated user; edit/delete agent-only | `routes/knowledge.py:160-164` | authz inconsistency | low | S | low | open |
| `avg_resolution_hours` garbage on SQLite (`extract('epoch', ...)` compiles to string math → constant `-58574100.0`); DB-side date math not portable | `utils.py:170-183` (surfaces `routes/analytics.py:110`) | portability bug | high (wrong analytics on SQLite) | M | high | open |

## Smell Inventory

| Smell | Location | Refactoring | Status |
|---|---|---|---|
| (Phase 2+) | | | |

## Sprout / Wrap Register

None yet.

## Debt Budget & Broken-Windows Policy

(Phase 6)

## Adopted Conventions

- **Characterization policy (2026-10-08):** bugs found while pinning behavior are marked `# CHARACTERIZED` in the test, ledgered here, and never silently fixed — callers may depend on the quirk; fixes are deliberate, separate changes.

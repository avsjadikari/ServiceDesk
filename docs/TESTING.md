# Testing

## Test Strategy

- pytest + pytest-flask, temp SQLite per test, CSRF disabled (re-enable per-test where needed — see `TestTwoFactorCsrf` in `tests/test_auth.py`).
- Characterization-first (Feathers): pin observed behavior, not imagined specs. Probe with a deliberately wrong assertion, read the failure, pin the real value.
- Role matrix: admin / agent / regular / anonymous exercised on every authorization branch.
- Green gate: `.venv/bin/python -m pytest` (252 tests, ~69s). Coverage: `pytest --cov=app --cov-report=term-missing`.

## Safety Net Map

| Module | Pinned behaviors | Test files | Gaps |
|---|---|---|---|
| `routes/tickets.py` (99%) | CRUD, filters (`category`, `assigned_to`), status transitions + `resolved_at`/`closed_at`/`first_response_at`, assign/unassign, comments + authz, link-asset, attachment upload validation (size/type/path traversal), download authz, role gates | `tests/test_tickets.py` (51 tests) | dead code: lines 381, 413-414 (unreachable defensive branches) |
| `routes/auth.py` (99%) | login role redirects, 2FA gate, account lockout, password-reset token flow, admin user management, session lifecycle, email send seams | `tests/test_auth.py` (88 tests) | dead code: lines 265-267 (guard unreachable: 162-char hash vs 128-char field cap) |
| `routes/knowledge.py` (99%) | publish/filter/search, version rows, helpful counter, delete authz, portal KB list/view endpoints | `tests/test_knowledge.py` | dead code: line 99 (unreachable redirect — non-agents abort at line 70) |
| `routes/analytics.py` (100%) | role gates (agent vs admin-only audit logs), chart JSON shapes, `days` fallback, SLA + performance endpoint values, audit-log ordering | `tests/test_analytics.py` | none |

## Characterization Backlog

- [ ] `routes/portal.py` 65% — non-KB routes (home, my_tickets, view_ticket, new_ticket) (risk: med)
- [ ] `routes/api.py` 60% (risk: med — external surface)
- [ ] `routes/setup.py` 49% (risk: low — one-time wizard)
- [ ] `routes/assets.py` 67% (risk: med)
- [ ] `routes/main.py` 77%, `email_utils.py` 71%, `sanitize.py` 66% (risk: low-med)

## CI Gates

- `pytest` green required pre-PR (AGENTS.md).
- Coverage baseline 83% total / 99-100% on the four pinned modules, recorded 2026-10-08. Floor enforcement deferred to Phase 2 decision.

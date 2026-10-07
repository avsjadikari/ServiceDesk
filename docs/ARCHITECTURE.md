# ServiceDesk Architecture

Status: **2026-10-08** — Phase 5 (clean-architecture) audit. Live doc; update with boundary changes.

## Context

Flask monolith, 1 maintainer, ~50 active users, real production data. SQLite dev / PostgreSQL prod. Worst failure: data loss, wrong SLA. Volatility: low (single deploy unit, one team). These facts drive the boundary policy below: a full Uncle-Bob four-ring rewrite is rejected; partial + documented boundaries are adopted.

## Module Inventory

| Module | Role | Framework exposure |
|---|---|---|
| `app/__init__.py` | Composition root: factory, config, wiring, temp-title hooks, seed accounts | heavy (intended) |
| `app/routes/*` | HTTP adapters (controllers) + a large share of business orchestration | heavy (intended) |
| `app/forms.py` | Request validation / WTForms | WTForms |
| `app/models.py` | Entities **and** persistence (SQLAlchemy) fused | heavy (accepted) |
| `app/utils.py` | Domain helpers: numbering, SLA, audit, automation, metrics, upload sniff, presentation colors | partial (`current_app` only in SLA defaults) |
| `app/enums.py` | Domain constants (ticket types/statuses/priorities) | none |
| `app/email_utils.py` | SMTP detail + async dispatch queue | heavy (detail, expected) |
| `app/settings_store.py` | `SystemSetting`-backed app config detail | SQLAlchemy (detail) |
| `app/security.py` / `sanitize.py` / `i18n.py` | Password-reset tokens, markdown sanitize, JSON i18n | thin (details) |
| `app/templates/`, `static/`, `translations/` | View layer | Jinja |

## Dependency Direction (as-built)

```
routes/* ──► models.py  utils.py  enums.py  forms.py  email_utils.py  settings_store.py
models.py ──► app(db)  enums.py
utils.py  ──► app(db)  models.py  enums.py
email_utils ──► (flask_mail / smtplib)          (leaf detail)
security / sanitize / i18n                       (leaf details)
app/__init__ ──► everything (composition)
```

- No component cycles. The only `app` inbound edges are the standard Flask idiom
  `from app import db` from models/utils/settings_store/forms — resolved after `db`
  is defined in `create_app`; treated as idiom, not a defect.
- Details (`email_utils`, `settings_store`, `security`, `sanitize`, `i18n`) never
  import routes or each other. Edges point inward. ✔

## Clean-Architecture Quick Diagnostic (7 rows)

| Row | Status | Note |
|---|---|---|
| Business rules testable w/o DB/web/framework | ✗ | Rules live on SQLAlchemy models or request-bound helpers; only SLA deadline + upload sniff are pure |
| Source dependencies point inward | ✔ | No outward edges found (Flask idiomatic `from app import db` excepted) |
| Swap DB without touching business logic | ✗ | Entities and persistence fused in `models.py` |
| Use cases independent of delivery mechanism | ✗ | Orchestration lives in controllers; forms/`request`/`redirect` touch domain paths |
| Framework confined to outermost | ✗ | Flask + SQLAlchemy reach the domain layer by design at this scale |
| Component graph cycle-free | ✔ | Package graph acyclic (ADP holds) |
| Main wires all dependencies | ✔ | `create_app` is the single composition root |

**Score 3/7 → band 3–5** — "persistence/framework dictates structure."

## Boundary Policy (decision)

Full de-correlation (pure entities, repositories, use-case interactors, DTOs
crossing boundaries) is **rejected for this scale**: ~5.9 kLoC, 1 maintainer, low
volatility, no second consumer of the domain. Cost is a rewrite with no testable
payoff. Instead adopt:

1. **Partial boundaries at high-risk logic** — extract *pure* domain functions for
   math-heavy or correctness-critical rules so they run without app/DB:
   - ✔ `calculate_sla_deadline(priority, sla_config, now)` — pure since 2026-10-08.
   - Next candidates (Phase 7/9, only if SLA/analytics correctness drives them):
     `TicketSla` module (breach/resolution/response math), analytics resolution
     portability fix for SQLite.
2. **Keep models as entity+persistence singleton** — acknowledged coupling;
   documented. Revisit only if a second runtime (CLI/worker) must share domain
   without Flask.
3. **Business logic in controllers** — recognized (validation + transitions +
   audit live in `routes/*`). This is the highest-cost debt of the three (Code
   Application/porting or headless testing hurts here). Tracked in TECH-DEBT.
4. **Presenter leakage** — `get_status_color`/`get_priority_color` (Bootstrap class
   mapping) are view-model helpers living in `utils.py`. Tolerated; re-home when
   the view layer grows.

Every boundary buy is deferred-thought: options bought (swap SMTP, re-style
colors, unit-test SLA) vs. options not bought (swap DB, headless use cases).

## Residual Debt (mapped)

| Item | Location | Owner |
|---|---|---|
| Business orchestration in controllers | `routes/tickets.py`, `routes/auth.py` (796 LoC) | Phase 6 (pragmatic-programmer) trims; full extraction only if headless use emerges |
| Entities blended with persistence | `app/models.py` | accepted (policy 2) |
| Composition-root coil | `app/__init__.py` (475 LoC: hooks, seed, error handlers, globals) | chunk into `app/bootstrap/` if it crosses ~600 LoC |
| Domain helpers mixed with presenters/audit | `app/utils.py` | documented contract (Phase 4); split when utils > ~400 LoC |
| `from app import db` idiom | models/utils/settings_store/forms | accepted (Flask norm) |

## Change Log

| Date | Change |
|---|---|
| 2026-10-08 | Initial map, 7-row diagnostic (3/7), boundary policy + debt map. `calculate_sla_deadline` made pure. |
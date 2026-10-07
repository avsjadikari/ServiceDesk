# ServiceDesk Architecture

Status: **2026-10-08** — Phase 5 (clean-architecture) + Phase 9 (ddia-systems) audits. Live doc; update with boundary changes.

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
   - ✔ analytics resolution portability fix for SQLite (Python-side, `67fc90c`).
   - Next candidate (only if SLA/analytics correctness drives it): `TicketSla`
     module (breach/resolution/response math).
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

## Data Layer (DDIA audit, Phase 9)

Relational choice is deliberate: referential integrity (FKs), joins across
audit/tickets, transactional SLA/assignment updates — a ticket domain is
relational by shape. **PostgreSQL prod** (multi-writer, durability) / **SQLite
dev** (zero-config, one file); both spoken through SQLAlchemy. Data is
write-light and read-light (~0.02 req/s — Phase 8), so engine internals
(B-tree, LSM) are not a lever here.

### Portability audit (SQLite ⟷ Postgres)

| Construct | Where | Status |
|---|---|---|
| `ilike` search | knowledge.py / portal.py / api.py | SQLAlchemy emulates on SQLite (`lower() LIKE lower()`); portable |
| `func.extract('epoch', ...)` | (removed) | was SQLite-broken; avg_resolution now Python-side (`67fc90c`) |
| JSON columns | `Article.tags`, `AuditLog.details`, AutomationRule | stored + whole-value, never path-queried → portable |
| Time source | `datetime.utcnow()` everywhere | Python-side, no `func.now()` → portable |
| Unique constraint | `ticket_number` | both engines enforce |

**Verdict: no portability landmines remain.** The only historical one
(`avg_resolution_hours`) is fixed and pinned.

### Isolation, consistency, and accepted races

Engine defaults: **Postgres = Read Committed** (no explicit
`isolation_level` is set); **SQLite = single-writer**, database-level lock.
SQLAlchemy sessions are request-scoped with explicit commits and
`db.session.remove()` on teardown. No `SELECT FOR UPDATE` anywhere — none of
the writes below is safety-critical, so locking is not worth the contention.

Four check-then-set races identified and **accepted at this scale** (each
with a named upgrade):

| Race | Impact now | Upgrade path |
|---|---|---|
| `generate_ticket_number` MAX+1 → unique collision | Extremely rare loud 500, nothing persisted; user retries | Postgres sequence / DB-generated ticket number |
| `record_failed_login` count increment (lost update) | Lockout triggers ≤1 attempt late under simultaneous failures | Atomic `UPDATE failed_login_count = failed_login_count + 1 … RETURNING` |
| Automation rule fires twice on same transition | Duplicate notification/audit row | `SELECT … FOR UPDATE` on the rule or dedup key |
| `view_count` / `helpful_count` increments | Counters undercount under concurrent reads | Atomic `UPDATE … SET n = n + 1` (no read-back) |

Liveness/metrics-grade only — no safety property (data integrity, SLA, access
control) depends on any of them. Revisit if any intersection becomes a real
contention point.

### Replication, partitioning, derived data

- **Replication:** none — single Postgres node by scope (Phase 8:
  no multi-AZ until downtime > 99.9% budget). RPO/RTO + backup recipe in
  OPERATIONS.md. Castable to single-leader + read replicas only if the
  analytics queries become hot.
- **Partitioning/hot keys:** single node; the only hot-row risk is the
  helpful/view counter on a popular article (accepted above). Sharding is
  off the table at 2.7 GB/yr.
- **System of record vs derived data:** analytics are computed on read (no
  materialized aggregates — nothing to invalidate); `sla_deadline` is a
  *denormalized fact* stored at creation so it survives SLA-config changes
  (deliberate); `AuditLog` is append-only; `ArticleVersion` history is
  snapshot-derived. Derivation rules are single-source in utils/models.

### DDIA Quick Diagnostic (7 rows)

| Row | Pass | Note |
|---|---|---|
| DB chosen for requirements, not familiarity | ✔ | relational fit + prod/dev split, documented above |
| Default isolation known; anomalies assessed | ✔ | Read Committed / SQLite single-writer; four races listed + accepted |
| Replication strategy explicit | ✔ | none by scope, deliberately; failover = RPO/RTO doc |
| Hot partition key handled | ✔ | N/A single node; hot-row counters accepted |
| System of record ≠ derived data | ✔ | computed-on-read analytics; stored-deadline fact documented |
| Timeouts/retries tuned | ✔ | `pool_pre_ping` + `pool_recycle` (1800), `MAIL_TIMEOUT`; DB retry unnecessary |
| Failover tested | ✗ | backup recipe untested; quarterly restore-verify is the operator checklist |

**Score ~8/10** (6/7 rows). Gap to 10/10: run the quarterly restore
verification (OPERATIONS.md) and record it here.

## Change Log

| Date | Change |
|---|---|
| 2026-10-08 | Initial map, 7-row diagnostic (3/7), boundary policy + debt map. `calculate_sla_deadline` made pure. |
| 2026-10-08 | Data-layer DDIA audit: portability clean, isolation/races assessed, replication/derived-data decisions, 6/7 diagnostic. |
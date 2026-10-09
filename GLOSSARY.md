# Glossary

Architecture and domain vocabulary for ServiceDesk. Domain *terms* (ticket,
status, priority, SLA, annotation, assignee, audit trail, automation rule) are
defined in `docs/ARCHITECTURE.md §Ubiquitous language`; this file names the
**modules and seams** the architecture leans on, using the shared design
vocabulary (module, interface, implementation, depth, seam, adapter, leverage,
locality).

## Architecture vocabulary

| Term | Meaning |
|---|---|
| module | A unit of code with an interface and an implementation. A **deep** module hides a lot behind a small interface; a **shallow** one's interface nearly matches its implementation. |
| interface | What a caller must know to use a module. The test surface. |
| seam | A place where behaviour can be substituted without editing callers. One adapter is a hypothetical seam; two make it real. |
| adapter | A caller-facing edge (route/controller) that translates input into a module call. |
| locality | Bugs and rules concentrate in one module instead of scattering across adapters. |
| leverage | One interface serving many call sites. |

## Deepened modules (this review)

| Term | Meaning | Home |
|---|---|---|
| ticket lifecycle | The create / transition / assign / annotate operations of a ticket, as one seam. Owns audit-trail wiring, notification, automation, and promote-on-assign; adapter commits. | `app/tickets_lifecycle.py` |
| ticket transition | A validated status move plus its effects: first-response/resolved/closed timestamps, audit row, notify. Entity behaviour lives on `Ticket`; orchestration in the lifecycle module. | `app/models.py` + lifecycle |
| password change | The account operation: hash, clear `must_change_password`, reset lockout, stamp `last_password_reset_at` — one invariant, always applied together. | `User.apply_password_change()` |
| user provisioning | Creating an account with an initial password, role, and flags. Shared by registration, admin create, setup wizard, and seed. | `User` / seed |
| authorization policy | Named access decisions (`can_view_ticket`, `can_view_asset`, `require_admin`, `require_agent`). Per-surface intent is explicit: the portal is end-user-only. | `app/policy.py` |
| notification dispatch | Best-effort email send that must never fail the surrounding request: log and continue. | `email_utils.notify()` |
| bootstrap | Composition-root wiring (extensions, hooks, filters, error handlers) extracted so `create_app` reads as wiring. | `app/bootstrap/` |
| seed | The initial demo accounts and article corpus, shared by the setup wizard and `init_database` so the two paths cannot drift. | `app/seed.py` |

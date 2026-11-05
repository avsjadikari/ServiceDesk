# ServiceDesk API Documentation

Base URL (local): `http://127.0.0.1:5000/api`

Authentication: Session-based (Flask-Login). Most endpoints require login and role checks.

## Endpoints

### Users
- GET `/api/users` (login_required, agent/admin) — list users
  - Response: array of `{id, username, full_name, role, department}`

### Tickets
- GET `/api/tickets` (login_required, agent/admin) — list tickets
- GET `/api/tickets/<id>` (login_required) — get ticket
- POST `/api/tickets` (login_required) — create ticket (non-agent: owner set to self)
- PUT `/api/tickets/<id>` (login_required, agent/admin) — update ticket:
  - Request body (JSON): `{title, description, priority, category, status, assigned_to}`
  - Passing `assigned_to: null` cleanly unassigns the ticket, reverts `assigned` status back to `new`, and logs audit trail.
- DELETE `/api/tickets/<id>` (login_required, agent/admin) — delete ticket

### Workflow & Lifecycle Actions
- POST `/tickets/<id>/update-status` (login_required, agent/admin) — atomic status update endpoint for web & Kanban clients:
  - Request body (JSON or form): `{status, assigned_to, comment}`
  - Atomically applies status move, optional assignee update/unassignment, and transition comment within a single database transaction. Returns `{success: true, message: ...}`.

### Articles
- GET `/api/articles` (login_required) — list published articles (supports `?search=`, `?limit=`, `?offset=`)
- GET `/api/articles/<id>` (login_required) — get article details

### Assets
- GET `/api/assets` (login_required, agent/admin) — list assets (supports `?limit=`, `?offset=`)
- GET `/api/assets/<id>` (login_required) — get asset (owner or agent/admin)

### Analytics
- GET `/api/analytics/dashboard` (login_required, agent/admin) — metrics + SLA compliance

## Testing
1. Start server: `python run.py`
2. Login via browser or test client
3. Call endpoints with session cookies

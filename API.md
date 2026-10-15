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
- PUT `/api/tickets/<id>` (login_required, agent/admin) — update ticket
- DELETE `/api/tickets/<id>` (login_required, agent/admin) — delete ticket

### Articles
- GET `/api/articles` (login_required) — list articles
- GET `/api/articles/<id>` (login_required) — get article
- POST `/api/articles` (login_required, agent/admin) — create article
- PUT `/api/articles/<id>` (login_required, agent/admin) — update article
- DELETE `/api/articles/<id>` (login_required, agent/admin) — delete article

### Assets
- GET `/api/assets` (login_required, agent/admin) — list assets
- GET `/api/assets/<id>` (login_required) — get asset (owner or agent/admin)
- POST `/api/assets` (login_required, agent/admin) — create asset
- PUT `/api/assets/<id>` (login_required, agent/admin) — update asset
- DELETE `/api/assets/<id>` (login_required, agent/admin) — delete asset

### Analytics
- GET `/api/analytics/dashboard` (login_required, agent/admin) — metrics + SLA compliance

## Testing
1. Start server: `python run.py`
2. Login via browser or test client
3. Call endpoints with session cookies

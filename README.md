# ServiceDesk Application

Enterprise IT Service Management system built with Python Flask.

## Features

- **Ticket Management** – Create, assign, track, and resolve support tickets
- **Knowledge Base** – Self‑service articles with full‑text search
- **Asset Management** – Track IT assets and link them to tickets
- **Automation** – Auto‑assignment, SLA management, workflow rules
- **Analytics** – Dashboard with metrics, charts, and SLA compliance
- **Self‑Service Portal** – Customer‑facing ticket submission and tracking
- **Multi‑theme Support** – Blue, green, purple, red, light, and dark themes
- **Two‑Factor Authentication (2FA)** – TOTP‑based 2FA using authenticator apps
- **Rate Limiting** – Protection against brute‑force attacks
- **Email Notifications** – Automatic notifications for ticket events

## Tech Stack

- **Backend** – Python 3.10+, Flask 3.x
- **Database** – SQLite (development), PostgreSQL (production) via SQLAlchemy
- **Authentication** – Flask‑Login with role‑based access control
- **Frontend** – Bootstrap 5, Chart.js
- **Forms** – Flask‑WTF
- **Security** – Flask‑Limiter, PyOTP (2FA), Flask‑Mail

## Prerequisites

- Python 3.10 or higher
- PostgreSQL (for production use)
- `pip` (Python package installer)

## Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository‑url>
cd ServiceDesk
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
# or
venv\Scripts\activate      # Windows
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create an Environment File

Copy the example file and edit it. A `.env.example` template is shipped in the repository.

```bash
cp .env.example .env
$EDITOR .env
```

Generate a strong `SECRET_KEY` with:

```bash
python -c "import secrets; print(secrets.token_hex(64))"
```

**Important variables:**

| Var | Required? | Notes |
|---|---|---|
| `SECRET_KEY` | **yes** | App refuses to start without it |
| `DB_TYPE` | no (default `sqlite`) | `sqlite` or `postgresql` |
| `DB_PASSWORD` | **yes when `DB_TYPE=postgresql`** | App refuses to start without it |
| `FLASK_CONFIG` | no (default `development`) | `development`, `testing`, or `production` |
| `FLASK_DEBUG` | no (default `false`) | Must be `false` in production |
| `TALISMAN_FORCE_HTTPS` | no (default `true` in prod) | Disable only when TLS is terminated upstream |

### 5. Initialise / Migrate the Database

Schema is now managed with **Flask-Migrate** (Alembic). For an existing deployment that used `db.create_all()`, generate the baseline migration once:

```bash
export FLASK_APP=cli.py
flask db upgrade            # apply pending migrations
# or, for a brand-new database with no baseline:
flask db init               # one time only, to create migrations/
flask db migrate -m "init"  # generate the initial migration
flask db upgrade
```

The first-time setup wizard (`/setup`) is still available for an empty database; it now uses `db.create_all()` and refuses destructive schema operations in production.

### 6. Run the Development Server

```bash
python run.py
```

Open a browser at **http://localhost:5000**.

### 7. First‑Time Setup Wizard (optional)

If the database is empty, the application automatically redirects to the **Setup Wizard** (`/setup`). The wizard will:

1. Ask for the company name
2. Let you choose the database backend and connection details
3. Create an initial **admin** account (password you choose in the form – **must be changed on first login**)
4. Create default `agent` and `user` demo accounts with **random temporary passwords** logged to the application output – both are forced to change their password on first login
5. Seed sample knowledge‑base articles

> Retrieve the temporary demo passwords from the application logs (stdout / `docker compose logs web`) immediately after the wizard completes.

## Default Users (after first‑time setup)

| Username | Password source | Role | `must_change_password` |
|----------|----------------|------|------------------------|
| admin    | Chosen in wizard | Admin | true |
| agent    | Random – see logs | Agent | true |
| user     | Random – see logs | User  | true |

All three users are flagged with `must_change_password=True` and will be redirected to the *Change Password* page on first login.

## Running with Docker

A production-ready multi-container setup is provided via `docker-compose.yml`.

```bash
cp .env.example .env
# Edit .env: set SECRET_KEY and DB_PASSWORD
docker compose up -d --build
docker compose logs -f web     # watch startup / retrieve temp passwords
```

The stack brings up:

- `web` – gunicorn-served Flask app (multi-stage image, non-root user, healthcheck)
- `db`  – PostgreSQL 16 with persistent volume
- `redis` – for rate-limiting / future Celery workers
- `nginx` – optional TLS reverse-proxy (`--profile proxy`)

The container entrypoint automatically runs `flask db upgrade` before starting gunicorn, so schema migrations are applied on every deploy. To skip migrations on a single run, set `SKIP_MIGRATIONS=true`.

Run CLI commands inside the container with:

```bash
docker compose exec web flask db migrate -m "add new field"
docker compose exec web flask shell
```

## Password Policy

- Minimum **8** characters (recommended **12+** for production)
- At least **1** uppercase letter
- At least **1** lowercase letter
- At least **1** digit
- At least **1** special character (`@$!%*?&`)

The registration and change‑password forms enforce this policy via WTForms validators.

## Running the Test Suite

```bash
# Install test dependencies (already in requirements.txt)
pip install pytest pytest-cov pytest-flask

# Execute all tests
pytest

# Generate an HTML coverage report
pytest --cov=app --cov-report=html
```

Coverage reports are written to `htmlcov/`.

## Project Structure

```
ServiceDesk/
├── app/                     # Flask application package
│   ├── __init__.py          # App factory, DB init, blueprint registration
│   ├── models.py            # SQLAlchemy models (User, Ticket, Article, …)
│   ├── forms.py            # WTForms definitions
│   ├── utils.py            # Helper functions (ticket numbers, SLA, automation)
│   ├── routes/             # Blueprint modules (auth, tickets, knowledge, …)
│   │   ├── auth.py
│   │   ├── tickets.py
│   │   ├── knowledge.py
│   │   ├── assets.py
│   │   ├── analytics.py
│   │   ├── portal.py
│   │   ├── api.py
│   │   └── setup.py
│   └── templates/          # Jinja2 UI templates (grouped by feature)
├── tests/                  # Pytest suite
├── config.py                # Configuration classes (development / production)
├── run.py                   # Entry point (`python run.py`)
├── requirements.txt         # Python dependencies
├── SECURITY.md              # Security review & hardening checklist
└── SPEC.md                  # Full functional specification
```

## Security & Hardening (see `SECURITY.md` for full details)

- **CSRF protection** – Flask‑WTF adds tokens to every form.
- **Password hashing** – Werkzeug's `generate_password_hash` (PBKDF2‑SHA256).
- **Audit logging** – All user actions are stored in the `audit_logs` table.
- **Rate limiting** – Global limits (`200 per day, 50 per hour`) plus per‑endpoint limits (e.g., login limited to 5 req/min).
- **Two‑factor authentication** – TOTP support via PyOTP.
- **Session security** – Flask‑Login with server‑side session handling.

**Production hardening checklist** (summarised):

1. Generate a strong, unique `SECRET_KEY`.
2. Switch `FLASK_ENV` to `production` and set `FLASK_DEBUG=false`.
3. Serve the app behind a reverse proxy (NGINX/Traefik) with **HTTPS** termination.
4. Add security headers (CSP, HSTS, X‑Frame‑Options) – e.g., using `flask‑talisman`.
5. Enable account lockout after repeated failed logins (custom middleware or extend the limiter).
6. Configure a real email backend for notifications.
7. Set up log aggregation and a database backup strategy.
8. Consider LDAP/AD integration or SSO for enterprise authentication.
9. Remove the hard‑coded default passwords from the setup wizard or force password change before the wizard completes.

## Missing / Incomplete Scripts & Code Issues

| File / Feature | Issue | Suggested Fix |
|---------------|-------|--------------|
| `app/routes/setup.py` | Uses `generate_password_hash` incorrectly (assigns to `password_hash` directly) and hard‑codes default passwords (`admin123`, `agent123`, `user123`). | Use the `User.set_password()` method and generate random passwords, then force a password reset via email or UI. |
| `.env.example` | Not shipped; users must create `.env` manually. | Add a minimal `.env.example` to the repo (see the example above). |
| Database migrations | No migration tool (e.g., Flask‑Migrate) included. | Add Flask‑Migrate to manage schema changes in production. |
| `SECURITY.md` notes hard‑coded `SECRET_KEY` in `config.py` – the code raises an error if `SECRET_KEY` is missing, but the repository does not provide a way to generate one automatically. | Provide a CLI helper (`hermes config set SECRET_KEY <value>`) or documentation on generating the key. |
| Rate limiting on many routes | Only the login route is explicitly limited; other potentially sensitive endpoints (password reset, 2FA, API) lack limits. | Add `@limiter.limit` decorators to those routes. |
| Missing input sanitisation for rendered user content | Templates directly output user‑provided text (e.g., ticket descriptions). | Implement a sanitisation helper (e.g., `bleach`) in `utils.py` and use it before storing/displaying markdown. |
| No CSRF token on API endpoints | The REST API (`/api/*`) does not enforce CSRF protection. | Either disable CSRF for API (with proper token auth) or switch to token‑based authentication (JWT). |
| No automated test for the setup wizard | The test suite covers auth, tickets, assets, knowledge but not the first‑time setup flow. | Add a `tests/test_setup.py` that verifies the wizard creates the admin user and writes `.env`. |
| Hard‑coded password reset token length/pattern | In `email_utils.send_password_reset` the token is generated elsewhere (not shown). Ensure token length meets security policy. |

Addressing the items above will improve reliability, security, and developer experience.

## Recommendations & Next Steps

1. **Add `.env.example`** – commit the example file so new developers have a clear starting point.
2. **Refactor the setup wizard** to:
   - Generate random passwords (or ask the installer to provide them).
   - Use `User.set_password()` instead of directly assigning `password_hash`.
   - Ensure `must_change_password` is set so admins must change their passwords immediately.
3. **Integrate Flask‑Migrate** for schema versioning.
4. **Hardening** – add Flask‑Talisman, enable HSTS, CSP, and secure cookie flags.
5. **Rate‑limit** all authentication‑related endpoints (login, 2FA, password reset, API token endpoints).
6. **Sanitise** any user‑generated markdown before rendering (use `bleach` or a safe markdown renderer).
7. **Extend tests** to cover the setup wizard and any newly added security measures.
8. **Documentation** – update the README (this file) and `SECURITY.md` with the above changes.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b my‑feature`)
3. Write tests for your changes (`tests/`)
4. Ensure the entire test suite passes (`pytest`)
5. Submit a Pull Request with a concise description and reference any open issue.

## License

MIT License – see the `LICENSE` file.

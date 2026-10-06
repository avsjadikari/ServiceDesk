# ServiceDesk Application

Enterprise IT Service Management system built with Python Flask.

## Features:

- **Ticket Management**: Create, assign, track, and resolve support tickets with SLA deadlines
- **Kanban Workflow Board**: Interactive HTML5 drag-and-drop workflow board (`/tickets/board`) with instant status transitions
- **Operational Dashboard**: Real-time metrics, 14-day activity trend chart, SLA breach alert banner, and agent performance tracking
- **Interactive Analytics**: Deep analytics dashboard with 7/30/90-day timeframes, MTTR calculation, category breakdown, and one-click CSV export
- **Multi-Language (i18n)**: Zero-dependency JSON catalog localization supporting 7 languages: English (`en`), Spanish (`es`), French (`fr`), German (`de`), Japanese (`ja`), Arabic (`ar` with RTL layout), and Sinhala (`si`)
- **Self‑Service Customer Portal**: Modern customer portal with search hero, service category cards, knowledge base spotlight, and 5-stage ticket lifecycle stepper
- **Knowledge Base**: Self‑service articles with full‑text search and category filtering
- **Asset Management**: Track IT assets, warranty details, and link assets directly to tickets
- **Automation**: Auto‑assignment, SLA monitoring, and status-based workflow triggers
- **Multi‑theme Support**: Blue, green, purple, red, light, and dark themes
- **Two‑Factor Authentication (2FA)**: TOTP‑based 2FA using authenticator apps
- **Rate Limiting and Security**: Brute‑force protection via Flask-Limiter, account lockout, Talisman security headers, and Bleach XSS sanitization
- **Email Notifications**: Automatic notifications for ticket events and password resets

## Tech stack:

- **Backend**: Python 3.10+, Flask 3.x
- **Database**: SQLite (development), PostgreSQL (production) via SQLAlchemy & Flask-Migrate
- **Authentication**: Flask‑Login with role‑based access control and account lockout
- **Frontend**: Bootstrap 5, Chart.js, HTML5 Drag-and-Drop, DataTables, RTL CSS
- **Forms**: Flask‑WTF with CSRF protection
- **Internationalization**: Lightweight zero-dependency JSON catalogs (`app/i18n.py`)
- **Security**: Flask‑Limiter, Flask-Talisman, Bleach, PyOTP (2FA), itsdangerous, Flask‑Mail


## Prerequisites

- Python 3.10 or higher
- PostgreSQL (for production use)
- `pip` (Python package installer)

## Installation and setup

### 1. Clone the repository

```bash
git clone <repository‑url>
cd ServiceDesk
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
# or
venv\Scripts\activate      # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create an environment file

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

### 5. Initialise or migrate the database

Schema is now managed with **Flask-Migrate** (Alembic). For an existing deployment that used `db.create_all()`, generate the baseline migration once:

```bash
export FLASK_APP=cli.py
flask db upgrade            # apply pending migrations
# or, for a brand-new database with no baseline:
flask db init               # one time only, to create migrations/
flask db migrate -m "init"  # generate the initial migration
flask db upgrade
```

If the app was previously run with an existing local database (created by the setup wizard via `db.create_all()`) before migrations were introduced, Alembic has no version row yet, so `flask db upgrade` fails. Mark the current schema as the baseline once:

```bash
flask db stamp head
```

After that, subsequent `flask db upgrade` calls apply only the migrations built on top of that baseline.

The first-time setup wizard (`/setup`) is still available for an empty database; it now uses `db.create_all()` and refuses destructive schema operations in production.

### 6. Run the development server

```bash
python run.py
```

Open a browser at **http://localhost:5000**.

### 7. First-time setup wizard (optional)

If the database is empty, the application automatically redirects to the **Setup Wizard** (`/setup`). The wizard will:

1. Ask for the company name
2. Let you choose the database backend and connection details
3. Create an initial **admin** account (password you choose in the form; it **must be changed on first login**)
4. Create default `agent` and `user` demo accounts with **random temporary passwords** logged to the application output – both are forced to change their password on first login
5. Seed sample knowledge‑base articles

> Retrieve the temporary demo passwords from the application logs (stdout / `docker compose logs web`) immediately after the wizard completes.

## Default users (after first‑time setup)

| Username | Password source | Role | `must_change_password` |
|----------|----------------|------|------------------------|
| admin    | Chosen in wizard | Admin | true |
| agent    | Random (see logs) | Agent | true |
| user     | Random (see logs) | User  | true |

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

- `web`: gunicorn-served Flask app (multi-stage image, non-root user, healthcheck)
- `db`: PostgreSQL 16 with persistent volume
- `redis`: for rate-limiting / future Celery workers
- `nginx`: optional TLS reverse-proxy (`--profile proxy`)

The container entrypoint automatically runs `flask db upgrade` before starting gunicorn, so schema migrations are applied on every deploy. To skip migrations on a single run, set `SKIP_MIGRATIONS=true`.

Run CLI commands inside the container with:

```bash
docker compose exec web flask db migrate -m "add new field"
docker compose exec web flask shell
```

## Password policy:

- Minimum **8** characters (recommended **12+** for production)
- At least **1** uppercase letter
- At least **1** lowercase letter
- At least **1** digit
- At least **1** special character (`@$!%*?&`)

The registration and change‑password forms enforce this policy via WTForms validators.

## Running the test suite

```bash
# Install test dependencies (already in requirements.txt)
pip install pytest pytest-cov pytest-flask

# Execute all tests
pytest

# Generate an HTML coverage report
pytest --cov=app --cov-report=html
```

Coverage reports are written to `htmlcov/`.

## Project structure

```
ServiceDesk/
├── app/                     # Flask application package
│   ├── __init__.py          # App factory, DB init, blueprint registration
│   ├── models.py            # SQLAlchemy models (User, Ticket, Article, …)
│   ├── forms.py             # WTForms definitions
│   ├── utils.py             # Helper functions (ticket numbers, SLA, automation)
│   ├── i18n.py              # Zero-dependency JSON i18n engine & context processor
│   ├── sanitize.py          # Bleach HTML/markdown sanitization
│   ├── security.py          # Token serialization & password reset security
│   ├── email_utils.py       # Notification mailers
│   ├── translations/        # Lightweight JSON localization catalogs
│   │   ├── en.json          # English (default)
│   │   ├── es.json          # Spanish
│   │   ├── fr.json          # French
│   │   ├── de.json          # German
│   │   ├── ja.json          # Japanese
│   │   ├── ar.json          # Arabic (RTL)
│   │   └── si.json          # Sinhala
│   ├── routes/              # Blueprint modules
│   │   ├── auth.py          # Authentication, 2FA, password reset
│   │   ├── main.py          # Operational dashboard, /set-lang
│   │   ├── tickets.py       # Ticket CRUD, Kanban board (/tickets/board)
│   │   ├── knowledge.py     # Knowledge base articles
│   │   ├── assets.py        # IT asset management
│   │   ├── analytics.py     # Interactive analytics, timeframes, CSV export
│   │   ├── portal.py        # Customer self-service portal
│   │   ├── api.py           # REST API endpoints
│   │   └── setup.py         # First-time setup wizard
│   └── templates/           # Jinja2 UI templates (grouped by feature)
├── tests/                   # Pytest suite (96 tests covering all features)
├── config.py                # Configuration classes (development / production)
├── run.py                   # Entry point (`python run.py`)
├── requirements.txt         # Python dependencies
├── SECURITY.md              # Security review & hardening checklist
└── SPEC.md                  # Full functional specification
```

## Security and hardening

- **CSRF protection**: Flask‑WTF adds tokens to every form and AJAX request.
- **Password hashing**: Werkzeug's `generate_password_hash` (PBKDF2‑SHA256).
- **Audit logging**: All user actions are stored in the `audit_logs` table.
- **Rate limiting**: Global limits (`200 per day, 50 per hour`) plus per‑endpoint limits (e.g., login limited to 5 req/min).
- **Two‑factor authentication**: TOTP support via PyOTP.
- **Session security**: Flask‑Login with server‑side session handling and fixation protection.
- **Safe Redirection**: Language switcher verifies referrer host against `request.host_url` preventing open redirects.
- **XSS Sanitization**: Markdown content safely sanitized with Bleach (`| markdown_safe`).

**Production hardening checklist** (summarised):

1. Generate a strong, unique `SECRET_KEY`.
2. Switch `FLASK_ENV` to `production` and set `FLASK_DEBUG=false`.
3. Serve the app behind a reverse proxy (NGINX/Traefik) with **HTTPS** termination.
4. Add security headers (CSP, HSTS, X‑Frame‑Options) – e.g., using `flask‑talisman`.
5. Enable account lockout after repeated failed logins (enforced in `auth.login`).
6. Configure a real email backend for notifications.
7. Set up log aggregation and a database backup strategy.
8. Consider LDAP/AD integration or SSO for enterprise authentication.

## Completed modernization and hardening

| Component / Feature | State | Implementation Details |
|---------------------|-------|------------------------|
| Multi-Language (i18n) | **Implemented** | Lightweight zero-dependency JSON catalogs (`app/i18n.py`) supporting English, Spanish, French, German, Japanese, Arabic (with RTL), and Sinhala. Instant language switching at `/set-lang/<code>` with open redirect validation. |
| Kanban Workflow Board | **Implemented** | Interactive HTML5 drag-and-drop board at `/tickets/board` with 5 workflow columns and optimistic status sync. |
| Operational Dashboard | **Implemented** | 14-day activity trend chart, real-time SLA breach alert banner, and agent performance tracking metrics. |
| Interactive Analytics Suite | **Implemented** | Deep analytics at `/analytics` with 7/30/90-day timeframes, MTTR metrics, category distribution, and one-click CSV export. |
| Customer Support Portal | **Implemented** | Search hero, service categories, knowledge spotlight, and 5-stage ticket lifecycle stepper. |
| Setup Wizard Security | **Implemented** | Generates secure random temporary passwords via `secrets`, uses `User.set_password()`, enforces `must_change_password`. |
| Database Migrations | **Implemented** | Flask-Migrate (Alembic) configured for schema versioning. |
| Environment Config | **Implemented** | `.env.example` shipped in repository; requires explicit `SECRET_KEY`. |
| Input Sanitization | **Implemented** | `app/sanitize.py` renders markdown safely with Bleach (`| markdown_safe`). |
| Automated Test Suite | **Implemented** | 96 unit and integration tests across auth, tickets, assets, knowledge, setup, analytics, and i18n (`pytest`). |



## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b my‑feature`)
3. Write tests for your changes (`tests/`)
4. Ensure the entire test suite passes (`pytest`)
5. Submit a Pull Request with a concise description and reference any open issue.

## License

MIT License. See the `LICENSE` file.

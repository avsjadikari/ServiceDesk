# ServiceDesk Application

Enterprise IT Service Management (ITSM) system built with Python Flask.

## Features

- **Ticket Management**: Create, assign, track, and resolve support tickets with full SLA management
- **Knowledge Base**: Self-service articles with full-text search and versioning
- **Asset Management**: Track IT assets (hardware/software/network) and link to tickets
- **Automation**: Auto-assignment, SLA management, workflow rules engine
- **Analytics**: Dashboard with metrics, charts, and SLA compliance reporting
- **Self-Service Portal**: Customer-facing ticket submission and real-time tracking
- **Multi-Theme Support**: Blue, green, purple, red, light, and dark themes
- **Two-Factor Authentication (2FA)**: TOTP-based 2FA via authenticator apps (Google Authenticator, Authy)
- **Rate Limiting**: Brute-force protection (5 login attempts/min, 200 req/day)
- **Email Notifications**: Ticket creation, assignment, status changes, and security events
- **Audit Logging**: Comprehensive per-action audit trail stored in database
- **Health Monitoring**: `/health` endpoint for load balancer and uptime checks
- **CSRF Protection**: All forms protected with Flask-WTF CSRF tokens
- **Security Headers**: TLS enforcement, HSTS, X-Frame-Options, referrer policy (production)
- **Session Fixation Protection**: Session is regenerated on login

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, Flask 3.x |
| **Database** | SQLite (dev), PostgreSQL 14+ (prod) |
| **ORM** | SQLAlchemy 2.x |
| **Authentication** | Flask-Login |
| **Frontend** | Bootstrap 5, Chart.js |
| **Forms & Validation** | Flask-WTF, WTForms |
| **Security** | Flask-Talisman, Flask-Limiter, PyOTP |
| **Email** | Flask-Mail |
| **Production Server** | Gunicorn |

## Prerequisites

- **Python** 3.10 or higher
- **pip** 22+
- **PostgreSQL** 14+ (for production deployments)
- An SMTP server (optional — for email notifications)

---

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ServiceDesk
```

### 2. Create a Virtual Environment

```bash
# Linux / macOS
python -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example env file and edit it:

```bash
cp .env.example .env
```

**Required variables:**

```env
# Generate with: python -c "import secrets; print(secrets.token_hex(64))"
SECRET_KEY=your-64-char-hex-secret-key

COMPANY_NAME=YourCompany
FLASK_CONFIG=development
```

**Database (SQLite for dev, PostgreSQL for prod):**

```env
# SQLite (default — no extra config needed)
DB_TYPE=sqlite

# PostgreSQL
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=servicedesk
DB_USER=servicedesk_user
DB_PASSWORD=strong-password-here
DB_SSL_MODE=require          # require in production, prefer in dev
```

**Email / SMTP (optional):**

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password   # Gmail App Password (not account password)
MAIL_DEFAULT_SENDER=noreply@yourcompany.com
```

### 5. Initialize the Database

```bash
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

### 6. Run the Application

**Development:**

```bash
python run.py
```

**Production (Gunicorn):**

```bash
gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app('production')"
```

Open your browser to `http://localhost:5000` (dev) or `http://your-server:8000` (prod).

---

## First-Time Setup Wizard

1. Navigate to `http://localhost:5000/setup`
2. Enter your **Company Name**
3. Configure **Database** settings
4. Create the **Admin Account**
5. Complete setup — you will be redirected to the login page

---

## Default Users

After setup completes, three demo users are created. **Passwords must be changed on first login.**

| Username | Default Password | Role | Access |
|----------|-----------------|------|--------|
| `admin` | `Admin@123456` | Admin | Full access + user management |
| `agent` | `Agent@123456` | Agent | Ticket management, knowledge base, assets |
| `user` | `User@123456` | User | Self-service portal only |

> ⚠️ **Change these passwords immediately** in production.

---

## Password Requirements

All passwords must satisfy:

- Minimum **8 characters**
- At least **1 uppercase** letter (A–Z)
- At least **1 lowercase** letter (a–z)
- At least **1 number** (0–9)
- At least **1 special character** (`@$!%*?&`)

---

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=html

# View HTML coverage report
# Open htmlcov/index.html in your browser
```

### Test Configuration

Tests use an **in-memory SQLite database** and have CSRF disabled automatically via the `testing` config. No `.env` changes are required to run tests — the `conftest.py` sets all required environment variables.

```bash
# Run a specific test module
pytest tests/test_auth.py -v

# Run a specific test class
pytest tests/test_tickets.py::TestTicketCreation -v
```

---

## Project Structure

```
ServiceDesk/
├── app/
│   ├── __init__.py          # Application factory, AnonymousUser, health endpoint
│   ├── models.py            # SQLAlchemy database models
│   ├── forms.py             # WTForms form classes (with validation)
│   ├── utils.py             # Utility functions (SLA, ticket numbers, audit)
│   ├── email_utils.py       # Email notification functions
│   ├── backup.py            # Database backup/restore utilities
│   └── routes/
│       ├── auth.py          # Login, logout, registration, 2FA, profile
│       ├── main.py          # Agent dashboard
│       ├── tickets.py       # Ticket CRUD and workflow
│       ├── knowledge.py     # Knowledge base articles
│       ├── assets.py        # IT asset management
│       ├── analytics.py     # Reporting and metrics
│       ├── portal.py        # Self-service portal (end-users)
│       ├── api.py           # REST API endpoints
│       ├── settings.py      # Admin settings panel
│       └── setup.py         # First-time setup wizard
├── tests/
│   ├── conftest.py          # Pytest fixtures and test app configuration
│   ├── test_auth.py         # Authentication and authorization tests
│   ├── test_tickets.py      # Ticket management tests
│   ├── test_knowledge.py    # Knowledge base tests
│   └── test_assets.py       # Asset management tests
├── config.py                # DevelopmentConfig, ProductionConfig, TestingConfig
├── run.py                   # Application entry point
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (do NOT commit)
├── .env.example             # Example env file (safe to commit)
├── .gitignore               # Git ignore rules
├── SECURITY.md              # Security policy and assessment
└── SPEC.md                  # Application specification
```

---

## API Endpoints

All API endpoints are prefixed with `/api`.

### Authentication

| Method | Endpoint | Auth Required | Description |
|--------|----------|--------------|-------------|
| `GET`  | `/api/users` | Agent | List all users |

### Tickets

| Method | Endpoint | Auth Required | Description |
|--------|----------|--------------|-------------|
| `GET`  | `/api/tickets` | Agent | List all tickets |
| `POST` | `/api/tickets` | User | Create ticket |
| `GET`  | `/api/tickets/<id>` | User (own) / Agent (all) | Get ticket |
| `PUT`  | `/api/tickets/<id>` | Agent | Update ticket |
| `DELETE` | `/api/tickets/<id>` | Agent | Delete ticket |

### Knowledge Base

| Method | Endpoint | Auth Required | Description |
|--------|----------|--------------|-------------|
| `GET`  | `/api/articles` | None | List published articles |
| `GET`  | `/api/articles/<id>` | None | Get article |
| `GET`  | `/api/articles?search=<q>` | None | Search articles |

### Assets

| Method | Endpoint | Auth Required | Description |
|--------|----------|--------------|-------------|
| `GET`  | `/api/assets` | Agent | List all assets |
| `GET`  | `/api/assets/<id>` | User (own) / Agent (all) | Get asset |

### Analytics

| Method | Endpoint | Auth Required | Description |
|--------|----------|--------------|-------------|
| `GET`  | `/api/analytics/dashboard` | Agent | Dashboard metrics + SLA |

### Health

| Method | Endpoint | Auth Required | Description |
|--------|----------|--------------|-------------|
| `GET`  | `/health` | None | Application health check |

---

## Enterprise Features

### Implemented ✅

| Feature | Details |
|---------|---------|
| Role-Based Access Control | Admin / Agent / User with granular permissions |
| SLA Management | Configurable response + resolution times per priority |
| Audit Logging | All user actions logged with IP address to database |
| Two-Factor Authentication | TOTP via Google Authenticator / Authy |
| Session Fixation Protection | Session regenerated on every login |
| Open Redirect Protection | `next` URL validated as relative path only |
| Password Strength Enforcement | Regex-validated complexity requirements |
| Rate Limiting | Per-endpoint and global limits via Flask-Limiter |
| CSRF Protection | Flask-WTF tokens on all state-changing forms |
| Security Headers | HSTS, X-Frame-Options, referrer policy (production) |
| Profile Form Validation | WTForms validates all profile update inputs |
| Health Endpoint | `/health` returns DB status + version (no auth) |
| Multi-Theme Support | 6 themes; stored per user preference |
| Database Backup | CLI backup/restore utility |
| Email Notifications | Ticket events, 2FA events, security alerts |

### Recommended for Production 🔧

| Priority | Feature | Notes |
|----------|---------|-------|
| **HIGH** | LDAP/Active Directory Integration | Sync users from corporate directory |
| **HIGH** | Account Lockout | Lock account after N failed login attempts |
| **HIGH** | Password Reset Flow | Email-based self-service password reset |
| **HIGH** | API Key Authentication | Machine-to-machine API access without session |
| **MEDIUM** | SSO / SAML 2.0 | Single sign-on (Okta, Azure AD, etc.) |
| **MEDIUM** | Slack/Teams Webhooks | Real-time channel notifications |
| **MEDIUM** | OpenAPI / Swagger Docs | Auto-generated API documentation |
| **MEDIUM** | S3 / Cloud File Storage | Attachment storage outside local disk |
| **MEDIUM** | Prometheus Metrics | Export metrics for Grafana dashboards |
| **LOW** | Elasticsearch Integration | Full-text search at scale |
| **LOW** | GDPR Data Export | Right-to-access and right-to-deletion |

---

## Security

See [SECURITY.md](SECURITY.md) for the full security assessment and production checklist.

---

## Troubleshooting

### `SECRET_KEY environment variable is required`

Ensure `.env` is properly configured with a `SECRET_KEY` value:

```bash
python -c "import secrets; print(secrets.token_hex(64))"
```

Copy the output into your `.env` file.

### Database Connection Issues (PostgreSQL)

1. Verify PostgreSQL is running: `pg_isready`
2. Create the database: `createdb servicedesk`
3. Verify credentials in `.env`
4. Check `DB_SSL_MODE` — use `prefer` for local dev, `require` for production

### Import / Dependency Errors

```bash
pip install -r requirements.txt
```

### Rate Limit Warnings in Tests

The `TestingConfig` automatically sets `RATELIMIT_ENABLED = False`. These warnings only appear in development mode.

### `can't compare offset-naive and offset-aware datetimes`

This is resolved — the `is_sla_breached` property now correctly handles both SQLite (naive) and PostgreSQL (aware) datetime storage.

---

## License

MIT License

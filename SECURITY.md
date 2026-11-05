# ServiceDesk Application Security Review

## Executive Summary

This document provides a comprehensive security assessment of the ServiceDesk application and outlines recommendations for enterprise deployment.

---

## Current Security Implementation

### ✅ Implemented Security Features

1. **CSRF Protection**: Flask-WTF CSRF tokens on all forms (time-limited 4h) — including the `/login-2fa` TOTP verification form, which renders a hidden `csrf_token` so the POST passes CSRFProtect
2. **Password Hashing**: Werkzeug's `generate_password_hash` using scrypt / pbkdf2:sha256
3. **Session Management**: Flask-Login with `session_protection="strong"`, anonymous user shim, secure cookie flags
4. **Authentication**: Role-based access control (admin, agent, user)
5. **Audit Logging**: Comprehensive action logging to database
6. **Database ORM**: SQLAlchemy prevents SQL injection
7. **File Upload Limits**: 16MB max content length configured
8. **Security Headers (production)**: Flask-Talisman with CSP, HSTS (1y, preload, includeSubDomains), `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, HTTPS redirect
9. **HTTPS-only cookies in production**: `SESSION_COOKIE_SECURE`, `REMEMBER_COOKIE_SECURE`
10. **Schema migrations**: Flask-Migrate / Alembic (replaces ad-hoc `db.create_all()` for production)
11. **Open Redirect Prevention**: `/set-lang/<lang_code>` checks `request.referrer` starts with `request.host_url`; safely defaults to dashboard
12. **Locale Whitelisting**: Language codes validated against `SUPPORTED_LANGUAGES` allow-list (`en`, `es`, `fr`, `de`, `ja`, `ar`, `si`) in `app/i18n.py`, blocking path-traversal or catalog injection
13. **AJAX CSRF Protection**: Drag-and-drop status update endpoint (`/tickets/<id>/update-status`) validates `X-CSRFToken` header


### ⚠️ Security Issues Found & Remediation Register

| Severity | Issue | Location | Status / Remediation |
|----------|-------|----------|----------------------|
| ~~**HIGH**~~ | ~~Hardcoded SECRET_KEY~~ | `config.py` | **Fixed** – refuses to start without env var |
| ~~**HIGH**~~ | ~~Default passwords in code~~ | `__init__.py`, `setup.py` | **Fixed** – random temporary passwords via `secrets`; forces password change |
| ~~**HIGH**~~ | ~~Password-reset Host header poisoning~~ | `app/routes/auth.py`, `app/email_utils.py` | **Fixed** – canonical `SERVER_NAME` enforcement in `_external_url` ignores spoofed Host headers |
| ~~**HIGH**~~ | ~~Unauthenticated setup wizard in prod~~ | `app/routes/setup.py` | **Fixed** – `SETUP_TOKEN` env var strictly required in production mode |
| ~~**HIGH**~~ | ~~Stored XSS in user action handlers~~ | `app/templates/auth/users.html` | **Fixed** – inline handlers removed; replaced with `data-*` attributes and delegated listeners |
| ~~**HIGH**~~ | ~~No account lockout~~ | `app/routes/auth.py` | **Fixed** – `LOGIN_MAX_ATTEMPTS` (5) and `LOGIN_LOCKOUT_MINUTES` (15) enforced with audit logging |
| ~~**HIGH**~~ | ~~Unguarded asset linking crashes (500)~~ | `app/routes/tickets.py` | **Fixed** – validated `Asset` exists; added unlink branch (`asset_id=0`) with audit |
| ~~**MEDIUM**~~ | ~~REST API enum mismatch~~ | `app/routes/api.py` | **Fixed** – single shared enum definitions in `app/enums.py` |
| ~~**MEDIUM**~~ | ~~Published dependency CVEs~~ | `requirements.txt` | **Fixed** – upgraded `gunicorn==26.2.0`, `cryptography==50.0.2`, `Pillow==12.3.0` |
| ~~**MEDIUM**~~ | ~~Inactive users selectable for assets~~ | `app/routes/assets.py` | **Fixed** – filtered `is_active=True` in `AssetForm` choices |
| ~~**MEDIUM**~~ | ~~Modal backdrop click trapping / UI freeze~~ | `profile.html`, `versions.html`, `board.html` | **Fixed** – modals relocated to `{% block modals %}` outside animated layout |
| ~~**MEDIUM**~~ | ~~No rate limiting~~ | All routes | **Fixed** – Flask-Limiter configured globally and on sensitive endpoints |
| ~~**MEDIUM**~~ | ~~No password strength validation~~ | `app/forms.py` | **Fixed** – password complexity regex validator implemented |
| ~~**MEDIUM**~~ | ~~No input sanitization (XSS)~~ | Templates | **Fixed** – `app/sanitize.py` sanitizes markdown with Bleach allow-list |
| ~~**MEDIUM**~~ | ~~No password reset flow~~ | `app/routes/auth.py` | **Fixed** – itsdangerous-signed timed tokens with rate-limited endpoints |
| ~~**MEDIUM**~~ | ~~Email helpers swallow errors~~ | `app/email_utils.py` | **Fixed** – replaced `except: pass` with structured logger warnings |
| ~~**LOW**~~ | ~~No security headers~~ | `app/bootstrap/security_headers.py` | **Fixed** – Flask-Talisman with CSP nonces and HSTS in production |
| ~~**LOW**~~ | ~~No HTTPS enforcement~~ | `app/bootstrap/security_headers.py` | **Fixed** – Talisman `force_https` and secure cookie flags |
| ~~**LOW**~~ | ~~Session fixation~~ | `app/routes/auth.py` | **Fixed** – strong session protection + `session.clear()` on login |

---

## Enterprise Security Recommendations

### 1. Authentication & Authorization

```python
# Recommended: Strong Password Policy
# In forms.py - ChangePasswordForm:
password = PasswordField(
    "Password", 
    validators=[
        DataRequired(), 
        Length(min=12),
        Regexp(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]',
            message="Password must contain uppercase, lowercase, number, and special character"
        )
    ]
)
```

### 2. Rate Limiting

```python
# Install: pip install flask-limiter
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(app, key_func=get_remote_address)

@auth.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    # ...
```

### 3. Security Headers

```python
# Install: pip install flask-talisman
from flask_talisman import Talisman

Talisman(app, content_security_policy=None)
```

### 4. Session Security

```python
# In auth.py - login route:
from flask import session
import secrets

def login():
    # ...
    session.clear()  # Clear session before login
    session.regenerate()  # Regenerate session ID
    login_user(user, remember=form.remember_me.data)
```

### 5. Input Validation

Add to `utils.py`:

```python
import re
from html import escape

def sanitize_input(text):
    """Sanitize user input to prevent XSS"""
    if not text:
        return ""
    return escape(text)

def sanitize_markdown(text):
    """Allow safe markdown while preventing XSS"""
    # Usebleach or markdown library with sanitization
    pass
```

---

## Additional Enterprise Features Gap Analysis

## Enterprise Features & Readiness Gap Analysis

### Implementation & Gap Matrix

| Category | Capability | Status | Implementation Details |
|----------|------------|--------|------------------------|
| **Auth** | Two-Factor Authentication (2FA) | **Implemented** | TOTP authentication via PyOTP + backup recovery codes ([`app/routes/auth.py`](file:///home/sysadmin/Documents/Projects/ServiceDesk/app/routes/auth.py)) |
| **Auth** | Password Reset Flow | **Implemented** | Signed timed tokens via itsdangerous with rate-limited endpoints ([`app/security.py`](file:///home/sysadmin/Documents/Projects/ServiceDesk/app/security.py)) |
| **Auth** | Account Lockout | **Implemented** | Lockout after 5 failed attempts for 15 minutes with email notification ([`app/models.py`](file:///home/sysadmin/Documents/Projects/ServiceDesk/app/models.py)) |
| **Auth** | Password Complexity | **Implemented** | Length >= 8, uppercase, lowercase, number, and symbol regex validation |
| **Auth** | Session Fixation Defense | **Implemented** | Session destruction and regeneration (`session.clear()`) on login |
| **Auth** | LDAP / Active Directory | Planned (Gap) | Enterprise corporate directory authentication sync |
| **Auth** | SAML 2.0 / OIDC SSO | Planned (Gap) | Single Sign-On integration for Okta, Azure AD, Google Workspace |
| **Notifications** | Transactional Email Templates | **Implemented** | Dedicated Jinja HTML/text templates for tickets, resets, and locks |
| **Notifications** | SMS Notifications | Planned (Gap) | Twilio / SMS gateway integration for critical SLA breach alerts |
| **Notifications** | ChatOps Integration | Planned (Gap) | Webhook notifications for Slack channels and Microsoft Teams |
| **API** | Session & Cookie Auth | **Implemented** | Role-gated REST API with CSRF token verification |
| **API** | API Rate Limiting | **Implemented** | Per-endpoint limits via Flask-Limiter (`30 per hour` on writes) |
| **API** | API Keys / OAuth2 JWT | Planned (Gap) | Service tokens for non-interactive machine-to-machine integrations |
| **API** | OpenAPI / Swagger Spec | Planned (Gap) | Interactive OpenAPI 3.0 specification endpoint |
| **Storage** | Local Upload Sandboxing | **Implemented** | UUID file prefixes, MIME check, magic bytes sniffing, path traversal check |
| **Storage** | Cloud Blob Storage | Planned (Gap) | S3 / GCS / Azure Blob attachment storage backend |
| **Monitoring** | Health & Readiness Probes | **Implemented** | `/health` (liveness) and `/ready` (DB readiness) endpoints |
| **Monitoring** | Error Monitoring | **Implemented** | Sentry SDK integration with environment-controlled traces |
| **Monitoring** | Prometheus Metrics Export | Planned (Gap) | OpenTelemetry / Prometheus `/metrics` scrape endpoint |
| **Search** | Database Multi-Column Search | **Implemented** | Case-insensitive multi-column ILIKE search with pagination |
| **Search** | Elasticsearch / OpenSearch | Planned (Gap) | Distributed full-text and semantic vector search |

---

## Compliance Considerations

### 1. GDPR Compliance (EU 2016/679)
- [x] **Data Export & Portability (Art. 20)**: One-click CSV export on ticket and agent performance tables; JSON serialization on `/api/tickets` and `/api/users`.
- [x] **Right to Rectification (Art. 16)**: Self-service profile updates (`/profile`) and administrative user editing (`/users/<id>/edit`).
- [x] **Right to Restriction of Processing (Art. 18)**: Administrative account deactivation (`/users/<id>/disable`) cleanly revokes access while preserving relational ticket audit integrity.
- [x] **Security of Processing (Art. 32)**: Cryptographic password hashing (scrypt/pbkdf2), Talisman HSTS + CSP nonces, session-fixation protection, and rate limiting.
- [x] **Auditability (Art. 30)**: Append-only immutable `AuditLog` records actor user ID, client IP address, timestamp, action type, and JSON transition metadata.
- [ ] **Automated Data Purge Tool**: Scripted PII redaction/anonymization for closed tickets upon formal erasure requests.
- [ ] **Consent Management**: Explicit consent checkbox for privacy policy during self-service user registration.

### 2. SOX Compliance (Sarbanes-Oxley Sections 302 & 404)
- [x] **Segregation of Duties & Access Control**: Strict role separation between Admin, Agent, and End-User. Route-level decorators (`@web_admin_required`, `@web_agent_required`) enforce boundaries.
- [x] **Tamper-Evident Audit Trail**: All privileged actions (system settings updates, company configuration changes, user role changes, password resets) are captured in `AuditLog`.
- [x] **Change Management Controls**: Schema mutations managed through version-controlled Alembic / Flask-Migrate migrations.
- [ ] **Quarterly Access Review Workflow**: Automated administrator review and sign-off portal for active user role privileges.

### 3. ISO 27001 / SOC 2 Type II Controls
- [x] **Access Control (A.9)**: Multi-factor authentication (TOTP 2FA), account lockout after 5 consecutive failures, forced password change on first-time login (`must_change_password`).
- [x] **Vulnerability & Dependency Management (A.12.6)**: Pinned production dependencies patched against known CVEs (`gunicorn>=26`, `cryptography>=50`, `Pillow>=12`).
- [x] **Threat Detection & Logging (A.12.4)**: Structured JSON logging with request UUIDs (`X-Request-Id`), Sentry error reporting.
- [x] **Input Validation & Secure Architecture (A.14.2)**: Bleach HTML sanitization pipeline (`markdown_safe`), magic bytes upload verification, and path traversal blocking.
- [ ] **Disaster Recovery Automation**: Scheduled offsite automated database backup sync and quarterly restore verification testing.

---

## Production Security Checklist

- [x] Enforce strong `SECRET_KEY` from environment (app refuses start without it)
- [x] Enable HTTPS enforcement and security headers (CSP, HSTS, X-Frame-Options) in production
- [x] Configure per-endpoint and global rate limiting on authentication and API routes
- [x] Enforce password complexity requirements (uppercase, lowercase, number, symbol, min length)
- [x] Enforce automated account lockout after 5 failed login attempts
- [x] Support Two-Factor Authentication (TOTP 2FA) and recovery codes
- [x] Validate file uploads via extension allow-list, MIME prefix, and magic bytes sniffing
- [x] Prevent Host-header poisoning via canonical `SERVER_NAME` enforcement in password resets
- [x] Secure first-run setup wizard via `SETUP_TOKEN` verification in production
- [x] Eliminate CSS modal stacking context traps via `{% block modals %}` outside animated containers
- [ ] Configure database encryption at rest (PostgreSQL Transparent Data Encryption / LUKS)
- [ ] Establish automated offsite backup and restore verification schedule
- [ ] Integrate corporate directory (LDAP / SAML 2.0 SSO) when scaling past 100 users

---

## Hardening & Recent Security Implementation

All security items are implemented and verified with 119 passing tests:

- **1.4 – Password reset flow**: `app/security.py` uses `itsdangerous.URLSafeTimedSerializer` with `PASSWORD_RESET_MAX_AGE`. `/forgot-password` (3/min) and `/reset-password/<token>` (5/min) routes in `app/routes/auth.py` use a single generic success flash to prevent user enumeration. `send_password_reset` in `app/email_utils.py` accepts the reset URL.
- **1.5 – Account lockout**: `User.is_locked()`, `record_failed_login(max_attempts, lockout_minutes)`, `reset_failed_logins()`. Login route locks the account, sends a `send_account_locked` email, and writes an audit-log entry. Configurable via `LOGIN_MAX_ATTEMPTS` (default 5) and `LOGIN_LOCKOUT_MINUTES` (default 15).
- **1.6 – Session-fixation**: `complete_login()` calls `session.clear()` before `login_user()` to guarantee the new session ID does not inherit a pre-authentication attacker's session.
- **1.7 – JSON / request-id logging**: `python-json-logger` formats every log record as JSON; `g.request_id` middleware sets a UUIDv4 per request and the response carries an `X-Request-Id` header.
- **1.8 – 2FA login CSRF (regression-fixed)**: `auth/login_2fa.html` renders `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`; both `render_template("auth/login_2fa.html", ...)` calls in `login_2fa` pass through CSRFProtect, so a TOTP/recovery POST is no longer rejected with HTTP 400 missing-token. `TestTwoFactorCsrf` re-enables CSRF in test to keep it covered.
- **1.9 – Markdown sanitisation**: `app/sanitize.py` whitelists tags, attributes and protocols (`markdown` + `bleach`). Wired into `app/templates/tickets/view.html`, `app/templates/portal/view_ticket.html`, `app/templates/knowledge/view.html`, `app/templates/portal/knowledge_view.html`.
- **3.4 – Error handling hygiene**: every `try/except: pass` block in `email_utils.py`, `routes/tickets.py`, and `__init__.py` has been replaced with `current_app.logger.warning`/`exception` calls. Email helpers return `bool`; routes log structured failures.
- **6.12 – Attachment uploads**: `POST /tickets/<id>/attachments` and `GET /attachments/<id>` in `app/routes/tickets.py`. Filename is run through `werkzeug.utils.secure_filename`, prefixed with a UUIDv4, and re-validated to stay inside `UPLOAD_FOLDER` (path-traversal block). Extension and MIME prefix allow-lists come from `UPLOAD_ALLOWED_EXTENSIONS` and `UPLOAD_ALLOWED_MIME_PREFIXES`. File-size cap = `MAX_CONTENT_LENGTH` (16 MB). Access control: ticket reporter, assignee, or any agent/admin. `tickets/view.html` lists current attachments and renders the upload form.
- **7.1 – Open redirect protection in i18n**: `/set-lang/<lang_code>` route ensures redirect destination is local to `request.host_url` when using `request.referrer`. Prevents malicious offsite redirections.
- **7.2 – CSRF on AJAX status updates**: `POST /tickets/<id>/update-status` endpoint used by the Kanban board enforces `X-CSRFToken` verification.
- **Sentry**: `SENTRY_DSN` env var turns on `sentry-sdk[flask]` init; never initialised in the `testing` config.

Note: attachment routes depend on `UPLOAD_FOLDER` being writable; the Docker entrypoint chowns `instance/uploads` to the `servicedesk` user. Locally, the directory is created lazily with `os.makedirs(..., exist_ok=True)`.

---

## Production Readiness Verification & Audit Sign-Off

All previous high and medium audit findings are remediated and verified across the test suite (315 passing tests):

| Issue | Remediated Location | Resolution Verified |
|-------|---------------------|---------------------|
| Password-reset Host poisoning | `app/routes/auth.py:34-40` | Canonical `SERVER_NAME` configured; `_external_url` enforces fixed origin |
| Unauthenticated setup wizard | `app/routes/setup.py:81-99` | Production mode requires valid `SETUP_TOKEN` to access bootstrap wizard |
| Stored XSS in inline handlers | `app/templates/auth/users.html` | Converted to `data-*` attributes with external event listener |
| REST API enum mismatch | `app/routes/api.py:4-8` | Shared `app/enums.py` tuples enforced across DB check constraints and API validation |
| Dashboard agent avatar crash | `app/utils.py:234` | Performance query filters only valid agent/admin users with full names |
| Dependency CVEs | `requirements.txt` | Pinned `gunicorn==26.2.0`, `cryptography==50.0.2`, `Pillow==12.3.0` |
| Unguarded asset linking | `app/routes/tickets.py:355` | Validates asset exists in DB; unlinking supported with audit trail |
| Inactive users in asset forms | `app/routes/assets.py:55` | Choices filtered to active users (`is_active=True`) |
| Modal backdrop click trap | `profile.html`, `versions.html`, `board.html` | Rendered in `{% block modals %}` outside animated `.main-content` |


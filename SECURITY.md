# ServiceDesk Application Security Review

## Executive Summary

This document provides a comprehensive security assessment of the ServiceDesk application and outlines recommendations for enterprise deployment.

---

## Current Security Implementation

### ✅ Implemented Security Features

1. **CSRF Protection**: Flask-WTF CSRF tokens on all forms (time-limited 4h)
2. **Password Hashing**: Werkzeug's `generate_password_hash` using scrypt / pbkdf2:sha256
3. **Session Management**: Flask-Login with `session_protection="strong"`, anonymous user shim, secure cookie flags
4. **Authentication**: Role-based access control (admin, agent, user)
5. **Audit Logging**: Comprehensive action logging to database
6. **Database ORM**: SQLAlchemy prevents SQL injection
7. **File Upload Limits**: 16MB max content length configured
8. **Security Headers (production)**: Flask-Talisman with CSP, HSTS (1y, preload, includeSubDomains), `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, HTTPS redirect
9. **HTTPS-only cookies in production**: `SESSION_COOKIE_SECURE`, `REMEMBER_COOKIE_SECURE`
10. **Schema migrations**: Flask-Migrate / Alembic (replaces ad-hoc `db.create_all()` for production)

### ⚠️ Security Issues Found

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| ~~**HIGH**~~ | ~~Hardcoded SECRET_KEY~~ | `config.py` | **Fixed** – now refuses to start without env var |
| ~~**HIGH**~~ | ~~Default passwords in code~~ | `__init__.py`, `setup.py` | **Fixed** – random temp passwords via `secrets`; wizard still forces password change |
| ~~**MEDIUM**~~ | ~~No rate limiting~~ | All routes | Implemented Flask-Limiter (global + login) |
| ~~**MEDIUM**~~ | ~~No password strength validation~~ | `forms.py` | Implemented complexity regex |
| ~~**MEDIUM**~~ | ~~No input sanitization~~ | Templates | **Fixed** – `app/sanitize.py` renders markdown via `markdown` + `bleach`; `| markdown_safe` Jinja filter wired into ticket, comment and article templates |
| ~~**MEDIUM**~~ | ~~No password reset flow~~ | Auth | **Fixed** – `app/security.py` issues itsdangerous-signed tokens; `/forgot-password` and `/reset-password/<token>` routes with per-endpoint rate limits; `send_password_reset` email helper |
| ~~**HIGH**~~ | ~~No account lockout~~ | `auth.py` | **Fixed** – `LOGIN_MAX_ATTEMPTS` (5) / `LOGIN_LOCKOUT_MINUTES` (15) enforced; `User.is_locked()`, `record_failed_login()`, `reset_failed_logins()`; locked-account email sent |
| ~~**MEDIUM**~~ | ~~Email helpers swallow errors~~ | `email_utils.py`, route files | **Fixed** – all `except: pass` blocks replaced with structured `current_app.logger` warnings; helpers return bool |
| ~~**LOW**~~ | ~~No security headers~~ | `__init__.py` | **Fixed** – Flask-Talisman in production |
| ~~**LOW**~~ | ~~No HTTPS enforcement~~ | `run.py` | **Fixed** – Talisman + ProductionConfig |
| ~~**LOW**~~ | ~~Session fixation~~ | `auth.py` | **Fixed** – strong session protection + `session.clear()` on login |

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

### Missing Features for Enterprise Readiness

| Category | Feature | Priority | Description |
|----------|---------|----------|-------------|
| **Auth** | Two-Factor Authentication | HIGH | TOTP-based 2FA |
| **Auth** | LDAP/AD Integration | HIGH | Corporate directory sync |
| **Auth** | SSO/SAML | MEDIUM | Single sign-on support |
| **Auth** | Password Reset Flow | MEDIUM | Email-based reset |
| **Auth** | Account Lockout | HIGH | After failed attempts |
| **Notifications** | Email Templates | HIGH | Customizable templates |
| **Notifications** | SMS Notifications | MEDIUM | Twilio integration |
| **Notifications** | Slack/Teams Integration | MEDIUM | Channel notifications |
| **API** | API Authentication | HIGH | API keys/JWT |
| **API** | Rate Limiting | HIGH | Per-endpoint limits |
| **API** | Swagger Documentation | MEDIUM | OpenAPI spec |
| **Storage** | S3/File Storage | MEDIUM | Cloud storage support |
| **Monitoring** | Health Checks | MEDIUM | /health endpoint |
| **Monitoring** | Metrics Export | LOW | Prometheus integration |
| **Search** | Elasticsearch | LOW | Full-text search |

---

## Compliance Considerations

### GDPR Compliance
- [ ] Data export functionality
- [ ] Right to deletion
- [ ] Consent management
- [ ] Data processing agreement

### SOX Compliance
- [ ] Enhanced audit logging
- [ ] Access reviews
- [ ] Change management

### ISO 27001
- [ ] Security policies
- [ ] Incident response
- [ ] Vulnerability management

---

## Recommended Security Checklist Before Production

- [ ] Change SECRET_KEY to random 64-byte value
- [ ] Enable HTTPS only mode
- [ ] Configure security headers (CSP, HSTS, X-Frame-Options)
- [ ] Implement rate limiting on all auth endpoints
- [ ] Add password complexity requirements
- [ ] Enable account lockout after failed attempts
- [ ] Set up log aggregation
- [ ] Configure database encryption at rest
- [ ] Set up backup strategy
- [ ] Implement 2FA
- [ ] Add LDAP/AD integration
- [ ] Configure email notifications
- [ ] Add API rate limiting
- [ ] Implement audit log retention policy

---

## Week 2 Hardening – Completed

All Week 2 items are implemented and the test suite is green (32 passed):

- **1.4 – Password reset flow**: `app/security.py` uses `itsdangerous.URLSafeTimedSerializer` with `PASSWORD_RESET_MAX_AGE`. `/forgot-password` (3/min) and `/reset-password/<token>` (5/min) routes in `app/routes/auth.py` use a single generic success flash to prevent user enumeration. `send_password_reset` in `app/email_utils.py` accepts the reset URL.
- **1.5 – Account lockout**: `User.is_locked()`, `record_failed_login(max_attempts, lockout_minutes)`, `reset_failed_logins()`. Login route locks the account, sends a `send_account_locked` email, and writes an audit-log entry. Configurable via `LOGIN_MAX_ATTEMPTS` (default 5) and `LOGIN_LOCKOUT_MINUTES` (default 15).
- **1.6 – Session-fixation**: `complete_login()` calls `session.clear()` before `login_user()` to guarantee the new session ID does not inherit a pre-authentication attacker's session.
- **1.7 – JSON / request-id logging**: `python-json-logger` formats every log record as JSON; `g.request_id` middleware sets a UUIDv4 per request and the response carries an `X-Request-Id` header.
- **1.9 – Markdown sanitisation**: `app/sanitize.py` whitelists tags, attributes and protocols (`markdown` + `bleach`). Wired into `app/templates/tickets/view.html`, `app/templates/portal/view_ticket.html`, `app/templates/knowledge/view.html`, `app/templates/portal/knowledge_view.html`.
- **3.4 – Error handling hygiene**: every `try/except: pass` block in `email_utils.py`, `routes/tickets.py`, and `__init__.py` has been replaced with `current_app.logger.warning`/`exception` calls. Email helpers return `bool`; routes log structured failures.
- **6.12 – Attachment uploads**: `POST /tickets/<id>/attachments` and `GET /attachments/<id>` in `app/routes/tickets.py`. Filename is run through `werkzeug.utils.secure_filename`, prefixed with a UUIDv4, and re-validated to stay inside `UPLOAD_FOLDER` (path-traversal block). Extension and MIME prefix allow-lists come from `UPLOAD_ALLOWED_EXTENSIONS` and `UPLOAD_ALLOWED_MIME_PREFIXES`. File-size cap = `MAX_CONTENT_LENGTH` (16 MB). Access control: ticket reporter, assignee, or any agent/admin. `tickets/view.html` lists current attachments and renders the upload form.
- **Sentry**: `SENTRY_DSN` env var turns on `sentry-sdk[flask]` init; never initialised in the `testing` config.

Note: attachment routes depend on `UPLOAD_FOLDER` being writable; the Docker entrypoint chowns `instance/uploads` to the `servicedesk` user. Locally, the directory is created lazily with `os.makedirs(..., exist_ok=True)`.

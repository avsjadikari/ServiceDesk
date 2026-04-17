# ServiceDesk — Security Policy & Assessment

**Last Updated:** 2026-04-17  
**Version:** 1.0.0

---

## Executive Summary

This document provides the current security posture of the ServiceDesk application, implemented fixes, and recommendations for enterprise production deployment.

---

## Current Security Implementation ✅

| Control | Status | Implementation Detail |
|---------|--------|-----------------------|
| **CSRF Protection** | ✅ Implemented | Flask-WTF CSRF tokens on every state-changing form |
| **Password Hashing** | ✅ Implemented | Werkzeug `scrypt` (NIST recommended) |
| **Session Management** | ✅ Implemented | Flask-Login with 24-hour session lifetime |
| **Session Fixation Prevention** | ✅ Implemented | `session.clear()` called before `login_user()` |
| **Open Redirect Protection** | ✅ Implemented | `next` URL validated — only relative paths accepted |
| **Role-Based Access Control** | ✅ Implemented | Admin / Agent / User with route-level enforcement |
| **Audit Logging** | ✅ Implemented | All actions logged with user ID and IP address |
| **SQL Injection Prevention** | ✅ Implemented | SQLAlchemy ORM with parameterised queries |
| **File Upload Limits** | ✅ Implemented | 16 MB max content length |
| **Rate Limiting** | ✅ Implemented | Flask-Limiter: 5 login/min, 200 req/day |
| **Password Complexity** | ✅ Implemented | Upper, lower, digit, special char required |
| **Two-Factor Authentication** | ✅ Implemented | TOTP (RFC 6238) via PyOTP + QR code setup |
| **Email Security Alerts** | ✅ Implemented | 2FA enable/disable alerts sent to user |
| **Security Headers (prod)** | ✅ Implemented | Flask-Talisman: HSTS, X-Frame-Options, referrer policy |
| **Profile Form Validation** | ✅ Implemented | WTForms-validated ProfileForm (was raw `request.form`) |
| **Input Sanitisation** | ✅ Implemented | WTForms validators on all inputs; bleach for markdown |
| **Anonymous User Safety** | ✅ Implemented | Custom AnonymousUser class prevents AttributeError |
| **Health Endpoint** | ✅ Implemented | `/health` unauthenticated monitoring endpoint |

---

## Security Fixes Applied (This Release)

### 1. Open Redirect Vulnerability (HIGH — Fixed)

**Risk:** An attacker could craft a login URL with `?next=https://evil.com` and redirect authenticated users to a malicious site after login.

**Fix in `app/routes/auth.py`:**
```python
from urllib.parse import urlsplit

next_page = request.args.get("next")
if next_page:
    parsed = urlsplit(next_page)
    if parsed.netloc or parsed.scheme:
        next_page = None  # Reject external redirects
```

---

### 2. Session Fixation (MEDIUM — Fixed)

**Risk:** An attacker who obtained a session cookie before login could reuse it after authentication.

**Fix in `app/routes/auth.py`:**
```python
def complete_login(user, remember_me=False):
    session.clear()          # Invalidate any pre-login session
    login_user(user, remember=remember_me)
```

---

### 3. Unvalidated Profile Update (MEDIUM — Fixed)

**Risk:** The profile update route directly accepted raw `request.form` data with no validation, allowing oversized or malformed inputs.

**Fix:** Replaced with a `ProfileForm(FlaskForm)` with proper validators including email uniqueness checks.

---

### 4. Hardcoded Fallback Database Password (HIGH — Fixed)

**Risk:** `config.py` had a hardcoded default database password `"Zaq12wsX"` that would silently be used if `DB_PASSWORD` was unset.

**Fix in `config.py`:** Default is now `""` (empty) — forcing explicit configuration.

---

### 5. Deprecated `datetime.utcnow()` (LOW — Fixed)

**Risk:** Python 3.12+ deprecated `datetime.utcnow()`; this will raise errors in future Python versions.

**Fix:** All occurrences replaced with `datetime.now(timezone.utc)` and a `_now()` helper function in `models.py`. SLA datetime comparison now correctly handles both timezone-naive (SQLite) and timezone-aware (PostgreSQL) datetimes.

---

## Security Configuration Guide

### Rate Limiting

Rate limits are enforced per remote IP address via Flask-Limiter.

```python
# Current limits
@limiter.limit("5 per minute")     # Login endpoint
@limiter.limit("10 per minute")    # 2FA verification
@limiter.limit("200 per day")      # Global default
@limiter.limit("50 per hour")      # Global default
```

> For production, configure a Redis storage backend:
> ```env
> RATELIMIT_STORAGE_URI=redis://localhost:6379/0
> ```

---

### Security Headers (Production)

Flask-Talisman is automatically activated in non-debug mode:

| Header | Value |
|--------|-------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | Not set (allow inline JS/CSS for now) |

> **Recommendation:** Enable a strict CSP once all inline scripts are removed or nonce-tagged.

---

### Two-Factor Authentication

- Based on TOTP (RFC 6238) using PyOTP
- QR code generated server-side and shown once during setup
- Secret stored hashed in the `users.two_factor_secret` column
- Email alert sent on enable and disable events

---

### Session Security

| Setting | Value |
|---------|-------|
| Session lifetime | 24 hours (configurable) |
| Cookie `HttpOnly` | Yes (Flask default) |
| Cookie `Secure` | Yes in production (Talisman) |
| Cookie `SameSite` | Lax |
| Session fixation | Mitigated via `session.clear()` pre-login |

---

## Enterprise Production Checklist

### Before Go-Live

- [ ] Generate a 64-byte random `SECRET_KEY`:  
  `python -c "import secrets; print(secrets.token_hex(64))"`
- [ ] Set `FLASK_CONFIG=production` in `.env`
- [ ] Enable HTTPS / TLS termination (nginx, AWS ALB, Cloudflare)
- [ ] Set `DB_SSL_MODE=require` for PostgreSQL connections
- [ ] Configure Redis for rate-limiter storage (`RATELIMIT_STORAGE_URI`)
- [ ] Enable and test email notifications
- [ ] Force all default user password changes
- [ ] Review and tighten the Content-Security-Policy header
- [ ] Set up database backups (daily minimum)
- [ ] Configure log aggregation (ELK, Splunk, CloudWatch)
- [ ] Set up uptime monitoring on `/health` endpoint

### Ongoing Security

- [ ] Review audit logs weekly
- [ ] Rotate `SECRET_KEY` annually (or after compromise)
- [ ] Keep Python dependencies updated (`pip list --outdated`)
- [ ] Run `bandit -r app/` for static security analysis
- [ ] Run `safety check` to detect vulnerable dependencies

---

## Enterprise Features Gap Analysis

### Authentication & Identity

| Feature | Priority | Status | Notes |
|---------|----------|--------|-------|
| Account Lockout | HIGH | ❌ Missing | Lock after N failed attempts |
| Password Reset via Email | HIGH | ❌ Missing | Token-based self-service |
| LDAP / Active Directory | HIGH | ❌ Missing | Corporate directory sync |
| SSO / SAML 2.0 | MEDIUM | ❌ Missing | Okta, Azure AD, Keycloak |
| API Key Authentication | HIGH | ❌ Missing | Machine-to-machine API access |

### Notifications

| Feature | Priority | Status | Notes |
|---------|----------|--------|-------|
| Email Notifications | HIGH | ✅ Implemented | Ticket lifecycle events |
| SMS Notifications | MEDIUM | ❌ Missing | Twilio / AWS SNS |
| Slack / MS Teams | MEDIUM | ❌ Missing | Webhook integration |

### API & Integration

| Feature | Priority | Status | Notes |
|---------|----------|--------|-------|
| OpenAPI / Swagger | MEDIUM | ❌ Missing | Auto-generated API docs |
| JWT Authentication | HIGH | ❌ Missing | Stateless API tokens |
| Webhook Outbound | MEDIUM | ❌ Missing | Notify external systems |

### Storage & Infrastructure

| Feature | Priority | Status | Notes |
|---------|----------|--------|-------|
| Health Endpoint | MEDIUM | ✅ Implemented | `/health` returns DB + version |
| File Upload (Cloud) | MEDIUM | ❌ Missing | S3 / Azure Blob Storage |
| Prometheus Metrics | LOW | ❌ Missing | `/metrics` for Grafana |
| Elasticsearch | LOW | ❌ Missing | Full-text search at scale |

---

## Compliance Considerations

### GDPR

- [ ] Data export endpoint (right to access)
- [ ] Data deletion endpoint (right to erasure)
- [ ] Consent management on registration
- [ ] Data processing agreement documentation

### SOX / ISO 27001

- [ ] Enhanced audit log retention (7+ years for SOX)
- [ ] Quarterly access reviews
- [ ] Change management procedures
- [ ] Incident response runbook

---

## Reporting Security Issues

If you discover a security vulnerability, please **do not open a public GitHub issue**. Contact the security team directly at `security@yourcompany.com`. See your organisation's vulnerability disclosure policy for SLAs.

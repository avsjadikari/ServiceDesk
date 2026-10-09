"""Security headers (Talisman) and the CSP-nonce template helper."""

from flask import request
from flask_talisman import Talisman

_DEFAULT_CSP = {
    "default-src": "'self'",
    "img-src": ["'self'", "data:", "https:"],
    "script-src": [
        "'self'",
        "https://cdn.jsdelivr.net",
        "https://code.jquery.com",
    ],
    "style-src": [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.jsdelivr.net",
        "https://fonts.googleapis.com",
    ],
    "font-src": [
        "'self'",
        "https://fonts.gstatic.com",
        "https://cdn.jsdelivr.net",
        "data:",
    ],
    "connect-src": ["'self'"],
    "frame-ancestors": "'none'",
    "object-src": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
}


def init_security_headers(app) -> None:
    if app.config.get("TALISMAN_ENABLED", False):
        Talisman(
            app,
            force_https=app.config.get("TALISMAN_FORCE_HTTPS", True),
            strict_transport_security=True,
            strict_transport_security_max_age=31536000,
            strict_transport_security_include_subdomains=True,
            strict_transport_security_preload=True,
            content_security_policy=_DEFAULT_CSP,
            content_security_policy_nonce_in=["script-src"],
            frame_options="DENY",
            referrer_policy="strict-origin-when-cross-origin",
            session_cookie_secure=app.config.get("SESSION_COOKIE_SECURE", True),
        )

    if "csp_nonce" not in app.jinja_env.globals:

        @app.template_global()
        def csp_nonce() -> str:
            return getattr(request, "csp_nonce", "")

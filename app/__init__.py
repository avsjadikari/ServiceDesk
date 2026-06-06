import os
import logging
import secrets
import uuid

from flask import (
    Flask,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_migrate import Migrate
from pythonjsonlogger import jsonlogger

from config import config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()
limiter = Limiter(
    key_func=get_remote_address, default_limits=["200 per day", "50 per hour"]
)

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


def _generate_temp_password(length: int = 20) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@$!%*?&"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _install_json_logging(app) -> None:
    """Replace Flask's default text handler with a JSON one in non-test envs."""
    handler = logging.StreamHandler()
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
        )
    )
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)
    werkzeug = logging.getLogger("werkzeug")
    werkzeug.setLevel(logging.WARNING)
    logging.getLogger().setLevel(logging.INFO)


def _install_sentry(app) -> None:
    dsn = app.config.get("SENTRY_DSN")
    if not dsn or app.config.get("TESTING", False):
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except Exception:
        app.logger.warning("sentry-sdk not importable; skipping init")
        return

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FlaskIntegration(),
            SqlalchemyIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=app.config.get("SENTRY_TRACES_SAMPLE_RATE", 0.1),
        environment=os.environ.get("FLASK_CONFIG", "development"),
        release=os.environ.get("APP_RELEASE"),
        send_default_pii=False,
    )
    app.logger.info("Sentry initialised (env=%s)", os.environ.get("FLASK_CONFIG"))


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    if not app.config.get("TESTING", False):
        _install_json_logging(app)
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        )

    _install_sentry(app)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)

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

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.session_protection = "strong"

    class _AnonymousUser:
        is_authenticated = False
        is_active = False
        is_anonymous = True
        username = ""
        email = ""
        full_name = ""
        role = "anonymous"

        def is_admin(self):
            return False

        def is_agent(self):
            return False

        def get_id(self):
            return None

        def check_password(self, _password):
            return False

    login_manager.anonymous_user = _AnonymousUser

    from app.sanitize import render_markdown_safe, render_plain_safe

    @app.template_filter("markdown_safe")
    def _markdown_safe_filter(text):
        return render_markdown_safe(text)

    @app.template_filter("plain_safe")
    def _plain_safe_filter(text):
        return render_plain_safe(text)

    @app.template_filter("datetime_human")
    def _datetime_human_filter(value, fmt="%Y-%m-%d %H:%M"):
        if not value:
            return ""
        return value.strftime(fmt)

    @app.context_processor
    def inject_globals():
        try:
            from app.settings_store import display_company_name

            brand = display_company_name()
        except Exception:  # pragma: no cover - defensive
            brand = app.config.get("COMPANY_NAME", "ServiceDesk")
        return dict(
            company_name=brand,
            request_id=g.get("request_id"),
        )

    @app.before_request
    def assign_request_id():
        rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        g.request_id = rid

    @app.after_request
    def add_request_id_header(response):
        rid = getattr(g, "request_id", None)
        if rid:
            response.headers.setdefault("X-Request-Id", rid)
        return response

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except (ValueError, TypeError):
            return None

    from app.routes.setup import setup as setup_bp
    from app.routes.auth import auth as auth_bp
    from app.routes.main import main as main_bp
    from app.routes.tickets import tickets as tickets_bp
    from app.routes.knowledge import knowledge as knowledge_bp
    from app.routes.assets import assets as assets_bp
    from app.routes.analytics import analytics as analytics_bp
    from app.routes.portal import portal as portal_bp
    from app.routes.api import api as api_bp
    from app.routes.settings import settings as settings_bp

    app.register_blueprint(setup_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(settings_bp)

    # Initialise Flask-Mail and overlay DB-stored mail settings on top of
    # the env-var defaults so admins can change the mail server at runtime.
    from app.email_utils import init_mail as _init_mail
    from app.settings_store import apply_mail_config, get_mail_config

    _init_mail(app)
    with app.app_context():
        try:
            apply_mail_config(app)
            cfg = get_mail_config()
            if cfg.get("MAIL_DEFAULT_SENDER"):
                app.config["MAIL_DEFAULT_SENDER"] = cfg["MAIL_DEFAULT_SENDER"]
        except Exception:
            current_app_logger = __import__("logging").getLogger("app")
            current_app_logger.exception("apply_mail_config failed at startup")

    @app.before_request
    def check_setup():
        exempt_endpoints = {
            "setup.wizard",
            "setup.complete",
            "auth.login",
            "auth.login_2fa",
            "auth.register",
            "auth.forgot_password",
            "auth.reset_password",
            "auth.logout",
            "main.health",
            "main.ready",
            "static",
        }
        if not request.endpoint or request.endpoint in exempt_endpoints:
            return

        if session.get("setup_complete"):
            return

        try:
            admin_exists = User.query.filter_by(role="admin").first()
        except Exception:
            return

        if not admin_exists:
            from flask_login import logout_user

            logout_user()
            session.clear()
            return redirect(url_for("setup.wizard"))

    return app


def init_database():
    db.create_all()
    return _create_default_data()


def _create_default_data():
    from app.models import User, Article
    from sqlalchemy import text

    generated_passwords = {}

    if User.query.count() == 0:
        admin_pw = _generate_temp_password()
        admin = User(
            username="admin",
            email="admin@servicedesk.local",
            full_name="System Administrator",
            role="admin",
            department="IT",
            is_active=True,
            must_change_password=True,
        )
        admin.set_password(admin_pw)
        db.session.add(admin)
        generated_passwords["admin"] = admin_pw

        agent_pw = _generate_temp_password()
        agent = User(
            username="agent",
            email="agent@servicedesk.local",
            full_name="Support Agent",
            role="agent",
            department="IT Support",
            is_active=True,
            must_change_password=True,
        )
        agent.set_password(agent_pw)
        db.session.add(agent)
        generated_passwords["agent"] = agent_pw

        user_pw = _generate_temp_password()
        user = User(
            username="user",
            email="user@servicedesk.local",
            full_name="Regular User",
            role="user",
            department="Operations",
            is_active=True,
            must_change_password=True,
        )
        user.set_password(user_pw)
        db.session.add(user)
        generated_passwords["user"] = user_pw

    db.session.flush()

    if Article.query.count() == 0:
        admin_id = (
            User.query.filter_by(username="admin").with_entities(User.id).scalar() or 1
        )
        sample_articles = [
            Article(
                title="How to Reset Your Password",
                content=(
                    "# Password Reset Guide\n\n"
                    "Follow these steps to reset your password:\n\n"
                    '1. Go to the login page\n2. Click "Forgot Password"\n'
                    "3. Enter your email address\n"
                    "4. Check your inbox for reset link\n"
                    "5. Create a new password\n\n"
                    "**Requirements:**\n- At least 8 characters\n"
                    "- Include uppercase and lowercase\n"
                    "- Include a number\n- Include a special character"
                ),
                category="Account/Access",
                tags=["password", "reset", "security"],
                status="published",
                author_id=admin_id,
            ),
            Article(
                title="VPN Setup Guide",
                content=(
                    "# Connecting to VPN\n\n## Prerequisites\n"
                    "- Active directory credentials\n- VPN client installed\n\n"
                    "## Steps to Connect\n\n"
                    "1. Open the VPN client\n2. Enter server address: vpn.company.local\n"
                    "3. Click Connect\n4. Enter your credentials\n"
                    "5. Complete 2FA verification\n\n"
                    "## Troubleshooting\n\n"
                    "If you cannot connect:\n- Check your internet connection\n"
                    "- Verify credentials are correct\n- Contact IT support"
                ),
                category="Network",
                tags=["vpn", "remote", "network"],
                status="published",
                author_id=admin_id,
            ),
            Article(
                title="Requesting Software Installation",
                content=(
                    "# Software Request Process\n\n## Approved Software\n"
                    "The following software is pre-approved:\n"
                    "- Microsoft Office Suite\n- Adobe Acrobat Reader\n"
                    "- Chrome/Firefox browsers\n\n## Request Process\n\n"
                    "1. Log in to ServiceDesk\n2. Submit a new ticket\n"
                    '3. Select "Software Request"\n'
                    "4. Provide software name and business justification\n"
                    "5. Wait for approval (24-48 hours)\n\n"
                    "## Unapproved Software\n"
                    "For software not in the approved list, manager approval is required."
                ),
                category="Software",
                tags=["software", "request", "installation"],
                status="published",
                author_id=admin_id,
            ),
        ]
        for article in sample_articles:
            db.session.add(article)

    db.session.commit()

    if generated_passwords:
        app = None
        try:
            from flask import current_app

            app = current_app._get_current_object()
            stream = app.logger.info
        except Exception:
            stream = print
        stream(
            "Generated temporary credentials (must be changed on first login): "
            + ", ".join(f"{u}={p}" for u, p in generated_passwords.items())
        )

    return generated_passwords or None

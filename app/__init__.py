import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from config import config
from app.email_utils import init_mail

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address, default_limits=["200 per day", "50 per hour"]
)
talisman = None


class AnonymousUser:
    """Anonymous user stub — inherits Flask-Login defaults and adds app-specific helpers."""

    # Flask-Login checks is_authenticated as an attribute/property — provide it as False
    is_authenticated = False
    is_active = False
    is_anonymous = True

    def get_id(self):
        return None

    def is_agent(self):
        return False

    def is_admin(self):
        return False


def init_security(app):
    global talisman

    if not app.config.get("DEBUG", False):
        talisman = Talisman(
            app,
            content_security_policy=None,
            force_https_permanent=True,
            strict_transport_security="max-age=31536000; includeSubDomains",
            x_content_type_options="nosniff",
            x_frame_options="DENY",
            referrer_policy="strict-origin-when-cross-origin",
        )


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    init_security(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.anonymous_user = AnonymousUser

    @app.context_processor
    def inject_company_name():
        import os

        company_name = "ServiceDesk"
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
        )
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("COMPANY_NAME="):
                        company_name = line.split("=", 1)[1].strip()
                        break
        return dict(company_name=company_name)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except:
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
    from app.routes.settings import settings_bp

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

    @app.before_request
    def check_setup():
        try:
            db.session.rollback()
        except Exception:
            pass

        if request.endpoint and request.endpoint not in [
            "setup.wizard",
            "setup.complete",
            "setup.create_tables",
            "static",
            "health",
        ]:
            if not session.get("setup_complete"):
                try:
                    admin_exists = User.query.filter_by(role="admin").first()
                    if not admin_exists:
                        from flask_login import logout_user

                        logout_user()
                        session.clear()
                        return redirect(url_for("setup.wizard"))
                except Exception:
                    from flask_login import logout_user

                    logout_user()
                    session.clear()
                    return redirect(url_for("setup.wizard"))

    @app.route("/health")
    def health():
        from flask import jsonify

        try:
            db.session.execute(db.text("SELECT 1"))
            db_status = "ok"
        except Exception:
            db_status = "error"

        return jsonify(
            {
                "status": "ok" if db_status == "ok" else "degraded",
                "database": db_status,
                "version": "1.0.0",
            }
        ), 200 if db_status == "ok" else 503

    return app


def init_database():
    db.create_all()
    _create_default_data()


def _create_default_data():
    from app.models import User, Article

    if User.query.count() == 0:
        admin = User(
            username="admin",
            email="admin@servicedesk.local",
            full_name="System Administrator",
            role="admin",
            department="IT",
            is_active=True,
            must_change_password=True,
        )
        admin.set_password("Admin@123456")
        db.session.add(admin)

        agent = User(
            username="agent",
            email="agent@servicedesk.local",
            full_name="Support Agent",
            role="agent",
            department="IT Support",
            is_active=True,
            must_change_password=True,
        )
        agent.set_password("Agent@123456")
        db.session.add(agent)

        user = User(
            username="user",
            email="user@servicedesk.local",
            full_name="Regular User",
            role="user",
            department="Operations",
            is_active=True,
            must_change_password=True,
        )
        user.set_password("User@123456")
        db.session.add(user)

    if Article.query.count() == 0:
        sample_articles = [
            Article(
                title="How to Reset Your Password",
                content='# Password Reset Guide\n\nFollow these steps to reset your password:\n\n1. Go to the login page\n2. Click "Forgot Password"\n3. Enter your email address\n4. Check your inbox for reset link\n5. Create a new password\n\n**Requirements:**\n- At least 8 characters\n- Include uppercase and lowercase\n- Include a number\n- Include a special character',
                category="Account/Access",
                tags=["password", "reset", "security"],
                status="published",
                author_id=1,
            ),
            Article(
                title="VPN Setup Guide",
                content="# Connecting to VPN\n\n## Prerequisites\n- Active directory credentials\n- VPN client installed\n\n## Steps to Connect\n\n1. Open the VPN client\n2. Enter server address: vpn.company.local\n3. Click Connect\n4. Enter your credentials\n5. Complete 2FA verification\n\n## Troubleshooting\n\nIf you cannot connect:\n- Check your internet connection\n- Verify credentials are correct\n- Contact IT support",
                category="Network",
                tags=["vpn", "remote", "network"],
                status="published",
                author_id=1,
            ),
            Article(
                title="Requesting Software Installation",
                content='# Software Request Process\n\n## Approved Software\nThe following software is pre-approved:\n- Microsoft Office Suite\n- Adobe Acrobat Reader\n- Chrome/Firefox browsers\n\n## Request Process\n\n1. Log in to ServiceDesk\n2. Submit a new ticket\n3. Select "Software Request"\n4. Provide software name and business justification\n5. Wait for approval (24-48 hours)\n\n## Unapproved Software\nFor software not in the approved list, manager approval is required.',
                category="Software",
                tags=["software", "request", "installation"],
                status="published",
                author_id=1,
            ),
        ]
        for article in sample_articles:
            db.session.add(article)

    db.session.commit()

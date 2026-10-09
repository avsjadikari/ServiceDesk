"""Application factory and wiring.

The Flask app is assembled here from focused bootstrap helpers: extensions,
logging, security headers, template filters, request hooks, and error
handlers all live under ``app.bootstrap``. This module owns configuration,
extension init order, and blueprint registration — the composition root.
"""

import os
import logging

from flask import Flask

from config import config

from app.bootstrap.extensions import csrf, db, limiter, login_manager, migrate
from app.bootstrap.errors import register_error_handlers
from app.bootstrap.filters import register_filters
from app.bootstrap.hooks import register_hooks
from app.bootstrap.logging import install_json_logging, install_sentry
from app.bootstrap.security_headers import init_security_headers
from app.seed import init_database  # noqa: F401  (kept as package-level entry point)


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


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    if not app.config.get("TESTING", False):
        install_json_logging(app)
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        )

    install_sentry(app)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)

    init_security_headers(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.session_protection = "strong"
    login_manager.anonymous_user = _AnonymousUser

    register_filters(app)
    register_hooks(app)

    from app.i18n import i18n_bp, load_translations

    load_translations()

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
    app.register_blueprint(i18n_bp)

    # Apply DB-stored mail settings first so Flask-Mail picks them up.
    # Flask-Mail 0.9.1 caches config at init_app time, so the values
    # must already be on app.config before we call init_mail.
    from app.email_utils import init_mail as _init_mail
    from app.settings_store import apply_mail_config, get_mail_config

    with app.app_context():
        try:
            apply_mail_config(app)
            cfg = get_mail_config()
            if cfg.get("MAIL_DEFAULT_SENDER"):
                app.config["MAIL_DEFAULT_SENDER"] = cfg["MAIL_DEFAULT_SENDER"]
        except Exception:
            logging.getLogger("app").exception("apply_mail_config failed at startup")

    _init_mail(app)

    register_error_handlers(app)

    return app

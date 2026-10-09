"""Request lifecycle hooks: language resolution, request ids, session
teardown, the login user_loader, the first-run setup gate, and the request
size guard."""

import uuid

from flask import g, redirect, request, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from app.bootstrap.extensions import db, login_manager


def register_hooks(app) -> None:
    from app.i18n import SUPPORTED_LANGUAGES

    @app.before_request
    def resolve_language():
        lang = request.args.get("lang")
        if lang and lang in SUPPORTED_LANGUAGES:
            session["lang"] = lang
        if not lang or lang not in SUPPORTED_LANGUAGES:
            lang = session.get("lang")
        if not lang or lang not in SUPPORTED_LANGUAGES:
            best = request.accept_languages.best_match(list(SUPPORTED_LANGUAGES.keys()))
            lang = best if best else "en"

        g.lang = lang
        g.lang_dir = SUPPORTED_LANGUAGES.get(lang, {}).get("dir", "ltr")

    @app.before_request
    def assign_request_id():
        g.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex

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
            "i18n.set_language",
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

    @app.before_request
    def enforce_request_size_limit():
        limit = app.config.get("MAX_CONTENT_LENGTH")
        if limit and request.content_length and request.content_length > limit:
            raise RequestEntityTooLarge()

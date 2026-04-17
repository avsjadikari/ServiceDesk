from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    session,
    current_app,
)
from flask_login import login_required, current_user, logout_user
from app.forms import SettingsForm
from app.utils import log_audit
import os

settings_bp = Blueprint("settings", __name__)


def get_env_path():
    return os.path.join(current_app.root_path, ".env")


def load_env():
    env = {}
    env_path = get_env_path()
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env[key] = value
    return env


def save_env_file(data):
    env_path = get_env_path()
    with open(env_path, "w") as f:
        for key, value in data.items():
            f.write(f"{key}={value}\n")


def get_settings():
    env = load_env()
    return {
        "company_name": env.get("COMPANY_NAME", "ServiceDesk"),
        "db_type": env.get("DB_TYPE", "sqlite"),
        "db_host": env.get("DB_HOST", "localhost"),
        "db_port": env.get("DB_PORT", "5432"),
        "db_name": env.get("DB_NAME", "servicedesk"),
        "db_user": env.get("DB_USER", "servicedesk"),
        "db_password": env.get("DB_PASSWORD", ""),
        "db_ssl_mode": env.get("DB_SSL_MODE", "prefer"),
        "mail_server": env.get("MAIL_SERVER", "smtp.gmail.com"),
        "mail_port": env.get("MAIL_PORT", "587"),
        "mail_use_tls": env.get("MAIL_USE_TLS", "true") == "true",
        "mail_use_ssl": env.get("MAIL_USE_SSL", "false") == "true",
        "mail_username": env.get("MAIL_USERNAME", ""),
        "mail_password": env.get("MAIL_PASSWORD", ""),
        "mail_default_sender": env.get(
            "MAIL_DEFAULT_SENDER", "noreply@servicedesk.local"
        ),
    }


@settings_bp.route("/settings", methods=["GET", "POST"])
@login_required
def index():
    if not current_user.is_admin():
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("main.dashboard"))

    settings_data = get_settings()
    db_changed = False

    # Debug: show what we're reading
    from flask import current_app

    env_path = os.path.join(current_app.root_path, ".env")

    form = SettingsForm(data=settings_data)

    form.db_type.choices = [
        ("sqlite", "SQLite (Development)"),
        ("postgresql", "PostgreSQL (Production)"),
    ]
    form.db_ssl_mode.choices = [
        ("disable", "Disable"),
        ("prefer", "Prefer"),
        ("require", "Require"),
        ("verify-full", "Verify Full"),
    ]

    if form.validate_on_submit():
        old_db = {
            "db_type": settings_data.get("db_type", ""),
            "db_host": settings_data.get("db_host", ""),
            "db_port": str(settings_data.get("db_port", "")),
            "db_name": settings_data.get("db_name", ""),
        }

        new_db = {
            "db_type": form.db_type.data,
            "db_host": form.db_host.data,
            "db_port": str(form.db_port.data),
            "db_name": form.db_name.data,
        }

        if old_db != new_db:
            db_changed = True

        existing_env = load_env()

        env_data = {
            "COMPANY_NAME": form.company_name.data,
            "DB_TYPE": form.db_type.data,
            "DB_HOST": form.db_host.data,
            "DB_PORT": str(form.db_port.data),
            "DB_NAME": form.db_name.data,
            "DB_USER": form.db_user.data,
            "DB_PASSWORD": form.db_password.data
            if form.db_password.data
            else settings_data.get("db_password", ""),
            "DB_SSL_MODE": form.db_ssl_mode.data,
            "MAIL_SERVER": form.mail_server.data,
            "MAIL_PORT": str(form.mail_port.data),
            "MAIL_USE_TLS": "true" if form.mail_use_tls.data else "false",
            "MAIL_USE_SSL": "true" if form.mail_use_ssl.data else "false",
            "MAIL_USERNAME": form.mail_username.data,
            "MAIL_PASSWORD": form.mail_password.data
            if form.mail_password.data
            else settings_data.get("mail_password", ""),
            "MAIL_DEFAULT_SENDER": form.mail_default_sender.data,
            "SECRET_KEY": existing_env.get("SECRET_KEY", ""),
            "FLASK_ENV": existing_env.get("FLASK_ENV", "development"),
        }

        save_env_file(env_data)

        log_audit(current_user.id, "settings_update", "system", 0, "Updated settings")

        # Debug: verify what was saved
        saved_env = load_env()
        flash(
            f"Settings saved! COMPANY_NAME in .env is now: {saved_env.get('COMPANY_NAME', 'NOT FOUND')}",
            "success",
        )

        if db_changed:
            flash("Database config changed. Please restart application.", "warning")
            return render_template("settings/index.html", form=form, db_changed=True)

        return redirect(url_for("settings.index"))

    return render_template("settings/index.html", form=form, db_changed=False)


@settings_bp.route("/settings/save-db-change", methods=["POST"])
@login_required
def save_db_change():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    logout_user()
    session.clear()

    flash("Config saved. Please restart application manually.", "info")
    return redirect(url_for("auth.login"))

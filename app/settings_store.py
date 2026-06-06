"""Helpers for the SystemSetting key-value store.

Settings are persisted in the `system_settings` table. The company name
is the first one: stored raw (e.g. "Acme"), but the helper
`display_company_name()` always returns "<stored> ServiceDesk" so every
page and dashboard renders the full brand string consistently.

Mail server settings are also stored here. The DB values take
precedence over the env-var defaults, so an admin can change the mail
server at runtime without restarting the app.
"""

from flask import current_app
from sqlalchemy.exc import OperationalError, ProgrammingError

from app import db
from app.models import SystemSetting

COMPANY_NAME_KEY = "company_name"
DEFAULT_COMPANY_NAME = "ServiceDesk"
PRODUCT_SUFFIX = " ServiceDesk"


MAIL_KEYS = {
    "mail_server": "MAIL_SERVER",
    "mail_port": "MAIL_PORT",
    "mail_use_tls": "MAIL_USE_TLS",
    "mail_username": "MAIL_USERNAME",
    "mail_password": "MAIL_PASSWORD",
    "mail_default_sender": "MAIL_DEFAULT_SENDER",
}


def get_setting(key, default=None):
    """Read a setting from the DB; fall back to ``default`` if missing or
    if the table doesn't exist yet (e.g. mid-setup)."""
    try:
        row = SystemSetting.query.filter_by(key=key).first()
    except (OperationalError, ProgrammingError):
        return default
    if row is None or row.value is None or row.value == "":
        return default
    return row.value


def set_setting(key, value, user_id=None):
    """Insert or update a setting."""
    row = SystemSetting.query.filter_by(key=key).first()
    if row is None:
        row = SystemSetting(key=key, value=value, updated_by=user_id)
        db.session.add(row)
    else:
        row.value = value
        row.updated_by = user_id
    db.session.commit()
    return row


def delete_setting(key):
    """Remove a setting (revert to env-var default)."""
    row = SystemSetting.query.filter_by(key=key).first()
    if row is not None:
        db.session.delete(row)
        db.session.commit()
    return row


def get_company_name():
    """Return the raw stored company name (no suffix).

    Falls back to ``COMPANY_NAME`` env var or ``DEFAULT_COMPANY_NAME``.
    """
    stored = get_setting(COMPANY_NAME_KEY)
    if stored:
        return stored
    return current_app.config.get("COMPANY_NAME") or DEFAULT_COMPANY_NAME


def display_company_name():
    """Return the full brand string used in every UI surface.

    The stored company name is concatenated with ``PRODUCT_SUFFIX`` so
    the result is always "<Company> ServiceDesk" on every page and
    dashboard.
    """
    raw = (get_company_name() or "").strip()
    if not raw:
        raw = DEFAULT_COMPANY_NAME
    return f"{raw}{PRODUCT_SUFFIX}"


def set_company_name(value, user_id=None):
    """Store the raw company name (suffix is added on display)."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("Company name cannot be empty")
    return set_setting(COMPANY_NAME_KEY, cleaned, user_id=user_id)


def get_mail_config():
    """Return the effective mail server config, merging DB overrides on
    top of the Flask config (which itself reads env vars)."""
    cfg = {
        "MAIL_SERVER": current_app.config.get("MAIL_SERVER")
        or "smtp.gmail.com",
        "MAIL_PORT": current_app.config.get("MAIL_PORT", 587),
        "MAIL_USE_TLS": current_app.config.get("MAIL_USE_TLS", True),
        "MAIL_USERNAME": current_app.config.get("MAIL_USERNAME"),
        "MAIL_PASSWORD": current_app.config.get("MAIL_PASSWORD"),
        "MAIL_DEFAULT_SENDER": current_app.config.get("MAIL_DEFAULT_SENDER"),
    }
    # Overlay DB-stored values; empty strings clear the override.
    db_server = get_setting(MAIL_KEYS["mail_server"])
    if db_server is not None:
        cfg["MAIL_SERVER"] = db_server
    db_port = get_setting(MAIL_KEYS["mail_port"])
    if db_port is not None:
        try:
            cfg["MAIL_PORT"] = int(db_port)
        except (TypeError, ValueError):
            pass
    db_tls = get_setting(MAIL_KEYS["mail_use_tls"])
    if db_tls is not None:
        cfg["MAIL_USE_TLS"] = db_tls.strip().lower() in ("true", "1", "on", "yes")
    db_user = get_setting(MAIL_KEYS["mail_username"])
    if db_user is not None:
        cfg["MAIL_USERNAME"] = db_user
    db_pass = get_setting(MAIL_KEYS["mail_password"])
    if db_pass is not None:
        cfg["MAIL_PASSWORD"] = db_pass
    db_sender = get_setting(MAIL_KEYS["mail_default_sender"])
    if db_sender is not None:
        cfg["MAIL_DEFAULT_SENDER"] = db_sender
    return cfg


def mail_is_configured():
    """True when both a server and a username have been set."""
    cfg = get_mail_config()
    return bool(cfg.get("MAIL_SERVER") and cfg.get("MAIL_USERNAME"))


def apply_mail_config(app):
    """Push the merged mail config onto ``app.config``.

    Should be called once at app start, and again after the admin saves
    new settings (so the running app picks them up without a restart).
    """
    cfg = get_mail_config()
    app.config["MAIL_SERVER"] = cfg["MAIL_SERVER"]
    app.config["MAIL_PORT"] = cfg["MAIL_PORT"]
    app.config["MAIL_USE_TLS"] = cfg["MAIL_USE_TLS"]
    app.config["MAIL_USERNAME"] = cfg["MAIL_USERNAME"]
    app.config["MAIL_PASSWORD"] = cfg["MAIL_PASSWORD"]
    app.config["MAIL_DEFAULT_SENDER"] = cfg["MAIL_DEFAULT_SENDER"]


def set_mail_config(values, user_id=None):
    """Persist a dict of mail settings; missing keys are left alone."""
    for setting_key, value in values.items():
        if setting_key not in MAIL_KEYS:
            continue
        if value in (None, ""):
            delete_setting(MAIL_KEYS[setting_key])
        else:
            set_setting(MAIL_KEYS[setting_key], str(value), user_id=user_id)


def mask_secret(value):
    """Return ``value`` with most characters replaced for display."""
    if not value:
        return ""
    if len(value) <= 4:
        return "•" * len(value)
    return value[:2] + "•" * (len(value) - 4) + value[-2:]

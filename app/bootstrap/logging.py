"""Logging and error-reporting setup."""

import logging
import os

from pythonjsonlogger import jsonlogger


def install_json_logging(app) -> None:
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
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger().setLevel(logging.INFO)


def install_sentry(app) -> None:
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

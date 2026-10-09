"""Template filters and context processors."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import g


def register_filters(app) -> None:
    from app.enums import (
        PRIORITY_COLORS,
        PRIORITY_LABELS,
        STATUS_COLORS,
        STATUS_LABELS,
    )
    from app.i18n import SUPPORTED_LANGUAGES, t
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
        zone = ZoneInfo(getattr(g, "app_timezone", "UTC") or "UTC")
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc).astimezone(zone)
        return value.strftime(fmt)

    @app.template_filter("status_color")
    def _status_color_filter(status):
        return STATUS_COLORS.get(status, "secondary")

    @app.template_filter("priority_color")
    def _priority_color_filter(priority):
        return PRIORITY_COLORS.get(priority, "secondary")

    @app.template_filter("status_label")
    def _status_label_filter(status):
        return STATUS_LABELS.get(status, status)

    @app.template_filter("priority_label")
    def _priority_label_filter(priority):
        return PRIORITY_LABELS.get(priority, priority)

    @app.context_processor
    def inject_status_labels():
        return {"STATUS_LABELS": STATUS_LABELS}

    @app.context_processor
    def inject_globals():
        try:
            from app.settings_store import display_company_name, get_app_timezone

            brand = display_company_name()
            tz_name = get_app_timezone()
            try:
                ZoneInfo(tz_name)
            except Exception:  # defensively fall back if stored value is stale
                tz_name = "UTC"
            g.app_timezone = tz_name
        except Exception:  # pragma: no cover - defensive
            brand = app.config.get("COMPANY_NAME", "ServiceDesk")
            g.app_timezone = "UTC"
        return dict(
            company_name=brand,
            app_timezone=g.app_timezone,
            request_id=g.get("request_id"),
            now=datetime.utcnow,
            t=t,
            _=t,
            current_lang=getattr(g, "lang", "en"),
            current_lang_dir=getattr(g, "lang_dir", "ltr"),
            supported_languages=SUPPORTED_LANGUAGES,
        )

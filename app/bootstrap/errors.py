"""HTTP error handlers."""

from flask import flash, jsonify, redirect, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge


def register_error_handlers(app) -> None:
    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(exc):
        from urllib.parse import urlsplit

        limit_mb = app.config.get("MAX_CONTENT_LENGTH", 0) // (1024 * 1024)
        if request.path.startswith("/api/"):
            return jsonify({"error": f"Request body exceeds the {limit_mb} MB limit"}), 413

        target = request.referrer or url_for("main.index")
        if urlsplit(target).netloc not in ("", request.host):
            target = url_for("main.index")
        flash(f"Request is too large (max {limit_mb} MB).", "danger")
        return redirect(target)

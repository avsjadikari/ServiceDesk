"""HTTP error handlers."""

from flask import flash, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge


def register_error_handlers(app) -> None:
    def _render_error(code, message):
        if request.path.startswith("/api/"):
            return jsonify({"error": message}), code
        return render_template("errors/error.html", code=code, message=message), code

    @app.errorhandler(403)
    def handle_forbidden(exc):
        return _render_error(403, "You don't have permission to access this page.")

    @app.errorhandler(404)
    def handle_not_found(exc):
        return _render_error(404, "We couldn't find the page you were looking for.")

    @app.errorhandler(500)
    def handle_server_error(exc):
        return _render_error(500, "Something went wrong on our end. Please try again.")

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

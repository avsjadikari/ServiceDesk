"""Password reset token utilities (itsdangerous signed tokens)."""
from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from flask import current_app


_RESET_SALT = "servicedesk.password-reset.v1"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt=_RESET_SALT,
    )


def generate_password_reset_token(user_id: int) -> str:
    """Return a single-use, time-limited signed token for a user id."""
    return _serializer().dumps({"user_id": user_id})


def verify_password_reset_token(token: str) -> int | None:
    """Return the user_id encoded in the token, or None if invalid/expired."""
    try:
        payload = _serializer().loads(
            token,
            max_age=current_app.config.get(
                "PASSWORD_RESET_MAX_AGE", 30 * 60
            ),
        )
    except SignatureExpired:
        current_app.logger.info("Password reset token expired")
        return None
    except BadSignature:
        current_app.logger.warning("Invalid password reset token presented")
        return None
    user_id = payload.get("user_id") if isinstance(payload, dict) else None
    return int(user_id) if user_id is not None else None

"""Password reset token utilities (itsdangerous signed tokens)."""
from __future__ import annotations

import hashlib
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from flask import current_app


_RESET_SALT = "servicedesk.password-reset.v1"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt=_RESET_SALT,
    )


def _pwd_fingerprint(pwd_hash: str | None) -> str:
    if not pwd_hash:
        return ""
    return hashlib.sha256(pwd_hash.encode()).hexdigest()[:16]


def generate_password_reset_token(user_id: int) -> str:
    """Return a single-use, time-limited signed token for a user id."""
    from app.models import User

    user = User.query.get(int(user_id))
    pwd = _pwd_fingerprint(user.password_hash) if user else ""
    return _serializer().dumps({"user_id": int(user_id), "pwd": pwd})


def verify_password_reset_token(token: str) -> int | None:
    """Return the user_id encoded in the token, or None if invalid/expired/already used."""
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
    if user_id is None:
        return None

    from app.models import User

    user = User.query.get(int(user_id))
    if not user:
        return None

    token_pwd = payload.get("pwd")
    if token_pwd is not None:
        if token_pwd != _pwd_fingerprint(user.password_hash):
            current_app.logger.info(
                "Password reset token already used (password changed)"
            )
            return None

    return int(user.id)

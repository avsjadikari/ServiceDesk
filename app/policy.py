"""Authorization policy: the single place "who may see or do what" is
decided. Routes ask these helpers instead of re-deriving role checks inline,
so the rules cannot drift between the web, portal, and API surfaces.
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

from flask import abort, flash, redirect, url_for
from flask_login import current_user

if TYPE_CHECKING:
    from app.models import Asset, Ticket, User


def can_view_ticket(user: User, ticket: Ticket) -> bool:
    """A ticket is visible to its reporter and to any agent or admin."""
    if not user.is_authenticated:
        return False
    if user.is_agent():
        return True
    return ticket.created_by == user.id


def can_view_portal_ticket(user: User, ticket: Ticket) -> bool:
    """The portal is end-user territory: only the reporter may view there."""
    return user.is_authenticated and ticket.created_by == user.id


def can_view_asset(user: User, asset: Asset) -> bool:
    """Agents see every asset; others see only assets assigned to them."""
    if not user.is_authenticated:
        return False
    if user.is_agent():
        return True
    return asset.assigned_to == user.id


def web_admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
    """Web guard for admin-only pages: flash and bounce to the dashboard."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("Access denied.", "danger")
            return redirect(url_for("main.dashboard"))
        return view(*args, **kwargs)

    return wrapped


def web_agent_required(view: Callable[..., Any]) -> Callable[..., Any]:
    """Web guard for agent/admin-only pages: 403 for everyone else."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if not current_user.is_authenticated or not current_user.is_agent():
            abort(403)
        return view(*args, **kwargs)

    return wrapped

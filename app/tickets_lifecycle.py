"""Ticket lifecycle: the single place ticket writes, audit, automation, and
notifications are orchestrated. Route callables are adapters — they validate
HTTP input, call a function here, then own the commit and the response.

Nothing in this module commits. That keeps each request's writes in one
transaction and lets callers (web, portal, API) share identical behaviour
instead of re-deriving timestamp/audit/notify rules per surface.
"""

from app import db, email_utils
from app.models import Comment
from app.utils import apply_automation_rules, build_ticket, log_ticket_audit


def create_ticket(
    *,
    title,
    description,
    ticket_type,
    priority,
    category,
    created_by_id,
    assigned_to=None,
):
    """Build, persist, audit, run creation automation, and notify. Returns
    the saved ticket (flushed, not committed)."""
    ticket = build_ticket(
        title=title,
        description=description,
        ticket_type=ticket_type,
        priority=priority,
        category=category,
        created_by_id=created_by_id,
        assigned_to=assigned_to,
    )
    db.session.add(ticket)
    db.session.flush()

    log_ticket_audit(ticket, "create", commit=False)
    apply_automation_rules(ticket, "ticket_created", commit=False)
    email_utils.notify(email_utils.send_ticket_created, ticket)
    return ticket


def change_status(ticket, new_status):
    """Apply a status transition: set status, stamp timestamps, audit, notify."""
    old_status = ticket.status
    ticket.status = new_status
    ticket.apply_status_timestamps(new_status)
    db.session.flush()

    log_ticket_audit(
        ticket,
        "status_change",
        {"old_status": old_status, "new_status": new_status},
        commit=False,
    )
    email_utils.notify(email_utils.send_ticket_status_changed, ticket, new_status)
    return ticket


def assign_ticket(ticket, assignee_id):
    """Assign an agent (promoting a new ticket to assigned), audit, notify."""
    ticket.assigned_to = assignee_id
    ticket.promote_status_if_new()
    db.session.flush()

    log_ticket_audit(
        ticket, "assign", {"assigned_to": assignee_id}, commit=False
    )
    email_utils.notify(email_utils.send_ticket_assigned, ticket)
    return ticket


def add_comment(ticket, content, is_internal, user_id):
    """Persist a comment on a ticket, audit it, and notify watchers."""
    comment = Comment(
        ticket_id=ticket.id,
        user_id=user_id,
        content=content,
        is_internal=is_internal,
    )
    db.session.add(comment)
    db.session.flush()

    log_ticket_audit(ticket, "comment", commit=False)
    email_utils.notify(email_utils.send_ticket_comment, ticket, comment)
    return comment

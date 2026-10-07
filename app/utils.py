import re
from datetime import datetime, timedelta
from flask import current_app, has_request_context, request
from flask_login import current_user
from app import db
from app.enums import (
    TICKET_CLOSED_STATUSES,
    TICKET_OPEN_STATUSES,
    TICKET_PRIORITIES,
    TICKET_STATUSES,
)
from app.models import Ticket, AuditLog, User

# Shared ticket-domain helpers: numbering, SLA math, audit logging, automation
# rules, presentation colors, dashboard metrics, and upload sniff validation.


def generate_ticket_number():
    last_ticket = Ticket.query.order_by(Ticket.id.desc()).first()
    if last_ticket:
        last_num = int(last_ticket.ticket_number.split("-")[1])
        new_num = last_num + 1
    else:
        new_num = 1000
    return f"TKT-{new_num:06d}"


def build_ticket(
    title,
    description,
    ticket_type,
    priority,
    category,
    created_by_id,
    assigned_to=None,
    sla_config=None,
    now=None,
):
    """Construct an unsaved Ticket: auto-number, SLA deadline from priority,
    and promote-to-assigned when an assignee is given. Shared by the agent,
    portal, and API creation flows so the mapping lives in one place."""
    ticket = Ticket(
        ticket_number=generate_ticket_number(),
        title=title,
        description=description,
        type=ticket_type,
        priority=priority,
        category=category,
        created_by=created_by_id,
        sla_deadline=calculate_sla_deadline(
            priority, sla_config=sla_config, now=now
        ),
    )
    if assigned_to:
        ticket.assigned_to = assigned_to
        ticket.promote_status_if_new()
    return ticket


def calculate_sla_deadline(priority, sla_config=None, now=None):
    """SLA deadline for a priority. Domain-pure: pass sla_config + now to
    test without app context; defaults read the Flask config."""
    sla_config = (
        sla_config
        if sla_config is not None
        else current_app.config.get("SLA_CONFIG", {})
    )
    now = now or datetime.utcnow()
    if priority in sla_config:
        hours = sla_config[priority]["resolution_hours"]
        return now + timedelta(hours=hours)
    return now + timedelta(hours=24)


def _client_ip():
    if not has_request_context():
        return None
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def log_audit(
    user_id,
    action,
    entity_type=None,
    entity_id=None,
    ticket_id=None,
    details=None,
    ip_address=None,
    commit=True,
):
    """Add an AuditLog row. By default commits; pass commit=False when the
    caller wants the audit row to share the surrounding transaction."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ticket_id=ticket_id,
        details=details,
        ip_address=ip_address or _client_ip(),
    )
    db.session.add(log)
    if commit:
        db.session.commit()


def log_ticket_audit(ticket, action, details=None, commit=True):
    """Record an audit event for a ticket. A ticket row always maps the
    same way (entity_type="ticket", entity_id=ticket.id, ticket_id=ticket.id),
    so that decision lives here instead of each route."""
    log_audit(
        current_user.id,
        action,
        entity_type="ticket",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        details=details,
        commit=commit,
    )


def get_status_color(status):
    colors = {
        s: c
        for s, c in zip(
            TICKET_STATUSES, ("primary", "info", "warning", "secondary", "success", "dark")
        )
    }
    return colors.get(status, "secondary")


def get_priority_color(priority):
    colors = {
        s: c
        for s, c in zip(
            TICKET_PRIORITIES, ("success", "warning", "danger", "danger")
        )
    }
    return colors.get(priority, "secondary")


def apply_automation_rules(ticket, trigger_type):
    from app.models import AutomationRule

    rules = (
        AutomationRule.query.filter_by(trigger_type=trigger_type, is_active=True)
        .order_by(AutomationRule.priority.desc())
        .all()
    )

    for rule in rules:
        _execute_automation_rule(ticket, rule)


def _execute_automation_rule(ticket, rule):
    if rule.action_type == "assign":
        if rule.action_config and "assign_to" in rule.action_config:
            assignee_id = rule.action_config["assign_to"]
            assignee = User.query.get(assignee_id)
            if assignee:
                ticket.assigned_to = assignee_id
                ticket.status = "assigned"
                db.session.commit()

    elif rule.action_type == "notify":
        pass

    elif rule.action_type == "escalate":
        if ticket.priority in ["high", "critical"]:
            ticket.priority = "critical"
            db.session.commit()


def parse_tags(tag_string):
    if not tag_string:
        return []
    return [tag.strip() for tag in tag_string.split(",") if tag.strip()]


def get_ticket_metrics():
    total = Ticket.query.count()
    open_tickets = Ticket.query.filter(Ticket.status.in_(TICKET_OPEN_STATUSES)).count()
    resolved = Ticket.query.filter_by(status="resolved").count()
    closed = Ticket.query.filter_by(status="closed").count()

    by_priority = {}
    for priority in TICKET_PRIORITIES:
        by_priority[priority] = Ticket.query.filter_by(priority=priority).count()

    by_status = {}
    for status in TICKET_STATUSES:
        by_status[status] = Ticket.query.filter_by(status=status).count()

    by_category = {}
    categories = [
        "Hardware",
        "Software",
        "Network",
        "Security",
        "Email",
        "Account/Access",
        "Application",
        "Database",
        "Other",
    ]
    for cat in categories:
        by_category[cat] = Ticket.query.filter_by(category=cat).count()

    return {
        "total": total,
        "open": open_tickets,
        "resolved": resolved,
        "closed": closed,
        "by_priority": by_priority,
        "by_status": by_status,
        "by_category": by_category,
    }


def get_agent_performance():
    agents = User.query.filter(User.role.in_(["agent", "admin"])).all()
    performance = []

    for agent in agents:
        assigned = Ticket.query.filter_by(assigned_to=agent.id).count()
        resolved = Ticket.query.filter_by(
            assigned_to=agent.id, status="resolved"
        ).count()

        avg_resolution = None
        resolved_tickets = Ticket.query.filter_by(
            assigned_to=agent.id, status="resolved"
        ).all()
        resolution_times = [
            t.resolution_time for t in resolved_tickets if t.resolution_time
        ]
        if resolution_times:
            avg_resolution = sum(resolution_times) / len(resolution_times)

        performance.append(
            {
                "agent": agent,
                "assigned": assigned,
                "resolved": resolved,
                "avg_resolution_hours": avg_resolution if avg_resolution else 0,
            }
        )

    return performance


def calculate_sla_compliance():
    resolved_tickets = Ticket.query.filter(
        Ticket.status.in_(TICKET_CLOSED_STATUSES), Ticket.resolved_at.isnot(None)
    ).all()

    if not resolved_tickets:
        return {"compliance_rate": 100, "breached": 0, "met": 0}

    met = 0
    breached = 0

    for ticket in resolved_tickets:
        if ticket.sla_deadline and ticket.resolved_at <= ticket.sla_deadline:
            met += 1
        elif ticket.sla_deadline:
            breached += 1

    total = met + breached
    compliance_rate = (met / total * 100) if total > 0 else 100

    return {
        "compliance_rate": round(compliance_rate, 1),
        "met": met,
        "breached": breached,
        "total": total,
    }


_MAGIC_SIGNATURES = {
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "gif": [b"GIF87a", b"GIF89a"],
    "pdf": [b"%PDF"],
    "zip": [b"PK\x03\x04", b"PK\x05\x06"],
    "gz": [b"\x1f\x8b"],
    "doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    "xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    "ppt": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    "docx": [b"PK\x03\x04", b"PK\x05\x06"],
    "xlsx": [b"PK\x03\x04", b"PK\x05\x06"],
    "pptx": [b"PK\x03\x04", b"PK\x05\x06"],
    "odt": [b"PK\x03\x04", b"PK\x05\x06"],
    "ods": [b"PK\x03\x04", b"PK\x05\x06"],
    "odp": [b"PK\x03\x04", b"PK\x05\x06"],
}


def validate_upload_sniff(filename, head):
    """Verify that the file's magic bytes match its extension where a
    reliable signature exists for that extension. Returns True for
    formats without a signature (txt/csv/log/md/tar/svg...) so those fall
    back to the existing extension/MIME checks."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    signatures = _MAGIC_SIGNATURES.get(ext)
    if not signatures:
        return True
    return any(head.startswith(sig) for sig in signatures)

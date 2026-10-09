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


def generate_ticket_number() -> str:
    last_ticket = Ticket.query.order_by(Ticket.id.desc()).first()
    if last_ticket:
        last_num = int(last_ticket.ticket_number.split("-")[1])
        new_num = last_num + 1
    else:
        new_num = 1000
    return f"TKT-{new_num:06d}"


def build_ticket(
    title: str,
    description: str,
    ticket_type: str,
    priority: str,
    category: str,
    created_by_id: int,
    assigned_to: int | None = None,
    sla_config: dict | None = None,
    now: datetime | None = None,
) -> Ticket:
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


def calculate_sla_deadline(
    priority: str, sla_config: dict | None = None, now: datetime | None = None
) -> datetime:
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


def _client_ip() -> str | None:
    if not has_request_context():
        return None
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def log_audit(
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    ticket_id: int | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    commit: bool = True,
) -> None:
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


def log_ticket_audit(
    ticket: Ticket, action: str, details: dict | None = None, commit: bool = True
) -> None:
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


def apply_automation_rules(
    ticket: Ticket, trigger_type: str, commit: bool = True
) -> None:
    from app.models import AutomationRule

    rules = (
        AutomationRule.query.filter_by(trigger_type=trigger_type, is_active=True)
        .order_by(AutomationRule.priority.desc())
        .all()
    )

    for rule in rules:
        _execute_automation_rule(ticket, rule, commit)


def _execute_automation_rule(ticket: Ticket, rule, commit: bool = True) -> None:
    if rule.action_type == "assign":
        assignee_id = (rule.action_config or {}).get("assign_to")
        if not assignee_id or not User.query.get(assignee_id):
            return
        ticket.assigned_to = assignee_id
        ticket.promote_status_if_new()
        if commit:
            db.session.commit()
    elif rule.action_type == "escalate":
        if ticket.priority in ("high", "critical"):
            ticket.priority = "critical"
            if commit:
                db.session.commit()


def parse_tags(tag_string: str | None) -> list[str]:
    if not tag_string:
        return []
    return [tag.strip() for tag in tag_string.split(",") if tag.strip()]


def get_ticket_metrics() -> dict:
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


def get_agent_performance() -> list[dict]:
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


def calculate_sla_compliance() -> dict:
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


def validate_upload_sniff(filename: str, head: bytes) -> bool:
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

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
    candidates = []
    for obj in db.session.new:
        if isinstance(obj, Ticket) and getattr(obj, "ticket_number", None):
            candidates.append(obj.ticket_number)

    last_ticket = Ticket.query.order_by(Ticket.id.desc()).first()
    if last_ticket and last_ticket.ticket_number:
        candidates.append(last_ticket.ticket_number)

    max_num = 999
    for tn in candidates:
        parts = str(tn).split("-")
        if len(parts) >= 2 and parts[1].isdigit():
            max_num = max(max_num, int(parts[1]))

    new_num = max_num + 1
    ticket_num = f"TKT-{new_num:06d}"

    while Ticket.query.filter_by(ticket_number=ticket_num).first() is not None:
        new_num += 1
        ticket_num = f"TKT-{new_num:06d}"

    return ticket_num


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
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.remote_addr
    return ip[:45] if ip else None


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
        user = User.query.get(assignee_id) if assignee_id else None
        if not user or not user.is_active or not user.is_agent():
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
    status_counts = dict(
        db.session.query(Ticket.status, db.func.count(Ticket.id))
        .group_by(Ticket.status)
        .all()
    )
    total = sum(status_counts.values())
    open_tickets = sum(status_counts.get(s, 0) for s in TICKET_OPEN_STATUSES)
    resolved = status_counts.get("resolved", 0)
    closed = status_counts.get("closed", 0)

    by_status = {s: status_counts.get(s, 0) for s in TICKET_STATUSES}

    priority_counts = dict(
        db.session.query(Ticket.priority, db.func.count(Ticket.id))
        .group_by(Ticket.priority)
        .all()
    )
    by_priority = {p: priority_counts.get(p, 0) for p in TICKET_PRIORITIES}

    category_counts = dict(
        db.session.query(Ticket.category, db.func.count(Ticket.id))
        .group_by(Ticket.category)
        .all()
    )
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
    by_category = {cat: category_counts.get(cat, 0) for cat in categories}

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
    if not agents:
        return []

    agent_ids = [a.id for a in agents]

    assigned_counts = dict(
        db.session.query(Ticket.assigned_to, db.func.count(Ticket.id))
        .filter(Ticket.assigned_to.in_(agent_ids))
        .group_by(Ticket.assigned_to)
        .all()
    )

    resolved_counts = dict(
        db.session.query(Ticket.assigned_to, db.func.count(Ticket.id))
        .filter(Ticket.assigned_to.in_(agent_ids), Ticket.status == "resolved")
        .group_by(Ticket.assigned_to)
        .all()
    )

    resolved_tickets = (
        Ticket.query.filter(
            Ticket.assigned_to.in_(agent_ids),
            Ticket.status == "resolved",
            Ticket.resolved_at.isnot(None),
            Ticket.created_at.isnot(None),
        ).all()
    )

    res_by_agent: dict[int, list[float]] = {}
    for t in resolved_tickets:
        if t.resolution_time is not None:
            res_by_agent.setdefault(t.assigned_to, []).append(t.resolution_time)

    performance = []
    for agent in agents:
        resolution_times = res_by_agent.get(agent.id, [])
        avg_res = (sum(resolution_times) / len(resolution_times)) if resolution_times else 0
        performance.append(
            {
                "agent": agent,
                "assigned": assigned_counts.get(agent.id, 0),
                "resolved": resolved_counts.get(agent.id, 0),
                "avg_resolution_hours": avg_res,
            }
        )

    return performance


def calculate_sla_compliance() -> dict:
    base_q = Ticket.query.filter(
        Ticket.status.in_(TICKET_CLOSED_STATUSES),
        Ticket.resolved_at.isnot(None),
        Ticket.sla_deadline.isnot(None),
    )

    met = base_q.filter(Ticket.resolved_at <= Ticket.sla_deadline).count()
    breached = base_q.filter(Ticket.resolved_at > Ticket.sla_deadline).count()
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

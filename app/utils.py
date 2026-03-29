import re
from datetime import datetime, timedelta
from flask import current_app
from app import db
from app.models import Ticket, AuditLog, User


def generate_ticket_number():
    last_ticket = Ticket.query.order_by(Ticket.id.desc()).first()
    if last_ticket:
        last_num = int(last_ticket.ticket_number.split("-")[1])
        new_num = last_num + 1
    else:
        new_num = 1000
    return f"TKT-{new_num:06d}"


def calculate_sla_deadline(priority):
    sla_config = current_app.config.get("SLA_CONFIG", {})
    if priority in sla_config:
        hours = sla_config[priority]["resolution_hours"]
        return datetime.utcnow() + timedelta(hours=hours)
    return datetime.utcnow() + timedelta(hours=24)


def log_audit(
    user_id,
    action,
    entity_type=None,
    entity_id=None,
    ticket_id=None,
    details=None,
    ip_address=None,
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ticket_id=ticket_id,
        details=details,
        ip_address=ip_address,
    )
    db.session.add(log)
    db.session.commit()


def get_status_color(status):
    colors = {
        "new": "primary",
        "assigned": "info",
        "in_progress": "warning",
        "pending": "secondary",
        "resolved": "success",
        "closed": "dark",
    }
    return colors.get(status, "secondary")


def get_priority_color(priority):
    colors = {
        "low": "success",
        "medium": "warning",
        "high": "danger",
        "critical": "danger",
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
    open_tickets = Ticket.query.filter(
        Ticket.status.in_(["new", "assigned", "in_progress", "pending"])
    ).count()
    resolved = Ticket.query.filter_by(status="resolved").count()
    closed = Ticket.query.filter_by(status="closed").count()

    by_priority = {}
    for priority in ["low", "medium", "high", "critical"]:
        by_priority[priority] = Ticket.query.filter_by(priority=priority).count()

    by_status = {}
    for status in ["new", "assigned", "in_progress", "pending", "resolved", "closed"]:
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

        avg_resolution = (
            db.session.query(
                db.func.avg(
                    db.func.extract("epoch", Ticket.resolved_at - Ticket.created_at)
                    / 3600
                )
            )
            .filter(
                Ticket.assigned_to == agent.id,
                Ticket.status == "resolved",
                Ticket.resolved_at.isnot(None),
            )
            .scalar()
        )

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
        Ticket.status.in_(["resolved", "closed"]), Ticket.resolved_at.isnot(None)
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

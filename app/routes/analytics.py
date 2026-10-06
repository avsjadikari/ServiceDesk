from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from app.models import Ticket, User, AuditLog
from app.utils import (
    get_ticket_metrics,
    get_agent_performance,
    calculate_sla_compliance,
)

analytics = Blueprint("analytics", __name__)


@analytics.route("/analytics")
@login_required
def index():
    if not current_user.is_agent():
        abort(403)

    metrics = get_ticket_metrics()
    performance = get_agent_performance()
    sla = calculate_sla_compliance()

    return render_template(
        "analytics/index.html", metrics=metrics, performance=performance, sla=sla
    )


@analytics.route("/analytics/tickets")
@login_required
def tickets():
    if not current_user.is_agent():
        abort(403)

    days = request.args.get("days", 30, type=int)
    if days <= 0 or days > 365:
        days = 30

    start_date = datetime.utcnow() - timedelta(days=days)
    date_list = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days + 1)]

    created_query = (
        db.session.query(
            func.date(Ticket.created_at).label("d"),
            func.count(Ticket.id).label("cnt"),
        )
        .filter(Ticket.created_at >= start_date)
        .group_by(func.date(Ticket.created_at))
        .all()
    )
    created_map = {str(r.d): r.cnt for r in created_query}

    resolved_query = (
        db.session.query(
            func.date(Ticket.resolved_at).label("d"),
            func.count(Ticket.id).label("cnt"),
        )
        .filter(Ticket.resolved_at >= start_date, Ticket.resolved_at.isnot(None))
        .group_by(func.date(Ticket.resolved_at))
        .all()
    )
    resolved_map = {str(r.d): r.cnt for r in resolved_query}

    return jsonify({
        "labels": date_list,
        "created": [created_map.get(d, 0) for d in date_list],
        "resolved": [resolved_map.get(d, 0) for d in date_list],
        "series": [{"date": d, "count": created_map.get(d, 0), "resolved": resolved_map.get(d, 0)} for d in date_list],
    })


@analytics.route("/analytics/sla")
@login_required
def sla():
    if not current_user.is_agent():
        abort(403)

    sla_data = calculate_sla_compliance()

    resolved_tickets = Ticket.query.filter(Ticket.resolved_at.isnot(None)).all()
    valid_res_times = [t.resolution_time for t in resolved_tickets if t.resolution_time is not None]
    avg_mttr = round(sum(valid_res_times) / len(valid_res_times), 1) if valid_res_times else 0.0
    sla_data["mttr_hours"] = avg_mttr

    active_breached = Ticket.query.filter(
        Ticket.status.in_(["new", "assigned", "in_progress", "pending"]),
        Ticket.sla_deadline.isnot(None),
        Ticket.sla_deadline < datetime.utcnow()
    ).count()
    sla_data["active_breached"] = active_breached

    return jsonify(sla_data)


@analytics.route("/analytics/performance")
@login_required
def performance():
    if not current_user.is_agent():
        abort(403)

    performance_data = get_agent_performance()
    return jsonify(
        [
            {
                "agent": p["agent"].full_name,
                "assigned": p["assigned"],
                "resolved": p["resolved"],
                "avg_resolution": round(p["avg_resolution_hours"], 1),
            }
            for p in performance_data
        ]
    )


@analytics.route("/analytics/categories")
@login_required
def categories():
    if not current_user.is_agent():
        abort(403)

    categories = (
        db.session.query(Ticket.category, func.count(Ticket.id).label("count"))
        .group_by(Ticket.category)
        .all()
    )

    return jsonify(
        [{"category": c.category, "count": c.count} for c in categories if c.category]
    )


@analytics.route("/analytics/audit-logs")
@login_required
def audit_logs():
    if not current_user.is_admin():
        abort(403)

    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template("analytics/audit_logs.html", logs=logs)


def abort(status_code):
    from flask import abort as flask_abort

    flask_abort(status_code)

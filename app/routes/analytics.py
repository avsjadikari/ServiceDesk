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

    start_date = datetime.utcnow() - timedelta(days=days)

    tickets_data = (
        db.session.query(
            func.date(Ticket.created_at).label("date"),
            func.count(Ticket.id).label("count"),
        )
        .filter(Ticket.created_at >= start_date)
        .group_by(func.date(Ticket.created_at))
        .all()
    )

    return jsonify([{"date": str(t.date), "count": t.count} for t in tickets_data])


@analytics.route("/analytics/sla")
@login_required
def sla():
    if not current_user.is_agent():
        abort(403)

    sla_data = calculate_sla_compliance()
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

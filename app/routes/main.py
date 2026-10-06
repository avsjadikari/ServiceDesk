from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy import text
from app import db
from app.models import Ticket, Article, Asset
from app.utils import (
    get_ticket_metrics,
    get_agent_performance,
    calculate_sla_compliance,
)

main = Blueprint("main", __name__)


@main.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@main.route("/ready")
def ready():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ready"}), 200
    except Exception as exc:
        return jsonify({"status": "not-ready", "error": str(exc)}), 503


@main.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.is_agent():
            return redirect(url_for("main.dashboard"))
        return redirect(url_for("portal.home"))
    return redirect(url_for("auth.login"))


@main.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_agent():
        return redirect(url_for("portal.home"))

    metrics = get_ticket_metrics()
    performance = get_agent_performance()
    sla = calculate_sla_compliance()

    recent_tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(10).all()
    open_tickets = (
        Ticket.query.filter(Ticket.status.in_(["new", "assigned", "in_progress"]))
        .order_by(Ticket.sla_deadline.asc())
        .limit(5)
        .all()
    )

    total_articles = Article.query.filter_by(status="published").count()
    total_assets = Asset.query.count()

    # 14-day trend for dashboard
    from datetime import datetime, timedelta
    from sqlalchemy import func

    start_date = datetime.utcnow() - timedelta(days=14)
    trend_dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(15)]

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

    trend_data = {
        "labels": [d[5:] for d in trend_dates],  # MM-DD format
        "created": [created_map.get(d, 0) for d in trend_dates],
        "resolved": [resolved_map.get(d, 0) for d in trend_dates],
    }

    # At-risk SLA count (breached or expiring within 4 hours)
    now = datetime.utcnow()
    sla_at_risk_count = Ticket.query.filter(
        Ticket.status.in_(["new", "assigned", "in_progress", "pending"]),
        Ticket.sla_deadline.isnot(None),
        Ticket.sla_deadline <= now + timedelta(hours=4),
    ).count()

    return render_template(
        "main/dashboard.html",
        metrics=metrics,
        performance=performance,
        sla=sla,
        trend_data=trend_data,
        sla_at_risk_count=sla_at_risk_count,
        recent_tickets=recent_tickets,
        open_tickets=open_tickets,
        total_articles=total_articles,
        total_assets=total_assets,
    )

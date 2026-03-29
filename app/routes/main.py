from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Ticket, Article, Asset
from app.utils import (
    get_ticket_metrics,
    get_agent_performance,
    calculate_sla_compliance,
)

main = Blueprint("main", __name__)


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

    return render_template(
        "main/dashboard.html",
        metrics=metrics,
        performance=performance,
        sla=sla,
        recent_tickets=recent_tickets,
        open_tickets=open_tickets,
        total_articles=total_articles,
        total_assets=total_assets,
    )


@main.route("/my-tickets")
@login_required
def my_tickets():
    if current_user.is_agent():
        tickets = (
            Ticket.query.filter(Ticket.assigned_to == current_user.id)
            .order_by(Ticket.created_at.desc())
            .all()
        )
    else:
        tickets = (
            Ticket.query.filter_by(created_by=current_user.id)
            .order_by(Ticket.created_at.desc())
            .all()
        )

    return render_template("main/my_tickets.html", tickets=tickets)


@main.route("/settings")
@login_required
def settings():
    return render_template("main/settings.html")

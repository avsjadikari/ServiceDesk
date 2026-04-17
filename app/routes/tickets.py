from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import datetime, timezone
from app import db
from app.models import Ticket, Comment, User, Asset
from app.forms import TicketForm, TicketFilterForm, CommentForm
from app.utils import (
    generate_ticket_number,
    calculate_sla_deadline,
    log_audit,
    apply_automation_rules,
    get_status_color,
    get_priority_color,
)

tickets = Blueprint("tickets", __name__)


@tickets.route("/tickets")
@login_required
def index():
    form = TicketFilterForm()
    form.assigned_to.choices = [(0, "All")] + [
        (u.id, u.full_name)
        for u in User.query.filter(User.role.in_(["agent", "admin"])).all()
    ]

    query = Ticket.query

    if current_user.is_agent():
        pass
    else:
        query = query.filter_by(created_by=current_user.id)

    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category")
    assigned_to = request.args.get("assigned_to")

    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)
    if assigned_to:
        query = query.filter_by(assigned_to=int(assigned_to))

    tickets = query.order_by(Ticket.created_at.desc()).all()

    return render_template("tickets/index.html", tickets=tickets, form=form)


@tickets.route("/tickets/new", methods=["GET", "POST"])
@login_required
def new():
    form = TicketForm()
    form.assigned_to.choices = [(0, "Auto-assign")] + [
        (u.id, u.full_name)
        for u in User.query.filter(User.role.in_(["agent", "admin"])).all()
    ]

    if form.validate_on_submit():
        ticket = Ticket(
            ticket_number=generate_ticket_number(),
            title=form.title.data,
            description=form.description.data,
            type=form.type.data,
            priority=form.priority.data,
            category=form.category.data,
            created_by=current_user.id,
            sla_deadline=calculate_sla_deadline(form.priority.data),
        )

        if form.assigned_to.data and int(form.assigned_to.data) > 0:
            ticket.assigned_to = int(form.assigned_to.data)
            ticket.status = "assigned"

        db.session.add(ticket)
        db.session.commit()

        log_audit(current_user.id, "create", "ticket", ticket.id, ticket.id)

        apply_automation_rules(ticket, "ticket_created")

        try:
            from app.email_utils import send_ticket_created

            send_ticket_created(ticket)
        except Exception as e:
            pass

        flash(f"Ticket {ticket.ticket_number} created successfully.", "success")

        if current_user.is_agent():
            return redirect(url_for("tickets.view", ticket_id=ticket.id))
        return redirect(url_for("portal.my_tickets"))

    return render_template("tickets/new.html", form=form)


@tickets.route("/tickets/<int:ticket_id>")
@login_required
def view(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    if not current_user.is_agent() and ticket.created_by != current_user.id:
        abort(403)

    comment_form = CommentForm()
    comments = (
        Comment.query.filter_by(ticket_id=ticket.id)
        .order_by(Comment.created_at.asc())
        .all()
    )

    status_color = get_status_color(ticket.status)
    priority_color = get_priority_color(ticket.priority)

    return render_template(
        "tickets/view.html",
        ticket=ticket,
        comment_form=comment_form,
        comments=comments,
        status_color=status_color,
        priority_color=priority_color,
    )


@tickets.route("/tickets/<int:ticket_id>/edit", methods=["GET", "POST"])
@login_required
def edit(ticket_id):
    if not current_user.is_agent():
        abort(403)

    ticket = Ticket.query.get_or_404(ticket_id)
    form = TicketForm(obj=ticket)
    form.assigned_to.choices = [(0, "Unassigned")] + [
        (u.id, u.full_name)
        for u in User.query.filter(User.role.in_(["agent", "admin"])).all()
    ]

    if form.validate_on_submit():
        ticket.title = form.title.data
        ticket.description = form.description.data
        ticket.type = form.type.data
        ticket.priority = form.priority.data
        ticket.category = form.category.data

        if form.assigned_to.data and int(form.assigned_to.data) > 0:
            ticket.assigned_to = int(form.assigned_to.data)
            if ticket.status == "new":
                ticket.status = "assigned"
        else:
            ticket.assigned_to = None
            ticket.status = "new"

        db.session.commit()

        log_audit(current_user.id, "update", "ticket", ticket.id, ticket.id)

        flash(f"Ticket {ticket.ticket_number} updated successfully.", "success")
        return redirect(url_for("tickets.view", ticket_id=ticket.id))

    return render_template("tickets/edit.html", form=form, ticket=ticket)


@tickets.route("/tickets/<int:ticket_id>/update-status", methods=["POST"])
@login_required
def update_status(ticket_id):
    if not current_user.is_agent():
        abort(403)

    ticket = Ticket.query.get_or_404(ticket_id)
    new_status = request.form.get("status")

    if new_status:
        old_status = ticket.status
        ticket.status = new_status

        if new_status == "in_progress" and not ticket.first_response_at:
            ticket.first_response_at = datetime.now(timezone.utc)

        if new_status == "resolved":
            ticket.resolved_at = datetime.now(timezone.utc)

        if new_status == "closed":
            ticket.closed_at = datetime.now(timezone.utc)

        db.session.commit()

        log_audit(
            current_user.id,
            "status_change",
            "ticket",
            ticket.id,
            ticket.id,
            {"old_status": old_status, "new_status": new_status},
        )

        try:
            from app.email_utils import send_ticket_status_changed

            send_ticket_status_changed(ticket, old_status, new_status)
        except Exception as e:
            pass

        flash(f"Ticket status updated to {new_status}.", "success")

    return redirect(url_for("tickets.view", ticket_id=ticket_id))


@tickets.route("/tickets/<int:ticket_id>/assign", methods=["POST"])
@login_required
def assign(ticket_id):
    if not current_user.is_agent():
        abort(403)

    ticket = Ticket.query.get_or_404(ticket_id)
    assignee_id = request.form.get("assigned_to")

    if assignee_id:
        ticket.assigned_to = int(assignee_id)
        if ticket.status == "new":
            ticket.status = "assigned"
        db.session.commit()

        log_audit(
            current_user.id,
            "assign",
            "ticket",
            ticket.id,
            ticket.id,
            {"assigned_to": assignee_id},
        )

        try:
            from app.email_utils import send_ticket_assigned

            send_ticket_assigned(ticket)
        except Exception as e:
            pass

        flash(
            f"Ticket assigned to {ticket.assignee.full_name if ticket.assignee else 'Unknown'}.",
            "success",
        )

    return redirect(url_for("tickets.view", ticket_id=ticket_id))


@tickets.route("/tickets/<int:ticket_id>/comment", methods=["POST"])
@login_required
def add_comment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    if not current_user.is_agent() and ticket.created_by != current_user.id:
        abort(403)

    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(
            ticket_id=ticket.id,
            user_id=current_user.id,
            content=form.content.data,
            is_internal=form.is_internal.data if current_user.is_agent() else False,
        )
        db.session.add(comment)
        db.session.commit()

        log_audit(current_user.id, "comment", "ticket", ticket.id, ticket.id)

        try:
            from app.email_utils import send_ticket_comment

            send_ticket_comment(ticket, comment)
        except Exception as e:
            pass

        flash("Comment added successfully.", "success")

    return redirect(url_for("tickets.view", ticket_id=ticket_id))


@tickets.route("/tickets/<int:ticket_id>/link-asset", methods=["POST"])
@login_required
def link_asset(ticket_id):
    if not current_user.is_agent():
        abort(403)

    ticket = Ticket.query.get_or_404(ticket_id)
    asset_id = request.form.get("asset_id")

    if asset_id:
        ticket.asset_id = int(asset_id)
        db.session.commit()

        log_audit(
            current_user.id,
            "link_asset",
            "ticket",
            ticket.id,
            ticket.id,
            {"asset_id": asset_id},
        )

        flash("Asset linked successfully.", "success")

    return redirect(url_for("tickets.view", ticket_id=ticket_id))

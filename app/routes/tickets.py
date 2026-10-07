import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app import db
from app.forms import AttachmentForm, CommentForm, TicketFilterForm, TicketForm
from app.models import Attachment, Comment, Ticket, User
from app.utils import (
    apply_automation_rules,
    calculate_sla_deadline,
    generate_ticket_number,
    get_priority_color,
    get_status_color,
    log_audit,
    validate_upload_sniff,
)

tickets = Blueprint("tickets", __name__)


def _agent_users():
    return User.query.filter(User.role.in_(["agent", "admin"])).all()


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _notify(ticket, description, send_fn, *args):
    """A failing email must not fail the request; log and continue."""
    try:
        send_fn(*args)
    except Exception:
        current_app.logger.warning(
            "Email send failed for ticket %s (%s)", ticket.id, description,
            exc_info=True,
        )


@tickets.route("/tickets")
@login_required
def index():
    form = TicketFilterForm()
    form.assigned_to.choices = [(0, "All")] + [
        (u.id, u.full_name) for u in _agent_users()
    ]

    query = Ticket.query

    if not current_user.is_agent():
        query = query.filter_by(created_by=current_user.id)

    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category")
    assigned_to = request.args.get("assigned_to", type=int)

    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)
    if assigned_to:
        query = query.filter_by(assigned_to=assigned_to)

    page = request.args.get("page", 1, type=int)
    tickets = (
        query.order_by(Ticket.created_at.desc())
        .options(joinedload(Ticket.creator), joinedload(Ticket.assignee))
        .paginate(page=page, per_page=25, error_out=False)
    )

    return render_template("tickets/index.html", tickets=tickets, form=form)


@tickets.route("/tickets/board")
@login_required
def board():
    if not current_user.is_agent():
        abort(403)

    tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    columns = {
        "new": [t for t in tickets if t.status == "new"],
        "assigned": [t for t in tickets if t.status == "assigned"],
        "in_progress": [t for t in tickets if t.status == "in_progress"],
        "pending": [t for t in tickets if t.status == "pending"],
        "resolved": [t for t in tickets if t.status == "resolved"],
    }
    return render_template(
        "tickets/board.html",
        columns=columns,
        agents=User.query.filter(User.role.in_(["agent", "admin"])).all(),
    )


@tickets.route("/tickets/new", methods=["GET", "POST"])
@login_required
def new():
    form = TicketForm()
    form.assigned_to.choices = [(0, "Auto-assign")] + [
        (u.id, u.full_name) for u in _agent_users()
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

        from app.email_utils import send_ticket_created

        _notify(ticket, "create", send_ticket_created)

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
        .options(joinedload(Comment.user))
        .order_by(Comment.created_at.asc())
        .all()
    )

    status_color = get_status_color(ticket.status)
    priority_color = get_priority_color(ticket.priority)

    return render_template(
        "tickets/view.html",
        ticket=ticket,
        comment_form=comment_form,
        attachment_form=AttachmentForm(),
        comments=comments,
        attachments=ticket.attachments.order_by(Attachment.created_at.desc()).all(),
        status_color=status_color,
        priority_color=priority_color,
        users=_agent_users(),
    )


@tickets.route("/tickets/<int:ticket_id>/edit", methods=["GET", "POST"])
@login_required
def edit(ticket_id):
    if not current_user.is_agent():
        abort(403)

    ticket = Ticket.query.get_or_404(ticket_id)
    form = TicketForm(obj=ticket)
    form.assigned_to.choices = [(0, "Unassigned")] + [
        (u.id, u.full_name) for u in _agent_users()
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
    new_status = request.json.get("status") if request.is_json else request.form.get("status")

    if not new_status:
        if request.is_json:
            return jsonify({"success": False, "error": "Invalid status"}), 400
        return redirect(url_for("tickets.view", ticket_id=ticket_id))

    old_status = ticket.status
    ticket.status = new_status

    if new_status == "in_progress" and not ticket.first_response_at:
        ticket.first_response_at = datetime.utcnow()

    if new_status == "resolved":
        ticket.resolved_at = datetime.utcnow()

    if new_status == "closed":
        ticket.closed_at = datetime.utcnow()

    db.session.commit()

    log_audit(
        current_user.id,
        "status_change",
        "ticket",
        ticket.id,
        ticket.id,
        {"old_status": old_status, "new_status": new_status},
    )

    from app.email_utils import send_ticket_status_changed

    _notify(ticket, "status change", send_ticket_status_changed, old_status, new_status)

    if request.is_json:
        return jsonify({"success": True, "ticket_id": ticket.id, "status": new_status})

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
        try:
            assignee_id = int(assignee_id)
        except (TypeError, ValueError):
            flash("Invalid assignee.", "danger")
            return redirect(url_for("tickets.view", ticket_id=ticket_id))

        assignee = User.query.get(assignee_id)
        if assignee is None or not assignee.is_active:
            flash("Assignee does not exist.", "danger")
            return redirect(url_for("tickets.view", ticket_id=ticket_id))
        if not assignee.is_agent():
            flash("Assignee must be an agent or admin.", "danger")
            return redirect(url_for("tickets.view", ticket_id=ticket_id))

        ticket.assigned_to = assignee_id
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

        from app.email_utils import send_ticket_assigned

        _notify(ticket, "assignment", send_ticket_assigned)

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

        from app.email_utils import send_ticket_comment

        _notify(ticket, "comment", send_ticket_comment, comment)

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
        asset_id = _to_int(asset_id)
        if asset_id is None:
            flash("Invalid asset.", "danger")
            return redirect(url_for("tickets.view", ticket_id=ticket_id))
        ticket.asset_id = asset_id
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


def _can_view_ticket(ticket):
    """A user can view a ticket if they are the reporter, an agent/admin,
    or the assignee."""
    if not current_user.is_authenticated:
        return False
    if current_user.is_agent():
        return True
    return ticket.created_by == current_user.id


def _attachment_allowed(filename, mime_type):
    """Validate the upload extension and MIME prefix against app config."""
    if not filename:
        return False
    safe_name = secure_filename(filename)
    if not safe_name or "." not in safe_name:
        return False
    ext = safe_name.rsplit(".", 1)[-1].lower()
    allowed_exts = current_app.config.get("UPLOAD_ALLOWED_EXTENSIONS") or set()
    allowed_mimes = current_app.config.get("UPLOAD_ALLOWED_MIME_PREFIXES") or []
    if ext not in allowed_exts:
        return False
    if mime_type and not any(
        mime_type.startswith(prefix) for prefix in allowed_mimes
    ):
        return False
    return True


@tickets.route("/tickets/<int:ticket_id>/attachments", methods=["POST"])
@login_required
def upload_attachment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not _can_view_ticket(ticket):
        abort(403)

    form = AttachmentForm()
    if not form.validate_on_submit():
        for _, errors in form.errors.items():
            for err in errors:
                flash(err, "danger")
        return redirect(url_for("tickets.view", ticket_id=ticket_id))

    f = form.file.data
    if not f or not f.filename:
        flash("No file selected.", "danger")
        return redirect(url_for("tickets.view", ticket_id=ticket_id))

    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH")
    if max_bytes and f.content_length and f.content_length > max_bytes:
        flash("File is too large.", "danger")
        return redirect(url_for("tickets.view", ticket_id=ticket_id))

    if not _attachment_allowed(f.filename, f.mimetype):
        flash("This file type is not allowed.", "danger")
        current_app.logger.warning(
            "Rejected attachment upload user_id=%s ticket_id=%s "
            "filename=%s mime=%s",
            current_user.id,
            ticket.id,
            f.filename,
            f.mimetype,
        )
        return redirect(url_for("tickets.view", ticket_id=ticket_id))

    f.stream.seek(0)
    sniff = f.stream.read(512)
    f.stream.seek(0)
    if not validate_upload_sniff(f.filename, sniff):
        flash("File content does not match its extension.", "danger")
        current_app.logger.warning(
            "Rejected attachment upload (magic-bytes mismatch) "
            "user_id=%s ticket_id=%s filename=%s mime=%s",
            current_user.id,
            ticket.id,
            f.filename,
            f.mimetype,
        )
        return redirect(url_for("tickets.view", ticket_id=ticket_id))

    safe_name = secure_filename(f.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    if not _store_attachment(ticket, f, safe_name, unique_name):
        flash("Invalid filename.", "danger")
        return redirect(url_for("tickets.view", ticket_id=ticket_id))

    flash("File uploaded successfully.", "success")
    return redirect(url_for("tickets.view", ticket_id=ticket_id))


def _store_attachment(ticket, upload, safe_name, unique_name):
    upload_dir = current_app.config.get("UPLOAD_FOLDER")
    os.makedirs(upload_dir, exist_ok=True)
    dest_path = os.path.join(upload_dir, unique_name)
    # Make sure the resolved path stays inside the upload directory.
    real_dir = os.path.realpath(upload_dir)
    real_path = os.path.realpath(dest_path)
    if not real_path.startswith(real_dir + os.sep):
        return False

    upload.save(dest_path)
    file_size = os.path.getsize(dest_path)

    attachment = Attachment(
        ticket_id=ticket.id,
        filename=safe_name,
        filepath=unique_name,
        file_size=file_size,
        mime_type=upload.mimetype,
        uploaded_by=current_user.id,
    )
    db.session.add(attachment)
    db.session.commit()

    log_audit(
        current_user.id,
        "upload_attachment",
        "ticket",
        ticket.id,
        ticket.id,
        {"filename": safe_name, "size": file_size},
    )
    return True


@tickets.route("/attachments/<int:attachment_id>")
@login_required
def download_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    ticket = attachment.ticket
    if not _can_view_ticket(ticket):
        abort(403)

    upload_dir = current_app.config.get("UPLOAD_FOLDER")
    real_dir = os.path.realpath(upload_dir)
    file_path = os.path.realpath(os.path.join(upload_dir, attachment.filepath))
    if not file_path.startswith(real_dir + os.sep):
        current_app.logger.error(
            "Attachment path traversal blocked: %s", attachment.filepath
        )
        abort(404)
    if not os.path.isfile(file_path):
        abort(404)

    log_audit(
        current_user.id,
        "download_attachment",
        "ticket",
        ticket.id,
        ticket.id,
        {"filename": attachment.filename},
    )
    return send_file(
        file_path,
        as_attachment=True,
        download_name=attachment.filename,
        mimetype=attachment.mime_type or "application/octet-stream",
    )

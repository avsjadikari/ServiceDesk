from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db, limiter
from app.enums import (
    TICKET_PRIORITIES,
    TICKET_STATUSES,
    TICKET_TYPES,
)
from app.models import Ticket, Article, Asset, User
from app.utils import (
    build_ticket,
    get_ticket_metrics,
    calculate_sla_compliance,
    log_audit,
)

VALID_TICKET_TYPES = set(TICKET_TYPES)
VALID_TICKET_STATUSES = set(TICKET_STATUSES)
VALID_TICKET_PRIORITIES = set(TICKET_PRIORITIES)

api = Blueprint("api", __name__)


def require_agent(f):
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_agent():
            return jsonify({"error": "Unauthorized"}), 403
        return f(*args, **kwargs)

    return decorated_function


@api.route("/tickets", methods=["GET"])
@login_required
@require_agent
def get_tickets():
    tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "title": t.title,
                "type": t.type,
                "status": t.status,
                "priority": t.priority,
                "category": t.category,
                "created_at": t.created_at.isoformat(),
                "assigned_to": t.assignee.full_name if t.assignee else None,
            }
            for t in tickets
        ]
    )


@api.route("/tickets", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def create_ticket():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400
    if len(title) > 200:
        return jsonify({"error": "Title must be 200 characters or fewer"}), 400

    ticket_type = data.get("type", "incident")
    if ticket_type not in VALID_TICKET_TYPES:
        return jsonify({"error": f"Invalid type. Must be one of: {', '.join(sorted(VALID_TICKET_TYPES))}"}), 400

    priority = data.get("priority", "medium")
    if priority not in VALID_TICKET_PRIORITIES:
        return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(sorted(VALID_TICKET_PRIORITIES))}"}), 400

    ticket = build_ticket(
        title=title,
        description=(data.get("description") or "").strip(),
        ticket_type=ticket_type,
        priority=priority,
        category=(data.get("category") or "").strip() or None,
        created_by_id=current_user.id,
    )

    db.session.add(ticket)
    db.session.commit()

    return jsonify(
        {
            "id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "message": "Ticket created successfully",
        }
    ), 201


@api.route("/tickets/<int:ticket_id>", methods=["GET"])
@login_required
def get_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    if not current_user.is_agent() and ticket.created_by != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify(
        {
            "id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "title": ticket.title,
            "description": ticket.description,
            "type": ticket.type,
            "status": ticket.status,
            "priority": ticket.priority,
            "category": ticket.category,
            "created_at": ticket.created_at.isoformat(),
            "sla_deadline": ticket.sla_deadline.isoformat()
            if ticket.sla_deadline
            else None,
            "assigned_to": ticket.assignee.full_name if ticket.assignee else None,
            "created_by": ticket.creator.full_name if ticket.creator else None,
            "is_sla_breached": ticket.is_sla_breached,
        }
    )


@api.route("/tickets/<int:ticket_id>", methods=["PUT"])
@login_required
@require_agent
@limiter.limit("30 per hour")
def update_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            return jsonify({"error": "Title cannot be empty"}), 400
        if len(title) > 200:
            return jsonify({"error": "Title must be 200 characters or fewer"}), 400
        ticket.title = title
    if "description" in data:
        ticket.description = (data["description"] or "").strip()
    if "status" in data:
        status = data["status"]
        if status not in VALID_TICKET_STATUSES:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(sorted(VALID_TICKET_STATUSES))}"}), 400
        ticket.status = status
    if "priority" in data:
        priority = data["priority"]
        if priority not in VALID_TICKET_PRIORITIES:
            return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(sorted(VALID_TICKET_PRIORITIES))}"}), 400
        ticket.priority = priority
    if "category" in data:
        ticket.category = (data["category"] or "").strip() or None
    if "assigned_to" in data:
        assignee_id = data["assigned_to"]
        if assignee_id is None:
            ticket.assigned_to = None
        else:
            try:
                assignee_id = int(assignee_id)
            except (TypeError, ValueError):
                return jsonify({"error": "assigned_to must be a user id"}), 400
            assignee = User.query.get(assignee_id)
            if assignee is None or not assignee.is_active:
                return jsonify({"error": "Assignee does not exist"}), 400
            if not assignee.is_agent():
                return jsonify(
                    {"error": "Assignee must be an agent or admin"}
                ), 400
            ticket.assigned_to = assignee_id

    db.session.commit()

    return jsonify({"message": "Ticket updated successfully"})


@api.route("/tickets/<int:ticket_id>", methods=["DELETE"])
@login_required
@require_agent
@limiter.limit("30 per hour")
def delete_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket_number = ticket.ticket_number
    log_audit(
        current_user.id,
        "delete_ticket",
        "ticket",
        ticket.id,
        details={"ticket_number": ticket_number},
    )
    db.session.delete(ticket)
    db.session.commit()

    return jsonify({"message": "Ticket deleted successfully"})


@api.route("/articles", methods=["GET"])
@login_required
def get_articles():
    query = Article.query.filter_by(status="published")

    search = request.args.get("search")
    if search:
        query = query.filter(
            db.or_(
                Article.title.ilike(f"%{search}%"), Article.content.ilike(f"%{search}%")
            )
        )

    articles = query.order_by(Article.updated_at.desc()).all()

    return jsonify(
        [
            {
                "id": a.id,
                "title": a.title,
                "category": a.category,
                "tags": a.tags,
                "view_count": a.view_count,
                "updated_at": a.updated_at.isoformat(),
            }
            for a in articles
        ]
    )


@api.route("/articles/<int:article_id>", methods=["GET"])
@login_required
def get_article(article_id):
    article = (
        Article.query.filter(
            Article.id == article_id, Article.status == "published"
        ).first_or_404()
    )

    return jsonify(
        {
            "id": article.id,
            "title": article.title,
            "content": article.content,
            "category": article.category,
            "tags": article.tags,
            "author": article.author.full_name,
            "view_count": article.view_count,
            "created_at": article.created_at.isoformat(),
            "updated_at": article.updated_at.isoformat(),
        }
    )


@api.route("/assets", methods=["GET"])
@login_required
@require_agent
def get_assets():
    assets = Asset.query.order_by(Asset.name.asc()).all()

    return jsonify(
        [
            {
                "id": a.id,
                "name": a.name,
                "asset_type": a.asset_type,
                "serial_number": a.serial_number,
                "status": a.status,
                "assigned_to": a.owner.full_name if a.owner else None,
                "location": a.location,
            }
            for a in assets
        ]
    )


@api.route("/assets/<int:asset_id>", methods=["GET"])
@login_required
def get_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)

    if not current_user.is_agent() and asset.assigned_to != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify(
        {
            "id": asset.id,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "serial_number": asset.serial_number,
            "model": asset.model,
            "manufacturer": asset.manufacturer,
            "status": asset.status,
            "assigned_to": asset.owner.full_name if asset.owner else None,
            "location": asset.location,
            "purchase_date": asset.purchase_date.isoformat()
            if asset.purchase_date
            else None,
            "warranty_expiry": asset.warranty_expiry.isoformat()
            if asset.warranty_expiry
            else None,
        }
    )


@api.route("/analytics/dashboard", methods=["GET"])
@login_required
@require_agent
def dashboard():
    metrics = get_ticket_metrics()
    sla = calculate_sla_compliance()

    return jsonify({"metrics": metrics, "sla": sla})


@api.route("/users", methods=["GET"])
@login_required
@require_agent
def get_users():
    users = User.query.all()
    return jsonify(
        [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "department": u.department,
            }
            for u in users
        ]
    )

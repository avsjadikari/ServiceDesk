from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models import Ticket, Article, Asset, User
from app.utils import (
    get_ticket_metrics,
    calculate_sla_compliance,
    get_status_color,
    get_priority_color,
)

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
def create_ticket():
    from app.utils import generate_ticket_number, calculate_sla_deadline

    data = request.get_json()

    ticket = Ticket(
        ticket_number=generate_ticket_number(),
        title=data.get("title"),
        description=data.get("description"),
        type=data.get("type", "incident"),
        priority=data.get("priority", "medium"),
        category=data.get("category"),
        created_by=current_user.id,
        sla_deadline=calculate_sla_deadline(data.get("priority", "medium")),
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
def update_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    data = request.get_json()

    if "title" in data:
        ticket.title = data["title"]
    if "description" in data:
        ticket.description = data["description"]
    if "status" in data:
        ticket.status = data["status"]
    if "priority" in data:
        ticket.priority = data["priority"]
    if "category" in data:
        ticket.category = data["category"]
    if "assigned_to" in data:
        ticket.assigned_to = data["assigned_to"]

    db.session.commit()

    return jsonify({"message": "Ticket updated successfully"})


@api.route("/tickets/<int:ticket_id>", methods=["DELETE"])
@login_required
@require_agent
def delete_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    db.session.delete(ticket)
    db.session.commit()

    return jsonify({"message": "Ticket deleted successfully"})


@api.route("/articles", methods=["GET"])
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
def get_article(article_id):
    article = Article.query.get_or_404(article_id)

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

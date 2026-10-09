from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Ticket, Article, Comment
from app.forms import TicketForm, CommentForm
from app.utils import build_ticket

portal = Blueprint("portal", __name__)


@portal.route("/portal")
@portal.route("/portal/home")
def home():
    if current_user.is_authenticated and current_user.is_agent():
        return redirect(url_for("main.dashboard"))

    recent_articles = (
        Article.query.filter_by(status="published")
        .order_by(Article.view_count.desc())
        .limit(5)
        .all()
    )

    return render_template("portal/home.html", recent_articles=recent_articles)


@portal.route("/portal/knowledge")
def knowledge():
    search = request.args.get("search")
    category = request.args.get("category")

    query = Article.query.filter_by(status="published")

    if search:
        query = query.filter(
            db.or_(
                Article.title.ilike(f"%{search}%"), Article.content.ilike(f"%{search}%")
            )
        )

    if category:
        query = query.filter_by(category=category)

    page = request.args.get("page", 1, type=int)
    articles = (
        query.order_by(Article.updated_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )

    return render_template("portal/knowledge.html", articles=articles)


@portal.route("/portal/knowledge/<int:article_id>")
def knowledge_view(article_id):
    article = (
        Article.query.filter(
            Article.id == article_id, Article.status == "published"
        ).first_or_404()
    )
    article.view_count += 1
    db.session.commit()

    return render_template("portal/knowledge_view.html", article=article)


@portal.route("/portal/tickets")
@login_required
def my_tickets():
    page = request.args.get("page", 1, type=int)
    tickets = (
        Ticket.query.filter_by(created_by=current_user.id)
        .order_by(Ticket.created_at.desc())
        .paginate(page=page, per_page=25, error_out=False)
    )
    return render_template("portal/my_tickets.html", tickets=tickets)


@portal.route("/portal/tickets/new", methods=["GET", "POST"])
@login_required
def new_ticket():
    form = TicketForm()
    form.assigned_to.choices = [(0, "")]

    if form.validate_on_submit():
        ticket = build_ticket(
            title=form.title.data,
            description=form.description.data,
            ticket_type=form.type.data,
            priority=form.priority.data,
            category=form.category.data,
            created_by_id=current_user.id,
        )

        db.session.add(ticket)
        db.session.commit()

        from app.email_utils import send_ticket_created

        send_ticket_created(ticket)

        flash(
            f"Ticket {ticket.ticket_number} submitted — you're all set."
            + (
                f" Expected Resolution: {ticket.sla_deadline:%m/%d/%Y %H:%M}."
                if ticket.sla_deadline
                else " We'll pick it up from here."
            ),
            "success",
        )
        return redirect(url_for("portal.my_tickets"))

    return render_template("portal/new_ticket.html", form=form)


@portal.route("/portal/tickets/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def view_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    if ticket.created_by != current_user.id:
        from flask import abort

        abort(403)

    comment_form = CommentForm()

    if comment_form.validate_on_submit():
        comment = Comment(
            ticket_id=ticket.id,
            user_id=current_user.id,
            content=comment_form.content.data,
            is_internal=False,
        )
        db.session.add(comment)
        db.session.commit()

        flash("Your comment has been added.", "success")
        return redirect(url_for("portal.view_ticket", ticket_id=ticket_id))

    comments = (
        Comment.query.filter_by(ticket_id=ticket.id, is_internal=False)
        .order_by(Comment.created_at.asc())
        .all()
    )

    from app.enums import STATUS_GLOSS

    return render_template(
        "portal/view_ticket.html",
        ticket=ticket,
        comment_form=comment_form,
        comments=comments,
        status_gloss=STATUS_GLOSS.get(ticket.status),
    )

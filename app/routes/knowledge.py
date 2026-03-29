from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Article, ArticleVersion
from app.forms import ArticleForm, ArticleSearchForm
from app.utils import parse_tags

knowledge = Blueprint("knowledge", __name__)


@knowledge.route("/knowledge")
def index():
    form = ArticleSearchForm()

    query = Article.query.filter_by(status="published")

    search = request.args.get("search")
    category = request.args.get("category")

    if search:
        query = query.filter(
            db.or_(
                Article.title.ilike(f"%{search}%"), Article.content.ilike(f"%{search}%")
            )
        )

    if category:
        query = query.filter_by(category=category)

    articles = query.order_by(Article.updated_at.desc()).all()

    return render_template("knowledge/index.html", articles=articles, form=form)


@knowledge.route("/knowledge/<int:article_id>")
def view(article_id):
    article = Article.query.get_or_404(article_id)
    article.view_count += 1
    db.session.commit()

    related = (
        Article.query.filter(
            Article.id != article.id,
            Article.status == "published",
            Article.category == article.category,
        )
        .limit(5)
        .all()
    )

    return render_template("knowledge/view.html", article=article, related=related)


@knowledge.route("/knowledge/new", methods=["GET", "POST"])
@login_required
def new():
    if not current_user.is_agent():
        abort(403)

    form = ArticleForm()

    if form.validate_on_submit():
        article = Article(
            title=form.title.data,
            content=form.content.data,
            category=form.category.data,
            tags=parse_tags(form.tags.data),
            author_id=current_user.id,
            status=form.status.data,
        )
        db.session.add(article)
        db.session.commit()

        version = ArticleVersion(
            article_id=article.id,
            version=1,
            content=article.content,
            created_by=current_user.id,
        )
        db.session.add(version)
        db.session.commit()

        flash(f'Article "{article.title}" created successfully.', "success")

        if current_user.is_agent():
            return redirect(url_for("knowledge.view", article_id=article.id))
        return redirect(url_for("knowledge.index"))

    return render_template("knowledge/new.html", form=form)


@knowledge.route("/knowledge/<int:article_id>/edit", methods=["GET", "POST"])
@login_required
def edit(article_id):
    if not current_user.is_agent():
        abort(403)

    article = Article.query.get_or_404(article_id)
    form = ArticleForm(obj=article)

    if form.validate_on_submit():
        old_content = article.content

        article.title = form.title.data
        article.content = form.content.data
        article.category = form.category.data
        article.tags = parse_tags(form.tags.data)
        article.status = form.status.data
        article.version += 1

        version = ArticleVersion(
            article_id=article.id,
            version=article.version,
            content=old_content,
            created_by=current_user.id,
        )
        db.session.add(version)

        db.session.commit()

        flash(f'Article "{article.title}" updated successfully.', "success")
        return redirect(url_for("knowledge.view", article_id=article.id))

    return render_template("knowledge/edit.html", form=form, article=article)


@knowledge.route("/knowledge/<int:article_id>/versions")
@login_required
def versions(article_id):
    if not current_user.is_agent():
        abort(403)

    article = Article.query.get_or_404(article_id)
    versions = (
        ArticleVersion.query.filter_by(article_id=article.id)
        .order_by(ArticleVersion.version.desc())
        .all()
    )

    return render_template(
        "knowledge/versions.html", article=article, versions=versions
    )


@knowledge.route("/knowledge/<int:article_id>/helpful", methods=["POST"])
@login_required
def helpful(article_id):
    article = Article.query.get_or_404(article_id)
    article.helpful_count += 1
    db.session.commit()
    flash("Thank you for your feedback!", "success")
    return redirect(url_for("knowledge.view", article_id=article_id))


@knowledge.route("/knowledge/<int:article_id>/delete", methods=["POST"])
@login_required
def delete(article_id):
    if not current_user.is_agent():
        abort(403)

    article = Article.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()

    flash("Article deleted successfully.", "success")
    return redirect(url_for("knowledge.index"))

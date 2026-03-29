from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Asset, User
from app.forms import AssetForm

assets = Blueprint("assets", __name__)


@assets.route("/assets")
@login_required
def index():
    if not current_user.is_agent():
        abort(403)

    status = request.args.get("status")
    asset_type = request.args.get("type")

    query = Asset.query

    if status:
        query = query.filter_by(status=status)
    if asset_type:
        query = query.filter_by(asset_type=asset_type)

    assets_list = query.order_by(Asset.name.asc()).all()

    return render_template("assets/index.html", assets=assets_list)


@assets.route("/assets/<int:asset_id>")
@login_required
def view(asset_id):
    asset = Asset.query.get_or_404(asset_id)

    if not current_user.is_agent() and asset.assigned_to != current_user.id:
        abort(403)

    return render_template("assets/view.html", asset=asset)


@assets.route("/assets/new", methods=["GET", "POST"])
@login_required
def new():
    if not current_user.is_agent():
        abort(403)

    form = AssetForm()
    form.assigned_to.choices = [(0, "Unassigned")] + [
        (u.id, u.full_name) for u in User.query.all()
    ]

    if form.validate_on_submit():
        asset = Asset(
            name=form.name.data,
            asset_type=form.asset_type.data,
            serial_number=form.serial_number.data,
            model=form.model.data,
            manufacturer=form.manufacturer.data,
            location=form.location.data,
            status=form.status.data,
            purchase_date=form.purchase_date.data,
            warranty_expiry=form.warranty_expiry.data,
            notes=form.notes.data,
        )

        if form.assigned_to.data and int(form.assigned_to.data) > 0:
            asset.assigned_to = int(form.assigned_to.data)

        db.session.add(asset)
        db.session.commit()

        flash(f'Asset "{asset.name}" created successfully.', "success")
        return redirect(url_for("assets.view", asset_id=asset.id))

    return render_template("assets/new.html", form=form)


@assets.route("/assets/<int:asset_id>/edit", methods=["GET", "POST"])
@login_required
def edit(asset_id):
    if not current_user.is_agent():
        abort(403)

    asset = Asset.query.get_or_404(asset_id)
    form = AssetForm(obj=asset)
    form.assigned_to.choices = [(0, "Unassigned")] + [
        (u.id, u.full_name) for u in User.query.all()
    ]

    if form.validate_on_submit():
        asset.name = form.name.data
        asset.asset_type = form.asset_type.data
        asset.serial_number = form.serial_number.data
        asset.model = form.model.data
        asset.manufacturer = form.manufacturer.data
        asset.location = form.location.data
        asset.status = form.status.data
        asset.purchase_date = form.purchase_date.data
        asset.warranty_expiry = form.warranty_expiry.data
        asset.notes = form.notes.data

        if form.assigned_to.data and int(form.assigned_to.data) > 0:
            asset.assigned_to = int(form.assigned_to.data)
        else:
            asset.assigned_to = None

        db.session.commit()

        flash(f'Asset "{asset.name}" updated successfully.', "success")
        return redirect(url_for("assets.view", asset_id=asset.id))

    return render_template("assets/edit.html", form=form, asset=asset)


@assets.route("/assets/<int:asset_id>/delete", methods=["POST"])
@login_required
def delete(asset_id):
    if not current_user.is_admin():
        abort(403)

    asset = Asset.query.get_or_404(asset_id)
    db.session.delete(asset)
    db.session.commit()

    flash("Asset deleted successfully.", "success")
    return redirect(url_for("assets.index"))


@assets.route("/assets/<int:asset_id>/assign", methods=["POST"])
@login_required
def assign(asset_id):
    if not current_user.is_agent():
        abort(403)

    asset = Asset.query.get_or_404(asset_id)
    user_id = request.form.get("user_id")

    if user_id:
        asset.assigned_to = int(user_id)
        db.session.commit()

        flash(f"Asset assigned successfully.", "success")

    return redirect(url_for("assets.view", asset_id=asset_id))

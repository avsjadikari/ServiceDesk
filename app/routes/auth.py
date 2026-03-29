from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import text
from app import db, limiter
from app.models import User
from app.forms import LoginForm, RegistrationForm, UserEditForm, ChangePasswordForm
from app.utils import log_audit

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    db.session.rollback()

    if current_user.is_authenticated:
        if current_user.must_change_password:
            return redirect(url_for("auth.change_password"))
        if current_user.is_agent():
            return redirect(url_for("main.dashboard"))
        return redirect(url_for("portal.home"))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data):
                if user.two_factor_enabled:
                    session["pre_2fa_user_id"] = user.id
                    session["remember_me"] = form.remember_me.data
                    return redirect(url_for("auth.login_2fa"))
                else:
                    return complete_login(user, form.remember_me.data)
            else:
                flash("Invalid username or password", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"Login error. Please try again.", "danger")
    return render_template("auth/login.html", form=form)


def complete_login(user, remember_me=False):
    login_user(user, remember=remember_me)
    log_audit(user.id, "login", "user", user.id)

    if user.must_change_password:
        flash("You must change your password on first login.", "warning")
        return redirect(url_for("auth.change_password"))

    next_page = request.args.get("next")
    if not next_page:
        if user.is_agent():
            next_page = url_for("main.dashboard")
        else:
            next_page = url_for("portal.home")
    return redirect(next_page)


@auth.route("/login-2fa", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login_2fa():
    user_id = session.get("pre_2fa_user_id")
    if not user_id:
        flash("Session expired. Please login again.", "warning")
        return redirect(url_for("auth.login"))

    user = User.query.get(user_id)
    if not user:
        flash("User not found. Please login again.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if user.verify_totp(code):
            remember_me = session.get("remember_me", False)
            session.pop("pre_2fa_user_id", None)
            session.pop("remember_me", None)
            return complete_login(user, remember_me)
        else:
            flash("Invalid verification code. Please try again.", "danger")

    return render_template("auth/login_2fa.html", user=user)


@auth.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()

    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
            return render_template("auth/change_password.html", form=form)

        if form.new_password.data == form.current_password.data:
            flash("New password must be different from current password.", "danger")
            return render_template("auth/change_password.html", form=form)

        current_user.set_password(form.new_password.data)
        current_user.must_change_password = False
        db.session.commit()

        log_audit(current_user.id, "password_change", "user", current_user.id)

        flash("Password changed successfully!", "success")

        if current_user.is_agent():
            return redirect(url_for("main.dashboard"))
        return redirect(url_for("portal.home"))

    return render_template("auth/change_password.html", form=form)


@auth.route("/logout")
@login_required
def logout():
    log_audit(current_user.id, "logout", "user", current_user.id)
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            department=form.department.data,
            phone=form.phone.data,
            role="user",
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        log_audit(user.id, "register", "user", user.id)

        flash("Registration successful! You can now login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth.route("/users/new", methods=["GET", "POST"])
@login_required
def create_user():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    from app.forms import RegistrationForm

    form = RegistrationForm()

    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            department=form.department.data,
            phone=form.phone.data,
            role="user",
            must_change_password=True,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        log_audit(current_user.id, "create_user", "user", user.id)

        flash(f"User {user.username} created successfully!", "success")
        return redirect(url_for("auth.users"))

    return render_template("auth/register.html", form=form, admin_create=True)


@auth.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.full_name = request.form.get("full_name")
        current_user.email = request.form.get("email")
        current_user.department = request.form.get("department")
        current_user.phone = request.form.get("phone")
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html")


@auth.route("/users")
@login_required
def users():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    all_users = User.query.all()
    return render_template("auth/users.html", users=all_users)


@auth.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    user = User.query.get_or_404(user_id)
    form = UserEditForm(obj=user)

    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.full_name = form.full_name.data
        user.department = form.department.data
        user.phone = form.phone.data
        user.role = form.role.data
        user.is_active = form.is_active.data
        db.session.commit()

        log_audit(current_user.id, "update_user", "user", user.id)

        flash(f"User {user.username} updated successfully.", "success")
        return redirect(url_for("auth.users"))

    return render_template("auth/edit_user.html", form=form, user=user)


@auth.route("/profile/2fa/setup", methods=["GET", "POST"])
@login_required
def setup_2fa():
    import pyotp
    import qrcode
    import io
    import base64

    if request.method == "POST":
        code = request.form.get("code", "").strip()

        if not current_user.two_factor_secret:
            current_user.two_factor_secret = pyotp.random_base32()
            db.session.commit()

        if current_user.verify_totp(code):
            current_user.two_factor_enabled = True
            db.session.commit()

            from app.email_utils import send_2fa_enabled

            try:
                send_2fa_enabled(current_user)
            except:
                pass

            log_audit(current_user.id, "2fa_enabled", "user", current_user.id)
            flash("Two-factor authentication enabled successfully!", "success")
            return redirect(url_for("auth.profile"))
        else:
            flash("Invalid verification code. Please try again.", "danger")

    if not current_user.two_factor_secret:
        current_user.two_factor_secret = pyotp.random_base32()
        db.session.commit()

    totp_uri = current_user.get_totp_uri()

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_code = base64.b64encode(buffer.getvalue()).decode()

    return render_template(
        "auth/setup_2fa.html", qr_code=qr_code, secret=current_user.two_factor_secret
    )


@auth.route("/profile/2fa/disable", methods=["POST"])
@login_required
def disable_2fa():
    password = request.form.get("password", "").strip()

    if not current_user.check_password(password):
        flash("Incorrect password. Cannot disable 2FA.", "danger")
        return redirect(url_for("auth.profile"))

    current_user.two_factor_enabled = False
    db.session.commit()

    from app.email_utils import send_2fa_disabled

    try:
        send_2fa_disabled(current_user)
    except:
        pass

    log_audit(current_user.id, "2fa_disabled", "user", current_user.id)
    flash("Two-factor authentication disabled.", "success")
    return redirect(url_for("auth.profile"))

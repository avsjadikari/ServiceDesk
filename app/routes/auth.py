from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app import db, limiter
from app.forms import (
    AdminResetPasswordForm,
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    RegistrationForm,
    ResetPasswordForm,
    UserEditForm,
)
from app.models import User
from app.security import generate_password_reset_token, verify_password_reset_token
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
        except Exception:
            current_app.logger.exception("DB error during login lookup")
            db.session.rollback()
            flash("Login temporarily unavailable. Please try again.", "danger")
            return render_template("auth/login.html", form=form)

        if user and user.is_locked():
            current_app.logger.info(
                "Login attempt for locked account user_id=%s until=%s",
                user.id,
                user.locked_until,
            )
            flash(
                "Account is temporarily locked due to repeated failed login "
                "attempts. Please try again later or reset your password.",
                "danger",
            )
            return render_template("auth/login.html", form=form)

        password_ok = bool(user and user.check_password(form.password.data))

        if password_ok and user and user.is_active:
            user.reset_failed_logins()
            db.session.commit()

            if user.two_factor_enabled:
                session["pre_2fa_user_id"] = user.id
                session["remember_me"] = form.remember_me.data
                return redirect(url_for("auth.login_2fa"))
            return complete_login(user, form.remember_me.data)

        if user:
            locked_now = user.record_failed_login(
                max_attempts=current_app.config["LOGIN_MAX_ATTEMPTS"],
                lockout_minutes=current_app.config["LOGIN_LOCKOUT_MINUTES"],
            )
            db.session.commit()
            if locked_now:
                log_audit(
                    user.id, "account_locked", "user", user.id,
                    details={"until": user.locked_until.isoformat()},
                )
                try:
                    from app.email_utils import send_account_locked

                    send_account_locked(user, user.locked_until)
                except Exception:
                    current_app.logger.exception("send_account_locked failed")
                flash(
                    "Too many failed login attempts. Your account has been "
                    "temporarily locked.",
                    "danger",
                )
                return render_template("auth/login.html", form=form)

        flash("Invalid username or password", "danger")
    return render_template("auth/login.html", form=form)


def complete_login(user, remember_me=False):
    """Finalise a successful login: clear the session to prevent fixation,
    log the user in, audit, and route to the right landing page."""
    session.clear()
    login_user(user, remember=remember_me)
    log_audit(user.id, "login", "user", user.id)

    if user.must_change_password:
        flash("You must change your password on first login.", "warning")
        return redirect(url_for("auth.change_password"))

    next_page = request.args.get("next")
    if next_page and not next_page.startswith("/"):
        next_page = None
    if not next_page:
        next_page = (
            url_for("main.dashboard")
            if user.is_agent()
            else url_for("portal.home")
        )
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
        flash("Invalid verification code. Please try again.", "danger")

    return render_template("auth/login_2fa.html", user=user)


@auth.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = ForgotPasswordForm()
    submitted = False
    if form.validate_on_submit():
        submitted = True
        try:
            user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        except Exception:
            current_app.logger.exception("forgot_password: DB error")
            user = None

        if user and user.is_active:
            token = generate_password_reset_token(user.id)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            try:
                from app.email_utils import send_password_reset

                if not send_password_reset(user, reset_url):
                    current_app.logger.warning(
                        "Password reset email not sent (mail disabled?) user_id=%s",
                        user.id,
                    )
            except Exception:
                current_app.logger.exception(
                    "send_password_reset failed user_id=%s", user.id
                )

            # Always log the URL so support staff can deliver it manually
            # when mail is not configured. Use a dedicated event name so it
            # is greppable.
            current_app.logger.info(
                "forgot_password reset_url user_id=%s username=%s url=%s",
                user.id,
                user.username,
                reset_url,
            )

        # Always respond the same to prevent user enumeration.
    if submitted:
        flash(
            "If an account exists for that email, a password reset link has "
            "been sent. Please check your inbox.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def reset_password(token):
    user_id = verify_password_reset_token(token)
    if not user_id:
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.get(user_id)
    if not user or not user.is_active:
        flash("This password reset link is no longer valid.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        if form.new_password.data == user.password_hash:
            flash("New password must be different from your current password.",
                  "danger")
            return render_template("auth/reset_password.html", form=form, token=token)

        user.set_password(form.new_password.data)
        user.must_change_password = False
        user.reset_failed_logins()
        user.last_password_reset_at = datetime.utcnow()
        db.session.commit()
        log_audit(user.id, "password_reset", "user", user.id)
        flash("Your password has been reset. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)


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
        current_user.last_password_reset_at = datetime.utcnow()
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
    form = UserEditForm(obj=user, editing_user_id=user.id)

    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.full_name = form.full_name.data
        user.department = form.department.data
        user.phone = form.phone.data
        user.role = form.role.data
        user.is_active = form.is_active.data
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception("edit_user commit failed user_id=%s", user.id)
            flash(
                "Could not save changes. The username or email may already be in "
                "use by another account. Please try a different value.",
                "danger",
            )
            return render_template("auth/edit_user.html", form=form, user=user)

        log_audit(current_user.id, "update_user", "user", user.id)

        flash(f"User {user.username} updated successfully.", "success")
        return redirect(url_for("auth.users"))

    return render_template("auth/edit_user.html", form=form, user=user)


@auth.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per hour")
def admin_reset_password(user_id):
    """Allow an admin to set a new password for another user.

    The new password is generated server-side (never typed by the admin) and
    is sent to the user over email. The user is forced to change it on next
    login unless the admin explicitly clears the checkbox.
    """
    import secrets as _secrets

    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash("Use the profile page to change your own password.", "warning")
        return redirect(url_for("auth.edit_user", user_id=target.id))

    form = AdminResetPasswordForm()
    if form.validate_on_submit():
        new_password = _secrets.token_urlsafe(16)
        target.set_password(new_password)
        target.must_change_password = form.must_change_password.data
        target.reset_failed_logins()
        target.last_password_reset_at = datetime.utcnow()
        db.session.commit()

        log_audit(
            current_user.id,
            "admin_password_reset",
            "user",
            target.id,
            details={
                "target_username": target.username,
                "must_change": target.must_change_password,
            },
        )

        # Try to email the new password; if email is not configured or the
        # send fails, we still need to make sure the admin can deliver it
        # to the user. Always log the password (info level) and expose it
        # on the success page so it can be communicated out-of-band.
        email_sent = False
        try:
            from app.email_utils import send_admin_password_reset

            email_sent = send_admin_password_reset(
                target,
                temporary_password=new_password,
                must_change=target.must_change_password,
            )
            if not email_sent:
                current_app.logger.warning(
                    "admin_password_reset: email not sent user_id=%s", target.id
                )
        except Exception:
            current_app.logger.exception("admin_password_reset: send_email failed")

        current_app.logger.info(
            "admin_password_reset admin_user_id=%s target_user_id=%s "
            "target_username=%s temporary_password=%s delivered_via=%s",
            current_user.id,
            target.id,
            target.username,
            new_password,
            "email" if email_sent else "manual",
        )

        if email_sent:
            flash(
                f"Password for {target.username} has been reset. "
                f"The temporary password has been emailed to {target.email}.",
                "success",
            )
            return redirect(url_for("auth.users"))

        # Fall back to showing the password on the success page. Mark the
        # message as warning so the admin knows email was not delivered.
        flash(
            f"Password for {target.username} has been reset, but the email "
            f"could not be delivered (mail server is not configured). "
            f"Copy the temporary password below and send it to the user "
            f"through another channel.",
            "warning",
        )
        return render_template(
            "auth/admin_reset_password.html",
            form=form,
            target=target,
            show_temp_password=True,
            temp_password=new_password,
        )

    return render_template(
        "auth/admin_reset_password.html", form=form, target=target
    )


@auth.route("/users/<int:user_id>/disable", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def disable_user(user_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash("You cannot disable your own account.", "danger")
        return redirect(url_for("auth.users"))

    if not target.is_active:
        flash(f"User {target.username} is already disabled.", "info")
        return redirect(url_for("auth.users"))

    target.is_active = False
    db.session.commit()
    log_audit(
        current_user.id,
        "disable_user",
        "user",
        target.id,
        details={"target_username": target.username},
    )

    try:
        from app.email_utils import send_account_disabled

        send_account_disabled(target)
    except Exception:
        current_app.logger.exception("send_account_disabled failed")

    flash(f"User {target.username} has been disabled.", "success")
    return redirect(url_for("auth.users"))


@auth.route("/users/<int:user_id>/enable", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def enable_user(user_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    target = User.query.get_or_404(user_id)
    if target.is_active:
        flash(f"User {target.username} is already active.", "info")
        return redirect(url_for("auth.users"))

    target.is_active = True
    db.session.commit()
    log_audit(
        current_user.id,
        "enable_user",
        "user",
        target.id,
        details={"target_username": target.username},
    )

    try:
        from app.email_utils import send_account_enabled

        send_account_enabled(target)
    except Exception:
        current_app.logger.exception("send_account_enabled failed")

    flash(f"User {target.username} has been enabled.", "success")
    return redirect(url_for("auth.users"))


@auth.route("/users/<int:user_id>/lock", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def lock_user(user_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash("You cannot lock your own account.", "danger")
        return redirect(url_for("auth.users"))

    if not target.is_active:
        flash(
            f"User {target.username} is disabled; enable them before locking.",
            "warning",
        )
        return redirect(url_for("auth.users"))

    try:
        minutes = int(request.form.get("minutes") or 60)
    except (TypeError, ValueError):
        minutes = 60
    minutes = max(1, min(minutes, 60 * 24 * 30))  # 1 minute .. 30 days

    unlock_at = target.lock(minutes=minutes)
    db.session.commit()
    log_audit(
        current_user.id,
        "lock_user",
        "user",
        target.id,
        details={"target_username": target.username, "minutes": minutes},
    )

    try:
        from app.email_utils import send_account_manually_locked

        send_account_manually_locked(target, unlock_at)
    except Exception:
        current_app.logger.exception("send_account_manually_locked failed")

    flash(
        f"User {target.username} has been locked for {minutes} minutes "
        f"(until {unlock_at.strftime('%Y-%m-%d %H:%M UTC')}).",
        "success",
    )
    return redirect(url_for("auth.users"))


@auth.route("/users/<int:user_id>/unlock", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def unlock_user(user_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("main.dashboard"))

    target = User.query.get_or_404(user_id)
    if not target.is_locked():
        flash(f"User {target.username} is not locked.", "info")
        return redirect(url_for("auth.users"))

    target.unlock()
    db.session.commit()
    log_audit(
        current_user.id,
        "unlock_user",
        "user",
        target.id,
        details={"target_username": target.username},
    )

    try:
        from app.email_utils import send_account_unlocked

        send_account_unlocked(target)
    except Exception:
        current_app.logger.exception("send_account_unlocked failed")

    flash(f"User {target.username} has been unlocked.", "success")
    return redirect(url_for("auth.users"))


@auth.route("/profile/2fa/setup", methods=["GET", "POST"])
@login_required
def setup_2fa():
    import base64
    import io

    import pyotp
    import qrcode

    if request.method == "POST":
        code = request.form.get("code", "").strip()

        if not current_user.two_factor_secret:
            current_user.two_factor_secret = pyotp.random_base32()
            db.session.commit()

        if current_user.verify_totp(code):
            current_user.two_factor_enabled = True
            db.session.commit()

            from app.email_utils import send_2fa_enabled

            send_2fa_enabled(current_user)

            log_audit(current_user.id, "2fa_enabled", "user", current_user.id)
            flash("Two-factor authentication enabled successfully!", "success")
            return redirect(url_for("auth.profile"))
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
        "auth/setup_2fa.html",
        qr_code=qr_code,
        secret=current_user.two_factor_secret,
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

    send_2fa_disabled(current_user)

    log_audit(current_user.id, "2fa_disabled", "user", current_user.id)
    flash("Two-factor authentication disabled.", "success")
    return redirect(url_for("auth.profile"))

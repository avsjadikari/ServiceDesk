from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.forms import MailSettingsForm, SystemSettingsForm, TestEmailForm
from app.models import AuditLog
from app.settings_store import (
    apply_mail_config,
    get_company_name,
    get_mail_config,
    mail_is_configured,
    mask_secret,
    set_company_name,
    set_mail_config,
)
from app.utils import log_audit

settings = Blueprint("settings", __name__, url_prefix="/settings")


def _company_history():
    return (
        AuditLog.query.filter_by(action="update_company_name")
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )


def _mail_history():
    return (
        AuditLog.query.filter_by(action="update_mail_config")
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )


@settings.route("/", methods=["GET", "POST"])
@login_required
def index():
    if not current_user.is_admin():
        flash("Only administrators can change system settings.", "danger")
        return redirect(url_for("main.dashboard"))

    form = SystemSettingsForm(data={"company_name": get_company_name()})
    if form.validate_on_submit():
        try:
            new_name = (form.company_name.data or "").strip()
            old_name = get_company_name()
            set_company_name(new_name, user_id=current_user.id)
        except ValueError as exc:
            flash(str(exc), "danger")
            mail_cfg = get_mail_config()
            return render_template(
                "settings/index.html",
                form=form,
                history=_company_history(),
                mail_form=_build_mail_form(),
                test_email_form=_build_test_email_form(),
                mail_config=mail_cfg,
                mail_is_configured=mail_is_configured(),
                mail_masked_password=mask_secret(mail_cfg.get("MAIL_PASSWORD")),
                mail_history=_mail_history(),
            )

        log_audit(
            current_user.id,
            "update_company_name",
            "system_setting",
            details={"old": old_name, "new": new_name},
        )
        current_app.logger.info(
            "Company name updated user_id=%s new=%r",
            current_user.id,
            new_name,
        )
        flash("System settings saved.", "success")
        return redirect(url_for("settings.index"))

    return _render_settings()


@settings.route("/mail", methods=["POST"])
@login_required
def update_mail():
    if not current_user.is_admin():
        flash("Only administrators can change system settings.", "danger")
        return redirect(url_for("main.dashboard"))

    form = MailSettingsForm()
    if not form.validate_on_submit():
        for field, errors in form.errors.items():
            for err in errors:
                flash(f"{field}: {err}", "danger")
        return redirect(url_for("settings.index"))

    old_cfg = get_mail_config()
    new_values = {
        "mail_server": (form.mail_server.data or "").strip(),
        "mail_port": (form.mail_port.data or ""),
        "mail_use_tls": form.mail_use_tls.data,
        "mail_username": (form.mail_username.data or "").strip(),
        "mail_password": (form.mail_password.data or "").replace(" ", ""),
        "mail_default_sender": (form.mail_default_sender.data or "").strip(),
    }
    # For boolean: store as the string "true" / "false" so the
    # get_mail_config helper can round-trip it.
    new_values["mail_use_tls"] = (
        "true" if new_values["mail_use_tls"] else "false"
    )
    # Treat empty password as "don't change it" so the admin does not
    # accidentally wipe a previously-stored secret.
    if not new_values["mail_password"]:
        new_values["mail_password"] = old_cfg.get("MAIL_PASSWORD") or ""

    set_mail_config(new_values, user_id=current_user.id)

    # Push the new values onto the live app so subsequent requests use
    # them without a restart.
    try:
        apply_mail_config(current_app._get_current_object())
    except Exception:
        current_app.logger.exception("apply_mail_config failed after save")

    new_cfg = get_mail_config()
    log_audit(
        current_user.id,
        "update_mail_config",
        "system_setting",
        details={
            "server_changed": old_cfg.get("MAIL_SERVER") != new_cfg.get("MAIL_SERVER"),
            "port_changed": old_cfg.get("MAIL_PORT") != new_cfg.get("MAIL_PORT"),
            "tls_changed": old_cfg.get("MAIL_USE_TLS") != new_cfg.get("MAIL_USE_TLS"),
            "username_changed": old_cfg.get("MAIL_USERNAME")
            != new_cfg.get("MAIL_USERNAME"),
            "password_changed": form.mail_password.data not in (None, ""),
            "sender_changed": old_cfg.get("MAIL_DEFAULT_SENDER")
            != new_cfg.get("MAIL_DEFAULT_SENDER"),
        },
    )
    current_app.logger.info(
        "Mail config updated user_id=%s server=%s port=%s tls=%s",
        current_user.id,
        new_cfg.get("MAIL_SERVER"),
        new_cfg.get("MAIL_PORT"),
        new_cfg.get("MAIL_USE_TLS"),
    )
    flash("Mail server settings saved.", "success")
    return redirect(url_for("settings.index"))


@settings.route("/mail/test", methods=["POST"])
@login_required
def test_mail():
    if not current_user.is_admin():
        flash("Only administrators can test the mail server.", "danger")
        return redirect(url_for("main.dashboard"))

    form = TestEmailForm()
    if not form.validate_on_submit():
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for("settings.index"))

    if not mail_is_configured():
        flash(
            "Mail is not configured yet. Save the mail server settings "
            "first, then try again.",
            "warning",
        )
        return redirect(url_for("settings.index"))

    from app.email_utils import MailSendError, send_email

    subject = "ServiceDesk mail test"
    body = (
        f"Hello,\n\n"
        f"This is a test email sent by ServiceDesk from the System "
        f"Settings page by {current_user.username}.\n\n"
        f"If you received this message, your mail server is configured "
        f"correctly.\n\n"
        f"--\n{current_user.full_name}"
    )
    recipient = form.recipient.data.strip()
    try:
        sent = send_email(recipient, subject, body)
    except MailSendError as exc:
        log_audit(
            current_user.id,
            "test_mail_failed",
            "system_setting",
            details={
                "recipient": recipient,
                "smtp_code": exc.smtp_code,
                "error": exc.user_message,
            },
        )
        current_app.logger.warning(
            "test_mail failed user_id=%s smtp_code=%s error=%s",
            current_user.id,
            exc.smtp_code,
            exc.user_message,
        )
        flash(exc.user_message, "danger")
        return redirect(url_for("settings.index"))

    if sent:
        log_audit(
            current_user.id,
            "test_mail",
            "system_setting",
            details={"recipient": recipient},
        )
        flash(f"Test email sent to {recipient}.", "success")
    else:
        flash(
            "Test email could not be sent. Check the application log for "
            "details, and verify the SMTP server, port, TLS, username and "
            "password are correct.",
            "danger",
        )
    return redirect(url_for("settings.index"))


def _build_mail_form():
    cfg = get_mail_config()
    return MailSettingsForm(
        data={
            "mail_server": cfg.get("MAIL_SERVER") or "",
            "mail_port": cfg.get("MAIL_PORT") or 587,
            "mail_use_tls": bool(cfg.get("MAIL_USE_TLS")),
            "mail_username": cfg.get("MAIL_USERNAME") or "",
            "mail_default_sender": cfg.get("MAIL_DEFAULT_SENDER") or "",
        }
    )


def _build_test_email_form():
    return TestEmailForm(
        data={"recipient": current_user.email if current_user.is_authenticated else ""}
    )


def _render_settings():
    form = SystemSettingsForm(data={"company_name": get_company_name()})
    mail_cfg = get_mail_config()
    return render_template(
        "settings/index.html",
        form=form,
        history=_company_history(),
        mail_form=_build_mail_form(),
        test_email_form=_build_test_email_form(),
        mail_config=mail_cfg,
        mail_is_configured=mail_is_configured(),
        mail_masked_password=mask_secret(mail_cfg.get("MAIL_PASSWORD")),
        mail_history=_mail_history(),
    )

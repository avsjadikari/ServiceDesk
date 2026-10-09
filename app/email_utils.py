import contextlib
import logging
import smtplib
import socket
import threading

from flask_mail import Mail, Message
from flask import current_app, url_for

from app.enums import STATUS_GLOSS

mail = Mail()

logger = logging.getLogger(__name__)

_background_workers = set()


@contextlib.contextmanager
def _mail_timeout():
    # ponytail: flask_mail's SMTP connect accepts no timeout (blocks
    # forever by default); scope a socket default timeout around the send.
    # Only SMTP sockets are opened inside this scope. Per-connection
    # timeout needs replacing flask_mail.Connection.
    old = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(current_app.config.get("MAIL_TIMEOUT", 10))
        yield
    finally:
        socket.setdefaulttimeout(old)


class MailSendError(Exception):
    """Raised when an email could not be sent and the cause is something
    the user can fix (bad credentials, no From address, etc.). The
    message is suitable for display in a flash."""

    def __init__(self, user_message, smtp_code=None, smtp_detail=None):
        super().__init__(user_message)
        self.user_message = user_message
        self.smtp_code = smtp_code
        self.smtp_detail = smtp_detail


def init_mail(app):
    mail.init_app(app)


def _resolve_sender():
    """Return the From address to use when sending email.

    Order of precedence:
    1. ``MAIL_DEFAULT_SENDER`` (set by the admin or by env var)
    2. ``MAIL_USERNAME`` (usually the same address the SMTP relay
       authenticates with, which is also a valid From address)
    Returns ``None`` when neither is set; callers must surface that.
    """
    return (
        current_app.config.get("MAIL_DEFAULT_SENDER")
        or current_app.config.get("MAIL_USERNAME")
    )


def _smtp_error_hint(code, server):
    """Return a short, actionable hint for a given SMTP error code."""
    if code in (530, 535):
        return (
            "The SMTP server rejected the username or password. "
            "Common causes: Google, Microsoft, and Yahoo no longer "
            "accept account passwords over SMTP. Use an App "
            "Password (requires 2-Step Verification on the account). "
            "If your Google account does not show the App Passwords "
            "option, 2-Step Verification is not enabled or your "
            "organisation's policy hides it. The App Password was "
            "typed with spaces. Google displays it as four 4-character "
            "groups (e.g. `abcd efgh ijkl mnop`), but the SMTP server "
            "requires the 16 characters with no spaces. This form "
            "strips spaces automatically, so re-paste the password "
            "and save again. The account password is wrong, or the "
            "username is not a full email address. Alternative: use a "
            "transactional email provider such as Mailgun, SendGrid, "
            "Brevo, Amazon SES, Postmark, or your own ISP's SMTP "
            "relay. These accept ordinary username/password "
            "credentials and do not require App Passwords."
        )
    if code == 421:
        return "The SMTP server is temporarily unavailable. Try again in a few minutes."
    if code == 450 or code == 451:
        return "Recipient mailbox is temporarily unavailable; the server asked us to retry later."
    if code == 452:
        return "The SMTP server is out of storage. Try again later."
    if code == 550:
        return "The server refused to deliver to this recipient (spam, policy, or unknown address)."
    if code == 553:
        return "The From address was rejected. Set a valid Default sender in System Settings."
    return f"Check the SMTP server ({server}) configuration and credentials."


def send_email(to, subject, body, html=None, sender=None, async_=None):
    """Send an email. Returns True on success.

    ``async_`` forces asynchronous dispatch when True or synchronous
    when False; ``None`` (default) falls back to the ``MAIL_ASYNC``
    config value. In async mode this returns True as soon as the send
    is queued on a daemon thread; failures are logged, never raised.
    ``MailSendError`` is only raised in sync mode, for user-actionable
    failures (no From address, SMTP auth failure, etc.); any other
    unexpected error is logged and returns False.
    """
    if not current_app.config.get("MAIL_USERNAME"):
        logger.warning(
            "Email not configured (MAIL_USERNAME missing) — skipping send to %s",
            to,
        )
        return False

    from_addr = sender or _resolve_sender()
    if not from_addr:
        msg = (
            "No From address is configured. Set 'Default sender' in the "
            "mail server form, or set MAIL_DEFAULT_SENDER in the env."
        )
        logger.warning("Email not sent: %s", msg)
        raise MailSendError(msg)

    if async_ is None:
        async_ = current_app.config.get("MAIL_ASYNC", False)

    recipients = [to] if isinstance(to, str) else list(to)

    if async_:
        app = current_app._get_current_object()
        thread = threading.Thread(
            target=_run_in_background,
            args=(_send_in_background, app, from_addr, recipients, subject, body, html),
            daemon=True,
        )
        _background_workers.add(thread)
        thread.start()
        logger.info("Email queued asynchronously to %s subject=%r", to, subject)
        return True

    try:
        msg = Message(
            subject=subject,
            sender=from_addr,
            recipients=recipients,
            body=body,
            html=html,
        )
        with _mail_timeout():
            mail.send(msg)
        logger.info("Email sent to %s from=%s subject=%r", to, from_addr, subject)
        return True
    except smtplib.SMTPAuthenticationError as exc:
        hint = _smtp_error_hint(exc.smtp_code, current_app.config.get("MAIL_SERVER"))
        logger.exception(
            "SMTP authentication failed for %s code=%s",
            from_addr,
            exc.smtp_code,
        )
        raise MailSendError(hint, smtp_code=exc.smtp_code, smtp_detail=str(exc))
    except smtplib.SMTPSenderRefused as exc:
        hint = _smtp_error_hint(exc.smtp_code, current_app.config.get("MAIL_SERVER"))
        logger.exception(
            "SMTP sender refused code=%s sender=%s", exc.smtp_code, exc.sender
        )
        raise MailSendError(hint, smtp_code=exc.smtp_code, smtp_detail=str(exc))
    except smtplib.SMTPRecipientsRefused as exc:
        logger.exception("SMTP refused recipient(s) %s", to)
        raise MailSendError(
            "The SMTP server refused the recipient address.",
            smtp_detail=str(exc),
        )
    except smtplib.SMTPException as exc:
        logger.exception("SMTP error sending to %s", to)
        raise MailSendError(
            f"The SMTP server returned an error: {exc}",
            smtp_detail=str(exc),
        )
    except Exception:
        logger.exception("Failed to send email to %s subject=%r", to, subject)
        return False


def _run_in_background(target, *args):
    try:
        target(*args)
    finally:
        _background_workers.discard(threading.current_thread())


def _send_in_background(app, from_addr, recipients, subject, body, html):
    try:
        with app.app_context():
            msg = Message(
                subject=subject,
                sender=from_addr,
                recipients=recipients,
                body=body,
                html=html,
            )
            with _mail_timeout():
                mail.send(msg)
        logger.info(
            "Email sent (async) to %s subject=%r", recipients, subject
        )
    except Exception:
        logger.exception(
            "Async email failed to=%s subject=%r", recipients, subject
        )


def join_email_workers(timeout=30):
    """Wait for in-flight background sends and clear the registry.

    Intended for tests and shutdown paths that must not race an
    asynchronous email dispatch.
    """
    for thread in list(_background_workers):
        thread.join(timeout)
    _background_workers.clear()


def send_ticket_created(ticket):
    """Notify the creator that their request landed and is owned by the team.

    States the computed Expected Resolution (or none if SLA is unset) and
    includes a track-it link; never promises a response time we don't enforce.
    """
    sla_line = (
        f"Expected Resolution: {ticket.sla_deadline:%m/%d/%Y %H:%M}\n\n"
        if ticket.sla_deadline
        else ""
    )
    subject = f"Ticket {ticket.ticket_number}: your request is in"
    body = (
        f"Your request is in — it's now ticket {ticket.ticket_number} and our team has it.\n\n"
        f"Request: {ticket.title}\n"
        f"Priority: {ticket.priority}\n"
        f"Category: {ticket.category or '-'}\n\n"
        f"{sla_line}"
        f"We'll email you the moment anything changes — no need to check back.\n\n"
        f"Track or update it any time: "
        f"{url_for('portal.view_ticket', ticket_id=ticket.id, _external=True)}\n"
    )
    return send_email(ticket.creator.email, subject, body)


def send_ticket_assigned(ticket):
    """Notify the assignee that they now own this ticket; no-op if unassigned."""
    if not ticket.assignee:
        return None
    subject = f"[{ticket.ticket_number}] Ticket Assigned to You"
    body = (
        f"A ticket has been assigned to you:\n\n"
        f"Ticket Number: {ticket.ticket_number}\n"
        f"Title: {ticket.title}\n"
        f"Priority: {ticket.priority}\n"
        f"Category: {ticket.category}\n"
        f"Assigned By: {ticket.creator.full_name}\n\n"
        f"Description:\n{ticket.description}\n\n"
        f"Log in to the ServiceDesk system to view and respond to this ticket."
    )
    return send_email(ticket.assignee.email, subject, body)


def send_ticket_status_changed(ticket, new_status):
    """Notify the creator of a status move, translated via STATUS_GLOSS.

    Plain-language meaning only — raw status slugs never reach end users.
    """
    gloss = STATUS_GLOSS.get(new_status, new_status)
    subject = f"Ticket {ticket.ticket_number}: status update"
    body = (
        f"Your ticket just moved:\n\n"
        f"Ticket: {ticket.ticket_number}\n"
        f"Request: {ticket.title}\n"
        f"What's happening: {gloss.capitalize()}\n\n"
        f"Track it any time: "
        f"{url_for('portal.view_ticket', ticket_id=ticket.id, _external=True)}\n"
    )
    return send_email(ticket.creator.email, subject, body)


def send_ticket_comment(ticket, comment):
    """Notify the creator that a new (non-internal) comment landed on their ticket."""
    subject = f"[{ticket.ticket_number}] New Comment on Your Ticket"
    body = (
        f"A new comment has been added to your ticket:\n\n"
        f"Ticket Number: {ticket.ticket_number}\n"
        f"Title: {ticket.title}\n"
        f"Comment by: {comment.user.full_name}\n\n"
        f"Comment:\n{comment.content}\n\n"
        f"Log in to the ServiceDesk system to view the full ticket and all comments."
    )
    return send_email(ticket.creator.email, subject, body)


def send_password_reset(user, reset_url):
    subject = "ServiceDesk - Password Reset Request"
    body = (
        f"Hello {user.full_name},\n\n"
        f"We received a request to reset your password.\n\n"
        f"Click the link below to set a new password. The link will expire in 30 minutes:\n"
        f"{reset_url}\n\n"
        f"If you did not request this, you can safely ignore this email. "
        f"Your password will remain unchanged.\n\n"
        f"Thank you,\nServiceDesk Team"
    )
    return send_email(user.email, subject, body, async_=False)


def send_welcome_email(user):
    subject = "Welcome to ServiceDesk"
    body = (
        f"Hello {user.full_name},\n\n"
        f"Welcome to ServiceDesk! Your account has been created.\n\n"
        f"Username: {user.username}\n"
        f"Role: {user.role}\n\n"
        f"Log in and change your password on first access.\n\n"
        f"Thank you,\nServiceDesk Team"
    )
    return send_email(user.email, subject, body)


def send_2fa_enabled(user):
    subject = "ServiceDesk - Two-Factor Authentication Enabled"
    body = (
        f"Hello {user.full_name},\n\n"
        f"Two-factor authentication has been enabled on your account.\n\n"
        f"If you did not enable this, please contact IT support immediately.\n\n"
        f"Thank you,\nServiceDesk Team"
    )
    return send_email(user.email, subject, body)


def send_2fa_disabled(user):
    subject = "ServiceDesk - Two-Factor Authentication Disabled"
    body = (
        f"Hello {user.full_name},\n\n"
        f"Two-factor authentication has been disabled on your account.\n\n"
        f"If you did not disable this, please contact IT support immediately.\n\n"
        f"Thank you,\nServiceDesk Team"
    )
    return send_email(user.email, subject, body)


def send_account_locked(user, unlock_at):
    subject = "ServiceDesk - Account temporarily locked"
    body = (
        f"Hello {user.full_name},\n\n"
        f"Too many failed login attempts have temporarily locked your account until "
        f"{unlock_at.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n\n"
        f"If this was not you, please contact IT support immediately.\n\n"
        f"Thank you,\nServiceDesk Team"
    )
    return send_email(user.email, subject, body)


def send_admin_password_reset(user, temporary_password=None, must_change=True):
    subject = "ServiceDesk - Your password was reset by an administrator"
    if temporary_password and must_change:
        body = (
            f"Hello {user.full_name},\n\n"
            f"An administrator reset your ServiceDesk password and set a "
            f"temporary password:\n\n"
            f"    {temporary_password}\n\n"
            f"You will be required to choose a new password the next time you sign in.\n\n"
            f"If you did not request this change, contact IT support immediately.\n\n"
            f"Thank you,\nServiceDesk Team"
        )
    else:
        body = (
            f"Hello {user.full_name},\n\n"
            f"An administrator reset your ServiceDesk password.\n\n"
            f"You can sign in with the new password you were given. "
            f"If you don't know it, contact IT support.\n\n"
            f"Thank you,\nServiceDesk Team"
        )
    return send_email(user.email, subject, body)


def send_account_disabled(user):
    subject = "ServiceDesk - Your account has been disabled"
    body = (
        f"Hello {user.full_name},\n\n"
        f"Your ServiceDesk account has been disabled by an administrator. "
        f"You will not be able to sign in until it is re-enabled.\n\n"
        f"If you believe this is a mistake, please contact IT support.\n\n"
        f"Thank you,\nServiceDesk Team"
    )
    return send_email(user.email, subject, body)


def send_account_enabled(user):
    subject = "ServiceDesk - Your account has been re-enabled"
    body = (
        f"Hello {user.full_name},\n\n"
        f"Your ServiceDesk account has been re-enabled by an administrator. "
        f"You can sign in again with your existing password.\n\n"
        f"Thank you,\nServiceDesk Team"
    )
    return send_email(user.email, subject, body)


def send_account_manually_locked(user, unlock_at):
    subject = "ServiceDesk - Your account has been locked"
    body = (
        f"Hello {user.full_name},\n\n"
        f"An administrator has locked your ServiceDesk account until "
        f"{unlock_at.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n\n"
        f"You will not be able to sign in during this time. "
        f"Contact IT support if you have questions.\n\n"
        f"Thank you,\nServiceDesk Team"
    )
    return send_email(user.email, subject, body)


def send_account_unlocked(user):
    subject = "ServiceDesk - Your account has been unlocked"
    body = (
        f"Hello {user.full_name},\n\n"
        f"An administrator has unlocked your ServiceDesk account. "
        f"You can sign in again with your existing password.\n\n"
        f"Thank you,\nServiceDesk Team"
    )
    return send_email(user.email, subject, body)

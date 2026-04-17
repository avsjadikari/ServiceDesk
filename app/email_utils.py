import os
import logging
from flask_mail import Mail, Message
from flask import current_app

mail = Mail()

logger = logging.getLogger(__name__)


def init_mail(app):
    mail.init_app(app)
    logger.info(f"Flask-Mail initialized with server: {app.config.get('MAIL_SERVER')}")


def send_email(to, subject, body, html=None, template=None):
    try:
        if not current_app.config.get("MAIL_USERNAME"):
            logger.warning("Email not configured - skipping send")
            return False

        msg = Message(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            body=body,
            html=html,
        )

        with current_app.app_context():
            mail.send(msg)

        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False


def send_ticket_created(ticket):
    subject = f"[{ticket.ticket_number}] New Ticket Created"
    body = f"""
A new ticket has been created:

Ticket Number: {ticket.ticket_number}
Title: {ticket.title}
Priority: {ticket.priority}
Category: {ticket.category}
Status: {ticket.status}

Description:
{ticket.description}

Please login to the ServiceDesk system to view and respond to this ticket.
"""
    send_email(ticket.creator.email, subject, body)


def send_ticket_assigned(ticket):
    if not ticket.assignee:
        return

    subject = f"[{ticket.ticket_number}] Ticket Assigned to You"
    body = f"""
A ticket has been assigned to you:

Ticket Number: {ticket.ticket_number}
Title: {ticket.title}
Priority: {ticket.priority}
Category: {ticket.category}
Assigned By: {ticket.creator.full_name}

Description:
{ticket.description}

Please login to the ServiceDesk system to view and respond to this ticket.
"""
    send_email(ticket.assignee.email, subject, body)


def send_ticket_status_changed(ticket, old_status, new_status):
    subject = f"[{ticket.ticket_number}] Ticket Status Updated"
    body = f"""
Your ticket status has been updated:

Ticket Number: {ticket.ticket_number}
Title: {ticket.title}
Previous Status: {old_status}
New Status: {new_status}

Please login to the ServiceDesk system to view the updated ticket.
"""
    send_email(ticket.creator.email, subject, body)


def send_ticket_comment(ticket, comment):
    subject = f"[{ticket.ticket_number}] New Comment on Your Ticket"
    body = f"""
A new comment has been added to your ticket:

Ticket Number: {ticket.ticket_number}
Title: {ticket.title}
Comment by: {comment.user.full_name}

Comment:
{comment.content}

Please login to the ServiceDesk system to view the full ticket and all comments.
"""
    send_email(ticket.creator.email, subject, body)


def send_password_reset(user, reset_token):
    subject = "ServiceDesk - Password Reset Request"
    body = f"""
Hello {user.full_name},

We received a request to reset your password.

Your password reset token is: {reset_token}

This token will expire in 24 hours.

If you did not request this, please ignore this email.

Thank you,
ServiceDesk Team
"""
    send_email(user.email, subject, body)


def send_welcome_email(user):
    subject = "Welcome to ServiceDesk"
    body = f"""
Hello {user.full_name},

Welcome to ServiceDesk! Your account has been created.

Username: {user.username}
Role: {user.role}

Please login and change your password on first access.

Thank you,
ServiceDesk Team
"""
    send_email(user.email, subject, body)


def send_2fa_enabled(user):
    subject = "ServiceDesk - Two-Factor Authentication Enabled"
    body = f"""
Hello {user.full_name},

Two-factor authentication has been enabled on your account.

If you did not enable this, please contact IT support immediately.

Thank you,
ServiceDesk Team
"""
    send_email(user.email, subject, body)


def send_2fa_disabled(user):
    subject = "ServiceDesk - Two-Factor Authentication Disabled"
    body = f"""
Hello {user.full_name},

Two-factor authentication has been disabled on your account.

If you did not disable this, please contact IT support immediately.

Thank you,
ServiceDesk Team
"""
    send_email(user.email, subject, body)

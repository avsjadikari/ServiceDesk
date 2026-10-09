"""Seed data: first-run accounts and the sample knowledge-base corpus.

Shared by the first-run setup wizard and the ``init_database`` entry point so
the two bootstrap paths create the same accounts and articles. Nothing here
commits; callers own the transaction.
"""

import secrets

from app import db
from app.models import Article, User

_TEMP_PASSWORD_ALPHABET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@$!%*?&"
)

_DEMO_ACCOUNTS = (
    ("agent", "agent@servicedesk.local", "Support Agent", "agent", "IT Support"),
    ("user", "user@servicedesk.local", "Regular User", "user", "Operations"),
)


def generate_temp_password(length: int = 20) -> str:
    return "".join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(length))


def init_database():
    db.create_all()
    return _create_default_data()


def _create_default_data():
    """Create schema and, when empty, the default accounts + sample articles.
    Returns the generated demo passwords (or None) for logging."""
    generated_passwords = {}

    if User.query.count() == 0:
        admin_pw = generate_temp_password()
        admin, demo = seed_accounts(
            admin_username="admin",
            admin_email="admin@servicedesk.local",
            admin_password=admin_pw,
            admin_full_name="System Administrator",
            admin_department="IT",
        )
        generated_passwords["admin"] = admin_pw
        generated_passwords.update(demo)
    else:
        admin = User.query.filter_by(role="admin").first()

    if admin is not None:
        seed_articles(author_id=admin.id)

    db.session.commit()

    if generated_passwords:
        _log_generated_credentials(generated_passwords)
    return generated_passwords or None


def _log_generated_credentials(passwords):
    try:
        from flask import current_app

        stream = current_app._get_current_object().logger.info
    except Exception:
        stream = print
    stream(
        "Generated temporary credentials (must be changed on first login): "
        + ", ".join(f"{u}={p}" for u, p in passwords.items())
    )


def seed_accounts(
    *,
    admin_username,
    admin_email,
    admin_password,
    admin_full_name,
    admin_department="IT",
):
    """Create the first admin plus the agent/user demo accounts (random
    temporary passwords). Flushes, does not commit. Returns
    ``(admin, {username: temp_password})`` for the demo accounts."""
    admin = User.provision(
        username=admin_username,
        email=admin_email,
        password=admin_password,
        full_name=admin_full_name,
        role="admin",
        department=admin_department,
        must_change_password=True,
    )
    db.session.add(admin)

    demo_passwords = {}
    for username, email, full_name, role, department in _DEMO_ACCOUNTS:
        password = generate_temp_password()
        db.session.add(
            User.provision(
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                role=role,
                department=department,
                must_change_password=True,
            )
        )
        demo_passwords[username] = password

    db.session.flush()
    return admin, demo_passwords


def seed_articles(*, author_id):
    """Add the sample knowledge-base articles when the table is empty.
    Does not commit."""
    if Article.query.count() > 0:
        return
    for article in _sample_articles(author_id):
        db.session.add(article)


def _sample_articles(author_id):
    return [
        Article(
            title="How to Reset Your Password",
            content=(
                "# Password Reset Guide\n\n"
                "Follow these steps to reset your password:\n\n"
                '1. Go to the login page\n2. Click "Forgot Password"\n'
                "3. Enter your email address\n"
                "4. Check your inbox for reset link\n"
                "5. Create a new password\n\n"
                "## Requirements\n- At least 8 characters\n"
                "- Include uppercase and lowercase\n"
                "- Include a number\n- Include a special character\n\n"
                "## Common Issues\n"
                "- If you don't receive the email, check your spam folder\n"
                "- For immediate assistance, contact IT support"
            ),
            category="Account/Access",
            tags=["password", "reset", "security"],
            status="published",
            author_id=author_id,
        ),
        Article(
            title="VPN Setup Guide",
            content=(
                "# Connecting to VPN\n\n## Prerequisites\n"
                "- Active directory credentials\n- VPN client installed\n\n"
                "## Steps to Connect\n\n"
                "1. Open the VPN client\n2. Enter server address: vpn.company.local\n"
                "3. Click Connect\n4. Enter your credentials\n"
                "5. Complete 2FA verification\n\n## Troubleshooting\n\n"
                "If you cannot connect:\n- Check your internet connection\n"
                "- Verify credentials are correct\n- Restart the VPN client\n"
                "- Contact IT support"
            ),
            category="Network",
            tags=["vpn", "remote", "network"],
            status="published",
            author_id=author_id,
        ),
        Article(
            title="Requesting Software Installation",
            content=(
                "# Software Request Process\n\n## Approved Software\n"
                "The following software is pre-approved:\n"
                "- Microsoft Office Suite\n- Adobe Acrobat Reader\n"
                "- Chrome/Firefox browsers\n- 7-Zip\n- VLC Media Player\n\n"
                "## Request Process\n\n"
                "1. Log in to ServiceDesk\n2. Submit a new ticket\n"
                '3. Select "Software Request"\n'
                "4. Provide software name and business justification\n"
                "5. Wait for approval (24-48 hours)\n\n"
                "## Unapproved Software\n"
                "For software not in the approved list, manager approval is required."
            ),
            category="Software",
            tags=["software", "request", "installation"],
            status="published",
            author_id=author_id,
        ),
        Article(
            title="Email Configuration Guide",
            content=(
                "# Email Configuration\n\n## Outlook Setup\n\n"
                "### Automatic Setup\n1. Open Outlook\n2. Enter your email address\n"
                "3. Click Connect\n4. Enter your password\n5. Complete 2FA if prompted\n\n"
                "### Manual Setup\nIf automatic setup fails:\n"
                "- Server: outlook.office365.com\n- Port: 993\n"
                "- Encryption: SSL/TLS\n- IMAP or POP3 available"
            ),
            category="Email",
            tags=["email", "outlook", "configuration"],
            status="published",
            author_id=author_id,
        ),
        Article(
            title="Network Drive Mapping",
            content=(
                "# Mapping Network Drives\n\n## Common Network Shares\n"
                "- S:\\\\ - Shared documents\n- T:\\\\ - Team folders\n"
                "- U:\\\\ - User home directory\n\n## How to Map\n"
                "1. Open File Explorer\n2. Right-click \"This PC\"\n"
                "3. Select \"Map network drive\"\n4. Choose a drive letter\n"
                "5. Enter the folder path\n6. Check \"Reconnect at logon\"\n\n"
                "## Access Issues\n"
                "Contact IT support if you cannot access your assigned drives."
            ),
            category="Network",
            tags=["network", "drive", "mapping"],
            status="published",
            author_id=author_id,
        ),
    ]

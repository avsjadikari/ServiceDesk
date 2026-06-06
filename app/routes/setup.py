import os
import re
from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    session,
    send_file,
    current_app,
)
from flask_login import login_user, current_user
from sqlalchemy import text
from app import db, _generate_temp_password
from app.models import User, Article
from app.forms import SetupForm

setup = Blueprint("setup", __name__)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _is_dev_mode():
    return os.environ.get("FLASK_CONFIG", "development") != "production"


def save_config(db_type, db_host, db_port, db_name, db_user, db_password, company_name):
    existing_config = {}

    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    existing_config[key] = value

    config_lines = []
    config_lines.append(f"DB_TYPE={db_type}")
    config_lines.append(f"DB_HOST={db_host}")
    config_lines.append(f"DB_PORT={db_port}")
    config_lines.append(f"DB_NAME={db_name}")
    config_lines.append(f"DB_USER={db_user}")
    config_lines.append(f"DB_PASSWORD={db_password}")
    config_lines.append(f"COMPANY_NAME={company_name}")

    if existing_config.get("SECRET_KEY"):
        config_lines.append(f"SECRET_KEY={existing_config['SECRET_KEY']}")
    if existing_config.get("FLASK_CONFIG"):
        config_lines.append(f"FLASK_CONFIG={existing_config['FLASK_CONFIG']}")

    with open(".env", "w") as f:
        f.write("\n".join(config_lines) + "\n")


@setup.route("/setup", methods=["GET", "POST"])
def wizard():
    try:
        admin_exists = User.query.filter_by(role="admin").first()
        if admin_exists:
            session["setup_complete"] = True
            return redirect(url_for("main.index"))
    except Exception:
        pass

    form = SetupForm()

    if form.validate_on_submit():
        admin_username = form.admin_username.data
        admin_email = form.admin_email.data
        admin_password = form.admin_password.data
        admin_full_name = form.admin_full_name.data
        company_name = (form.company_name.data or "ServiceDesk").strip()

        db_type = form.db_type.data
        db_host = form.db_host.data
        db_port = form.db_port.data
        db_name = form.db_name.data
        db_user = form.db_user.data
        db_password = form.db_password.data

        save_config(
            db_type, db_host, db_port, db_name, db_user, db_password, company_name
        )

        db.create_all()

        from app.settings_store import set_company_name

        set_company_name(company_name, user_id=None)

        admin = User(
            username=admin_username,
            email=admin_email,
            full_name=admin_full_name,
            role="admin",
            department="IT",
            is_active=True,
            must_change_password=True,
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.flush()

        agent_pw = _generate_temp_password()
        agent = User(
            username="agent",
            email="agent@servicedesk.local",
            full_name="Support Agent",
            role="agent",
            department="IT Support",
            is_active=True,
            must_change_password=True,
        )
        agent.set_password(agent_pw)
        db.session.add(agent)

        user_pw = _generate_temp_password()
        user = User(
            username="user",
            email="user@servicedesk.local",
            full_name="Regular User",
            role="user",
            department="Operations",
            is_active=True,
            must_change_password=True,
        )
        user.set_password(user_pw)
        db.session.add(user)

        sample_articles = [
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
                author_id=admin.id,
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
                author_id=admin.id,
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
                author_id=admin.id,
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
                author_id=admin.id,
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
                author_id=admin.id,
            ),
        ]

        for article in sample_articles:
            db.session.add(article)

        db.session.commit()

        session["setup_complete"] = True
        session["company_name"] = company_name
        session["setup_temp_passwords"] = {"agent": agent_pw, "user": user_pw}

        flash(
            "Setup completed. Please log in. "
            "Demo accounts (agent/user) were created with random temporary passwords "
            "shown in the application logs; both must change their password on first login.",
            "success",
        )
        login_user(admin)

        return redirect(url_for("main.dashboard"))

    company_name = os.environ.get("COMPANY_NAME", "ServiceDesk")
    return render_template("setup/wizard.html", company_name=company_name, form=form)


@setup.route("/setup/complete")
def complete():
    session["setup_complete"] = True
    return redirect(url_for("main.index"))


@setup.route("/admin/db/init", methods=["GET", "POST"])
def db_init():
    if not current_user.is_authenticated or not current_user.is_admin():
        flash("Access denied. Admin only.", "danger")
        return redirect(url_for("main.dashboard"))

    if not _is_dev_mode():
        flash(
            "Database initialization via the web UI is disabled in production. "
            "Use 'flask db upgrade' / 'flask db downgrade' on the server instead.",
            "danger",
        )
        return redirect(url_for("main.dashboard"))

    confirm = request.form.get("confirm", "")
    if request.method == "POST" and confirm != "RESET":
        flash("Confirmation phrase incorrect. Database was NOT modified.", "warning")
        return redirect(url_for("setup.db_init"))

    if request.method == "POST":
        try:
            db.session.commit()

            db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")

            if "postgresql" in db_uri:
                db.session.execute(text("DROP SCHEMA public CASCADE"))
                db.session.execute(text("CREATE SCHEMA public"))
            else:
                result = db.session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
                tables = [row[0] for row in result]
                for table in tables:
                    if not _SAFE_IDENTIFIER.match(table):
                        current_app.logger.warning(
                            "Skipping table drop for unsafe name: %s", table
                        )
                        continue
                    db.session.execute(text(f"DROP TABLE IF EXISTS {table}"))

            db.session.commit()

            flash(
                "Database re-initialized successfully! Please restart and run setup again.",
                "success",
            )
            session.clear()

            return redirect(url_for("setup.wizard"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Database re-init failed")
            flash(f"Error initializing database: {str(e)}", "danger")

    return render_template("setup/db_init.html")


@setup.route("/admin/db/backup")
def db_backup():
    if not current_user.is_authenticated or not current_user.is_admin():
        flash("Access denied. Admin only.", "danger")
        return redirect(url_for("main.dashboard"))

    try:
        db_uri = db.engine.url
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if str(db_uri).startswith("sqlite"):
            db_path = db_uri.database
            if os.path.exists(db_path):
                return send_file(
                    db_path,
                    as_attachment=True,
                    download_name=f"servicedesk_backup_{timestamp}.db",
                    mimetype="application/x-sqlite3",
                )
            flash("Database file not found", "danger")
        else:
            flash(
                "Backup feature currently only supports SQLite. For PostgreSQL, "
                "use 'pg_dump' on the server or your managed-database tooling.",
                "warning",
            )

    except Exception as e:
        current_app.logger.exception("Database backup failed")
        flash(f"Error creating backup: {str(e)}", "danger")

    return redirect(url_for("main.dashboard"))

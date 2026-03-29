from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    session,
    send_file,
    jsonify,
)
from flask_login import login_user, current_user
from app import db
from app.models import User, Article
from app.forms import SetupForm
from werkzeug.security import generate_password_hash
import os
from datetime import datetime

setup = Blueprint("setup", __name__)


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
    if existing_config.get("FLASK_ENV"):
        config_lines.append(f"FLASK_ENV={existing_config['FLASK_ENV']}")
    if existing_config.get("FLASK_DEBUG"):
        config_lines.append(f"FLASK_DEBUG={existing_config['FLASK_DEBUG']}")

    with open(".env", "w") as f:
        f.write("\n".join(config_lines))


@setup.route("/setup", methods=["GET", "POST"])
def wizard():
    try:
        admin_exists = User.query.filter_by(role="admin").first()
        if admin_exists:
            session["setup_complete"] = True
            return redirect(url_for("main.index"))
    except:
        pass

    form = SetupForm()

    if form.validate_on_submit():
        admin_username = form.admin_username.data
        admin_email = form.admin_email.data
        admin_password = form.admin_password.data
        admin_full_name = form.admin_full_name.data
        company_name = form.company_name.data or "ServiceDesk"

        db_type = form.db_type.data
        db_host = form.db_host.data
        db_port = form.db_port.data
        db_name = form.db_name.data
        db_user = form.db_user.data
        db_password = form.db_password.data

        save_config(
            db_type, db_host, db_port, db_name, db_user, db_password, company_name
        )

        try:
            from sqlalchemy import text

            db.session.commit()
            db.session.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            db.session.execute(text("CREATE SCHEMA public"))
            db.session.commit()
            db.create_all()
        except Exception as e:
            db.session.rollback()
            try:
                db.drop_all()
                db.create_all()
            except:
                pass

        admin = User(
            username=admin_username,
            email=admin_email,
            full_name=admin_full_name,
            role="admin",
            department="IT",
            is_active=True,
            must_change_password=True,
        )
        admin.password_hash = generate_password_hash(admin_password)
        db.session.add(admin)
        db.session.flush()

        agent = User(
            username="agent",
            email="agent@servicedesk.local",
            full_name="Support Agent",
            role="agent",
            department="IT Support",
            is_active=True,
            must_change_password=True,
        )
        agent.password_hash = generate_password_hash("agent123")
        db.session.add(agent)

        user = User(
            username="user",
            email="user@servicedesk.local",
            full_name="Regular User",
            role="user",
            department="Operations",
            is_active=True,
            must_change_password=True,
        )
        user.password_hash = generate_password_hash("user123")
        db.session.add(user)

        sample_articles = [
            Article(
                title="How to Reset Your Password",
                content="""# Password Reset Guide

Follow these steps to reset your password:

1. Go to the login page
2. Click "Forgot Password"
3. Enter your email address
4. Check your inbox for reset link
5. Create a new password

## Requirements
- At least 8 characters
- Include uppercase and lowercase
- Include a number
- Include a special character

## Common Issues
- If you don't receive the email, check your spam folder
- For immediate assistance, contact IT support""",
                category="Account/Access",
                tags=["password", "reset", "security"],
                status="published",
                author_id=admin.id,
            ),
            Article(
                title="VPN Setup Guide",
                content="""# Connecting to VPN

## Prerequisites
- Active directory credentials
- VPN client installed

## Steps to Connect

1. Open the VPN client
2. Enter server address: vpn.company.local
3. Click Connect
4. Enter your credentials
5. Complete 2FA verification

## Troubleshooting

If you cannot connect:
- Check your internet connection
- Verify credentials are correct
- Restart the VPN client
- Contact IT support""",
                category="Network",
                tags=["vpn", "remote", "network"],
                status="published",
                author_id=admin.id,
            ),
            Article(
                title="Requesting Software Installation",
                content="""# Software Request Process

## Approved Software
The following software is pre-approved:
- Microsoft Office Suite
- Adobe Acrobat Reader
- Chrome/Firefox browsers
- 7-Zip
- VLC Media Player

## Request Process

1. Log in to ServiceDesk
2. Submit a new ticket
3. Select "Software Request"
4. Provide software name and business justification
5. Wait for approval (24-48 hours)

## Unapproved Software
For software not in the approved list, manager approval is required.""",
                category="Software",
                tags=["software", "request", "installation"],
                status="published",
                author_id=admin.id,
            ),
            Article(
                title="Email Configuration Guide",
                content="""# Email Configuration

## Outlook Setup

### Automatic Setup
1. Open Outlook
2. Enter your email address
3. Click Connect
4. Enter your password
5. Complete 2FA if prompted

### Manual Setup
If automatic setup fails:
- Server: outlook.office365.com
- Port: 993
- Encryption: SSL/TLS
- IMAP or POP3 available""",
                category="Email",
                tags=["email", "outlook", "configuration"],
                status="published",
                author_id=admin.id,
            ),
            Article(
                title="Network Drive Mapping",
                content="""# Mapping Network Drives

## Common Network Shares
- S:\\ - Shared documents
- T:\\ - Team folders
- U:\\ - User home directory

## How to Map
1. Open File Explorer
2. Right-click "This PC"
3. Select "Map network drive"
4. Choose a drive letter
5. Enter the folder path
6. Check "Reconnect at logon"

## Access Issues
Contact IT support if you cannot access your assigned drives.""",
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

        flash(
            "Setup completed successfully! Restart the application to apply database changes.",
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

    if request.method == "POST":
        try:
            from sqlalchemy import text

            db.session.commit()
            db.session.execute(text("DROP SCHEMA public CASCADE"))
            db.session.execute(text("CREATE SCHEMA public"))
            db.session.commit()

            flash(
                "Database re-initialized successfully! Please restart and run setup again.",
                "success",
            )
            session.clear()

            return redirect(url_for("setup.wizard"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error initializing database: {str(e)}", "danger")

    return render_template("setup/db_init.html")


@setup.route("/admin/db/backup")
def db_backup():
    if not current_user.is_authenticated or not current_user.is_admin():
        flash("Access denied. Admin only.", "danger")
        return redirect(url_for("main.dashboard"))

    try:
        db_uri = db.engine.url
        db_name = db_uri.database
        db_user = db_uri.username
        db_host = db_uri.host

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
            else:
                flash("Database file not found", "danger")
        else:
            flash(
                "Backup feature currently only supports SQLite. For PostgreSQL, use pg_dump manually.",
                "warning",
            )

    except Exception as e:
        flash(f"Error creating backup: {str(e)}", "danger")

    return redirect(url_for("main.dashboard"))

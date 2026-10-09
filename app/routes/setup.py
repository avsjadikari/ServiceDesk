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
from app import db
from app.models import User
from app.seed import seed_accounts, seed_articles
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

    # In production the wizard is the trusted one-time bootstrap, so require
    # evidence that the operator prepared it (SETUP_TOKEN env). Prevents a
    # remote attacker from racing the real admin to create the first account.
    if not _is_dev_mode():
        expected = current_app.config.get("SETUP_TOKEN") or os.environ.get(
            "SETUP_TOKEN", ""
        )
        provided = (request.form.get("setup_token") or "").strip()
        if not expected or provided != expected:
            if request.method == "POST":
                flash(
                    "Setup token is invalid. The server administrator must set "
                    "SETUP_TOKEN before first-run setup can complete.",
                    "danger",
                )
            return render_template(
                "setup/wizard.html",
                company_name=os.environ.get("COMPANY_NAME", "ServiceDesk"),
                form=form,
                require_setup_token=bool(expected),
                setup_token_unconfigured=not bool(expected),
            )

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

        if _is_dev_mode():
            save_config(
                db_type, db_host, db_port, db_name, db_user, db_password, company_name
            )
        else:
            current_app.logger.info(
                "Skipping .env write: production database configuration must "
                "come from the deployment environment"
            )

        db.create_all()

        from app.settings_store import set_company_name

        set_company_name(company_name, user_id=None)

        admin, demo_passwords = seed_accounts(
            admin_username=admin_username,
            admin_email=admin_email,
            admin_password=admin_password,
            admin_full_name=admin_full_name,
        )
        seed_articles(author_id=admin.id)

        db.session.commit()

        session["setup_complete"] = True
        session["company_name"] = company_name
        session["setup_temp_passwords"] = demo_passwords

        flash(
            "Setup completed. Please log in. "
            "Demo accounts (agent/user) were created with random temporary passwords "
            "shown in the application logs; both must change their password on first login.",
            "success",
        )
        login_user(admin)

        return redirect(url_for("main.dashboard"))

    company_name = os.environ.get("COMPANY_NAME", "ServiceDesk")
    return render_template(
        "setup/wizard.html",
        company_name=company_name,
        form=form,
        require_setup_token=False,
        setup_token_unconfigured=False,
    )


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

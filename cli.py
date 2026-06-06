"""Flask CLI entry point.

Lets ``flask db ...`` (Flask-Migrate) and other registered CLI groups work
when invoking the application via the ``flask`` command.
"""
from app import create_app, db
from app.models import (
    User,
    Ticket,
    Comment,
    Article,
    ArticleVersion,
    Asset,
    Attachment,
    AuditLog,
    AutomationRule,
)

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "User": User,
        "Ticket": Ticket,
        "Comment": Comment,
        "Article": Article,
        "ArticleVersion": ArticleVersion,
        "Asset": Asset,
        "Attachment": Attachment,
        "AuditLog": AuditLog,
        "AutomationRule": AutomationRule,
    }

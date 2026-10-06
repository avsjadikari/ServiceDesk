"""Add query indices and CHECK constraints

Revision ID: 2f9c4a7d3e10
Revises: 1e8703d56f57
Create Date: 2026-10-06

Adds the missing secondary indexes used by list/filter/join queries and
DB-level CHECK constraints for the well-known value enums (user role,
ticket status/priority/type, article status, asset status). Batch mode
lets this run on SQLite (table copy) and PostgreSQL (direct ALTER).
"""
from alembic import op

revision = "2f9c4a7d3e10"
down_revision = "1e8703d56f57"


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.create_index("ix_users_role", ["role"])
        batch.create_check_constraint(
            "ck_users_role", "role IN ('user', 'agent', 'admin')"
        )

    with op.batch_alter_table("tickets") as batch:
        batch.create_index("ix_tickets_created_by", ["created_by"])
        batch.create_index("ix_tickets_assigned_to", ["assigned_to"])
        batch.create_check_constraint(
            "ck_tickets_status",
            "status IN ('new', 'assigned', 'in_progress', 'pending', "
            "'resolved', 'closed')",
        )
        batch.create_check_constraint(
            "ck_tickets_priority", "priority IN ('low', 'medium', 'high', 'critical')"
        )
        batch.create_check_constraint(
            "ck_tickets_type", "type IN ('incident', 'request', 'problem')"
        )

    with op.batch_alter_table("comments") as batch:
        batch.create_index("ix_comments_ticket_id", ["ticket_id"])
        batch.create_index("ix_comments_user_id", ["user_id"])

    with op.batch_alter_table("articles") as batch:
        batch.create_index("ix_articles_author_id", ["author_id"])
        batch.create_index("ix_articles_updated_at", ["updated_at"])
        batch.create_check_constraint(
            "ck_articles_status",
            "status IN ('draft', 'published', 'archived')",
        )

    with op.batch_alter_table("assets") as batch:
        batch.create_index("ix_assets_name", ["name"])
        batch.create_index("ix_assets_assigned_to", ["assigned_to"])
        batch.create_check_constraint(
            "ck_assets_status",
            "status IN ('active', 'maintenance', 'retired', 'available')",
        )

    with op.batch_alter_table("article_versions") as batch:
        batch.create_index("ix_article_versions_article_id", ["article_id"])

    with op.batch_alter_table("attachments") as batch:
        batch.create_index("ix_attachments_ticket_id", ["ticket_id"])


def downgrade():
    with op.batch_alter_table("attachments") as batch:
        batch.drop_index("ix_attachments_ticket_id")

    with op.batch_alter_table("article_versions") as batch:
        batch.drop_index("ix_article_versions_article_id")

    with op.batch_alter_table("assets") as batch:
        batch.drop_index("ix_assets_assigned_to")
        batch.drop_index("ix_assets_name")
        batch.drop_check_constraint("ck_assets_status")

    with op.batch_alter_table("articles") as batch:
        batch.drop_index("ix_articles_updated_at")
        batch.drop_index("ix_articles_author_id")
        batch.drop_check_constraint("ck_articles_status")

    with op.batch_alter_table("comments") as batch:
        batch.drop_index("ix_comments_user_id")
        batch.drop_index("ix_comments_ticket_id")

    with op.batch_alter_table("tickets") as batch:
        batch.drop_check_constraint("ck_tickets_type")
        batch.drop_check_constraint("ck_tickets_priority")
        batch.drop_check_constraint("ck_tickets_status")
        batch.drop_index("ix_tickets_assigned_to")
        batch.drop_index("ix_tickets_created_by")

    with op.batch_alter_table("users") as batch:
        batch.drop_check_constraint("ck_users_role")
        batch.drop_index("ix_users_role")
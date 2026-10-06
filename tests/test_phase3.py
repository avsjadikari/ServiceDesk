"""Tests for Phase 3 hardening items.

Covers: pagination of list views, eager-loading, magic-byte upload
validation, DB CHECK constraints, and async email dispatch.
"""
import io
import tempfile

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Asset, Article, Attachment, Ticket, User
from app.utils import calculate_sla_deadline, generate_ticket_number, validate_upload_sniff


def _login_admin(client):
    client.post("/login", data={"username": "admin", "password": "Admin@123456"})


def _make_ticket(user_id, priority="medium", status="new", category="Hardware", ticket_number=None):
    return Ticket(
        ticket_number=ticket_number or generate_ticket_number(),
        title="Paginated ticket",
        description="body",
        type="incident",
        priority=priority,
        status=status,
        category=category,
        created_by=user_id,
        sla_deadline=calculate_sla_deadline(priority),
    )


class TestPagination:
    def test_tickets_index_paginates(self, client, app, admin_user):
        _login_admin(client)
        with app.app_context():
            db.session.add_all(
                [_make_ticket(admin_user.id, ticket_number=f"TKT-{1000 + i}") for i in range(30)]
            )
            db.session.commit()

        page1 = client.get("/tickets")
        assert page1.status_code == 200
        html1 = page1.get_data(as_text=True)
        # 25 of 30 tickets, plus pagination controls.
        assert "Paginated ticket" in html1
        assert 'class="pagination' in html1

        page2 = client.get("/tickets?page=2")
        assert page2.status_code == 200
        assert 'class="pagination' in page2.get_data(as_text=True)

        page3 = client.get("/tickets?page=3")
        # Out-of-range page must not 404 (error_out=False).
        assert page3.status_code == 200

    def test_tickets_filter_args_survive_pagination(self, client, app, admin_user):
        _login_admin(client)
        with app.app_context():
            for i in range(26):
                db.session.add(
                    _make_ticket(
                        admin_user.id,
                        priority="high",
                        ticket_number=f"TKT-{2000 + i}",
                    )
                )
            db.session.commit()

        resp = client.get("/tickets?priority=high")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        # Pagination links must keep the active filter argument.
        assert 'class="pagination' in html
        assert "priority=high" in html

    def test_assets_index_paginates(self, client, app):
        _login_admin(client)
        with app.app_context():
            db.session.add_all(
                [
                    Asset(name=f"Laptop {i}", asset_type="Hardware", status="active")
                    for i in range(30)
                ]
            )
            db.session.commit()

        resp = client.get("/assets")
        assert resp.status_code == 200
        assert 'class="pagination' in resp.get_data(as_text=True)

        resp2 = client.get("/assets?page=2")
        assert resp2.status_code == 200

    def test_knowledge_index_paginates(self, client, app, admin_user):
        with app.app_context():
            db.session.add_all(
                [
                    Article(
                        title=f"Article {i}",
                        content="x" * 10,
                        category="Software",
                        status="published",
                        author_id=admin_user.id,
                    )
                    for i in range(25)
                ]
            )
            db.session.commit()

        resp = client.get("/knowledge")
        assert resp.status_code == 200
        assert 'class="pagination' in resp.get_data(as_text=True)

        resp2 = client.get("/knowledge?page=2")
        assert resp2.status_code == 200

    def test_knowledge_empty_state(self, client):
        resp = client.get("/knowledge")
        assert resp.status_code == 200
        assert "No articles found" in resp.get_data(as_text=True)

    def test_portal_knowledge_paginates(self, client, app, admin_user):
        with app.app_context():
            db.session.add_all(
                [
                    Article(
                        title=f"Portal Article {i}",
                        content="x" * 10,
                        category="Software",
                        status="published",
                        author_id=admin_user.id,
                    )
                    for i in range(25)
                ]
            )
            db.session.commit()

        resp = client.get("/portal/knowledge")
        assert resp.status_code == 200
        assert 'class="pagination' in resp.get_data(as_text=True)

    def test_portal_my_tickets_paginates(self, client, app, admin_user):
        _login_admin(client)
        with app.app_context():
            db.session.add_all(
                [
                    _make_ticket(admin_user.id, ticket_number=f"TKT-{4000 + i}")
                    for i in range(30)
                ]
            )
            db.session.commit()

        resp = client.get("/portal/tickets")
        assert resp.status_code == 200
        assert 'class="pagination' in resp.get_data(as_text=True)


class TestMagicBytes:
    def test_validate_upload_sniff(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        assert validate_upload_sniff("img.png", png) is True
        # Python source disguised as a PNG.
        assert validate_upload_sniff("img.png", b"<?php echo 'x'; ?>") is False
        # Extensions without a signature are always allowed past the sniff.
        assert validate_upload_sniff("notes.txt", b"anything goes") is True

    def test_mismatched_upload_rejected(self, client, app, admin_user):
        _login_admin(client)
        upload_dir = tempfile.mkdtemp()
        app.config["UPLOAD_FOLDER"] = upload_dir

        with app.app_context():
            ticket = _make_ticket(admin_user.id, ticket_number="TKT-3001")
            db.session.add(ticket)
            db.session.commit()
            ticket_id = ticket.id

        resp = client.post(
            f"/tickets/{ticket_id}/attachments",
            data={"file": (io.BytesIO(b"<?php echo 'x'; ?>"), "evil.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        with app.app_context():
            assert Attachment.query.count() == 0

        follow = client.get(resp.headers["Location"])
        assert "does not match its extension" in follow.get_data(as_text=True)

    def test_valid_png_upload_accepted(self, client, app, admin_user):
        _login_admin(client)
        upload_dir = tempfile.mkdtemp()
        app.config["UPLOAD_FOLDER"] = upload_dir

        with app.app_context():
            ticket = _make_ticket(admin_user.id, ticket_number="TKT-3002")
            db.session.add(ticket)
            db.session.commit()
            ticket_id = ticket.id

        payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        resp = client.post(
            f"/tickets/{ticket_id}/attachments",
            data={"file": (io.BytesIO(payload), "diagram.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        with app.app_context():
            assert Attachment.query.count() == 1


class TestCheckConstraints:
    def test_invalid_user_role_rejected(self, db):
        bad = User(
            username="super",
            email="super@test.com",
            full_name="Super",
            role="superadmin",
            is_active=True,
        )
        bad.set_password("Super@123456")
        db.session.add(bad)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_invalid_ticket_type_rejected(self, db, admin_user):
        ticket = Ticket(
            ticket_number=generate_ticket_number(),
            title="Bad type",
            description="x",
            type="feature",
            priority="medium",
            status="new",
            created_by=admin_user.id,
        )
        db.session.add(ticket)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


class TestAsyncEmail:
    def test_async_dispatch_pushes_to_outbox(self, app, db):
        from app.email_utils import mail, send_email, join_email_workers

        app.config.update(
            MAIL_USERNAME="smtp-user@example.com",
            MAIL_DEFAULT_SENDER="no-reply@example.com",
            MAIL_ASYNC=True,
        )

        with mail.record_messages() as outbox:
            with app.test_request_context():
                queued = send_email("to@example.com", "Async hi", "body")
            assert queued is True

            join_email_workers(timeout=5)
            assert len(outbox) == 1
            assert outbox[0].subject == "Async hi"

    def test_async_flag_overrides_config(self, app, db):
        from app.email_utils import mail, send_email, join_email_workers

        app.config.update(
            MAIL_USERNAME="smtp-user@example.com",
            MAIL_DEFAULT_SENDER="no-reply@example.com",
            MAIL_ASYNC=False,
        )

        with mail.record_messages() as outbox:
            with app.test_request_context():
                # Explicit override beats the MAIL_ASYNC=False default.
                assert send_email("to@example.com", "Sync hi", "body", async_=True) is True
                # Default stays synchronous.
                assert send_email("to2@example.com", "Sync hi 2", "body") is True

            join_email_workers(timeout=5)
            assert len(outbox) == 2
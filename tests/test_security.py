import pytest


def _login_admin(client):
    client.post("/login", data={"username": "admin", "password": "Admin@123456"})


class TestApiTicketEnums:
    def test_api_enums_match_db_enums(self, app):
        import app.routes.api as api_module

        from app.enums import (
            TICKET_PRIORITIES,
            TICKET_STATUSES,
            TICKET_TYPES,
        )

        assert api_module.VALID_TICKET_TYPES == set(TICKET_TYPES)
        assert api_module.VALID_TICKET_STATUSES == set(TICKET_STATUSES)
        assert api_module.VALID_TICKET_PRIORITIES == set(TICKET_PRIORITIES)

    def test_create_ticket_accepts_db_valid_type(self, client, app, admin_user):
        _login_admin(client)
        resp = client.post(
            "/api/tickets",
            json={
                "title": "Printer jammed",
                "type": "request",
                "priority": "medium",
                "description": "Laser printer misfeeds paper.",
            },
        )
        assert resp.status_code == 201

    def test_create_ticket_rejects_mismatched_type(self, client, app, admin_user):
        _login_admin(client)
        resp = client.post(
            "/api/tickets",
            json={"title": "Nope", "type": "service_request", "priority": "low"},
        )
        assert resp.status_code == 400
        assert b"Invalid type" in resp.data

    def test_update_ticket_accepts_db_valid_status(
        self, client, app, db, admin_user
    ):
        from app.models import Ticket
        from app.utils import generate_ticket_number

        _login_admin(client)

        ticket = Ticket(
            ticket_number=generate_ticket_number(),
            title="Needs assignment",
            description="",
            type="incident",
            priority="high",
            created_by=1,
        )
        db.session.add(ticket)
        db.session.commit()

        resp = client.put(
            f"/api/tickets/{ticket.id}", json={"status": "assigned"}
        )
        assert resp.status_code == 200
        db.session.refresh(ticket)
        assert ticket.status == "assigned"

    def test_update_ticket_rejects_mismatched_status(
        self, client, app, db, admin_user
    ):
        from app.models import Ticket
        from app.utils import generate_ticket_number

        _login_admin(client)

        ticket = Ticket(
            ticket_number=generate_ticket_number(),
            title="Needs assignment",
            description="",
            type="incident",
            priority="high",
            created_by=1,
        )
        db.session.add(ticket)
        db.session.commit()

        resp = client.put(
            f"/api/tickets/{ticket.id}", json={"status": "open"}
        )
        assert resp.status_code == 400
        assert b"Invalid status" in resp.data


class TestResetLinkHost:
    def test_reset_link_uses_configured_server_name(self, app, db, monkeypatch):
        from app import email_utils
        from app.models import User

        app.config["SERVER_NAME"] = "servicedesk.example.com"

        user = User(
            username="bob",
            email="bob@test.com",
            full_name="Bob",
            role="user",
            is_active=True,
        )
        user.set_password("Strong@Pass1")
        db.session.add(user)
        db.session.commit()

        captured = {}

        def fake_send(user_, url):
            captured["url"] = url
            return True

        monkeypatch.setattr(email_utils, "send_password_reset", fake_send)

        client = app.test_client()
        resp = client.post(
            "/forgot-password",
            data={"email": "bob@test.com"},
            headers={"Host": "evil.example.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "servicedesk.example.com" in captured["url"]
        assert "evil.example.com" not in captured["url"]


class TestSetupWizardGate:
    def test_setup_wizard_accessible_in_dev_without_admin(self, app, db):
        from app.models import User

        assert User.query.count() == 0
        client = app.test_client()
        resp = client.get("/setup")
        assert resp.status_code == 200
        assert b"Setup Wizard" in resp.data

    def test_setup_requires_token_in_production(self, app, db, monkeypatch):
        from app.models import User

        monkeypatch.setenv("FLASK_CONFIG", "production")
        app.config["SETUP_TOKEN"] = "super-secret-token"

        client = app.test_client()
        resp = client.get("/setup")
        assert resp.status_code == 200

        form_data = {
            "setup_token": "wrong-token",
            "company_name": "ACME",
            "db_type": "sqlite",
            "db_host": "localhost",
            "db_port": "5432",
            "db_name": "servicedesk",
            "db_user": "servicedesk",
            "db_password": "",
            "admin_username": "boss",
            "admin_email": "boss@acme.com",
            "admin_full_name": "Boss",
            "admin_password": "Strong!Passw0rd",
        }
        resp = client.post("/setup", data=form_data)
        assert resp.status_code == 200
        assert User.query.filter_by(username="boss").first() is None

        form_data["setup_token"] = "super-secret-token"
        resp = client.post("/setup", data=form_data)
        assert User.query.filter_by(username="boss").first() is not None

    def test_setup_without_token_configured_is_blocked_in_production(
        self, app, db, monkeypatch
    ):
        from app.models import User

        monkeypatch.setenv("FLASK_CONFIG", "production")
        app.config["SETUP_TOKEN"] = None

        client = app.test_client()
        resp = client.get("/setup")
        assert resp.status_code == 200
        assert b"SETUP_TOKEN" in resp.data

        resp = client.post(
            "/setup",
            data={
                "setup_token": "",
                "company_name": "ACME",
                "db_type": "sqlite",
                "admin_username": "boss2",
                "admin_email": "boss2@acme.com",
                "admin_full_name": "Boss Two",
                "admin_password": "Strong!Passw0rd",
            },
        )
        assert User.query.filter_by(username="boss2").first() is None


class TestStoredXssInlineHandlers:
    USERNAME_PAYLOAD = "x');alert(1)//"
    RESET_CODE_NOSCRIPT = '"><img src=x onerror=alert(1)>'

    def _evil_user(self, db, username, email):
        from app.models import User

        user = User(
            username=username,
            email=email,
            full_name="Evil",
            role="user",
            is_active=True,
        )
        user.set_password("Strong@Pass1")
        db.session.add(user)
        db.session.commit()
        return user

    def test_users_page_has_no_inline_event_handlers(
        self, client, app, db, admin_user
    ):
        self._evil_user(db, self.USERNAME_PAYLOAD, "evil@test.com")
        _login_admin(client)

        resp = client.get("/users")
        assert resp.status_code == 200
        assert b"onsubmit=" not in resp.data
        assert b"confirm('x');alert(1)//" not in resp.data
        assert b'data-username="x&#39;);alert(1)//"' in resp.data

    def test_reset_password_page_has_no_inline_event_handlers(
        self, client, app, db, admin_user
    ):
        evil = self._evil_user(db, self.RESET_CODE_NOSCRIPT, "evil2@test.com")
        _login_admin(client)

        resp = client.get(f"/users/{evil.id}/reset-password")
        assert resp.status_code == 200
        assert b"onclick=" not in resp.data
        assert b"onsubmit=" not in resp.data
        assert b'data-username="&#34;&gt;&lt;img src=x onerror=alert(1)&gt;"' in resp.data
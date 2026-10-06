import pytest
from app.models import Attachment, Ticket, User


class TestTicketCreation:
    """Test ticket creation functionality"""

    def test_create_ticket_as_agent(self, client, app, admin_user):
        """Test agent can create tickets"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.post(
                "/tickets/new",
                data={
                    "title": "Test Ticket",
                    "description": "Test Description",
                    "type": "incident",
                    "priority": "high",
                    "category": "Hardware",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

            ticket = Ticket.query.filter_by(title="Test Ticket").first()
            assert ticket is not None
            assert ticket.priority == "high"

    def test_create_ticket_as_user(self, client, app, regular_user):
        """Test regular user can create tickets"""
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            response = client.post(
                "/tickets/new",
                data={
                    "title": "User Ticket",
                    "description": "User Issue",
                    "type": "request",
                    "priority": "medium",
                    "category": "Software",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_ticket_number_generation(self, client, app, admin_user):
        """Test ticket number is generated correctly"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            client.post(
                "/tickets/new",
                data={
                    "title": "Ticket 1",
                    "description": "Description",
                    "type": "incident",
                    "priority": "medium",
                    "category": "Hardware",
                },
            )

            ticket = Ticket.query.first()
            assert ticket.ticket_number is not None
            assert ticket.ticket_number.startswith("TKT-")


class TestTicketAccess:
    """Test ticket access control"""

    def test_user_can_view_own_ticket(self, client, app, db, regular_user):
        """Test user can view their own ticket"""
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})

            ticket = Ticket(
                ticket_number="TKT-000001",
                title="Test",
                description="Test",
                created_by=regular_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.get(f"/tickets/{ticket.id}")
            assert response.status_code == 200

    def test_user_cannot_view_others_ticket(
        self, client, app, db, regular_user, admin_user
    ):
        """Test user cannot view other users' tickets"""
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})

            ticket = Ticket(
                ticket_number="TKT-000002",
                title="Admin Ticket",
                description="Admin Issue",
                created_by=admin_user.id,
                type="incident",
                priority="high",
                category="Software",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.get(f"/tickets/{ticket.id}")
            assert response.status_code == 403

    def test_reporter_can_upload_and_download_attachment(
        self, client, app, db, regular_user
    ):
        """Regression: ``_can_view_ticket`` referenced the non-existent
        ``reporter_id`` attribute (the column is ``created_by``), so every
        non-agent upload/download raised AttributeError and returned 500."""
        import io

        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})

            ticket = Ticket(
                ticket_number="TKT-000900",
                title="Test",
                description="Test",
                created_by=regular_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/attachments",
                data={"file": (io.BytesIO(b"attachment content"), "note.txt")},
                content_type="multipart/form-data",
                follow_redirects=False,
            )
            assert response.status_code == 302

            attachment = Attachment.query.filter_by(ticket_id=ticket.id).first()
            assert attachment is not None

            response = client.get(f"/attachments/{attachment.id}")
            assert response.status_code == 200
            assert response.data == b"attachment content"


class TestTicketStatus:
    """Test ticket status management"""

    def test_update_ticket_status(self, client, app, db, admin_user):
        """Test agent can update ticket status"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            ticket = Ticket(
                ticket_number="TKT-000003",
                title="Test",
                description="Test",
                created_by=admin_user.id,
                status="new",
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/update-status",
                data={"status": "in_progress"},
                follow_redirects=True,
            )

            assert response.status_code == 200

            ticket = Ticket.query.get(ticket.id)
            assert ticket.status == "in_progress"


class TestTicketComments:
    """Test ticket commenting"""

    def test_add_comment_to_ticket(self, client, app, db, admin_user):
        """Test adding comment to ticket"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            ticket = Ticket(
                ticket_number="TKT-000004",
                title="Test",
                description="Test",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/comment",
                data={"content": "Test comment", "is_internal": "false"},
                follow_redirects=True,
            )

            assert response.status_code == 200


class TestTicketAssignment:
    """Test ticket assignment"""

    def test_assign_ticket_to_agent(self, client, app, db, admin_user, agent_user):
        """Test assigning ticket to agent"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            ticket = Ticket(
                ticket_number="TKT-000005",
                title="Test",
                description="Test",
                created_by=admin_user.id,
                type="incident",
                priority="high",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/assign",
                data={"assigned_to": str(agent_user.id)},
                follow_redirects=True,
            )

            assert response.status_code == 200

            ticket = Ticket.query.get(ticket.id)
            assert ticket.assigned_to == agent_user.id
            assert ticket.status == "assigned"

    def test_assign_ticket_to_regular_user_rejected(
        self, client, app, db, admin_user, regular_user
    ):
        """Regression: assigning a ticket to a non-agent must be rejected
        instead of silently assigning a regular user."""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            ticket = Ticket(
                ticket_number="TKT-000901",
                title="Test",
                description="Test",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/assign",
                data={"assigned_to": str(regular_user.id)},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"must be an agent or admin" in response.data

            ticket = Ticket.query.get(ticket.id)
            assert ticket.assigned_to is None
            assert ticket.status == "new"

    def test_assign_ticket_to_unknown_user_rejected(
        self, client, app, db, admin_user
    ):
        """Regression: an assignee id with no matching user must not
        raise IntegrityError (500); it redirects with a flash."""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            ticket = Ticket(
                ticket_number="TKT-000902",
                title="Test",
                description="Test",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/assign",
                data={"assigned_to": "999999"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Assignee does not exist" in response.data

            ticket = Ticket.query.get(ticket.id)
            assert ticket.assigned_to is None
            assert ticket.status == "new"

    def test_ticket_view_assign_dropdown_lists_agents(
        self, client, app, db, admin_user, agent_user
    ):
        """Assign dropdown must list agent/admin options.

        Regression: the template iterates ``users`` but the view route
        never passed it, so only "Unassigned" rendered and assignment
        never persisted.
        """
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})

            ticket = Ticket(
                ticket_number="TKT-000006",
                title="Test",
                description="Test",
                created_by=admin_user.id,
                type="incident",
                priority="high",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.get(f"/tickets/{ticket.id}")
            assert response.status_code == 200
            assert f'value="{agent_user.id}"'.encode() in response.data
            assert f'value="{admin_user.id}"'.encode() in response.data


class TestKanbanBoard:
    """Test Kanban board functionality and JSON status update"""

    def test_kanban_board_agent_access(self, client, app, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            response = client.get("/tickets/board")
            assert response.status_code == 200
            assert b"Ticket Workflow Board" in response.data

    def test_kanban_board_user_forbidden(self, client, app, regular_user):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            response = client.get("/tickets/board")
            assert response.status_code == 403

    def test_kanban_json_status_update(self, client, app, db, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            ticket = Ticket(
                ticket_number="TKT-000099",
                title="Kanban Test",
                description="Test Drag and Drop",
                created_by=admin_user.id,
                type="incident",
                priority="high",
                category="Hardware",
                status="new",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/update-status",
                json={"status": "in_progress"},
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["status"] == "in_progress"

            updated_ticket = Ticket.query.get(ticket.id)
            assert updated_ticket.status == "in_progress"
            assert updated_ticket.first_response_at is not None

    def test_ticket_list_with_sla_deadlines(self, client, app, db, admin_user):
        """Test tickets index renders properly with tickets having SLA deadlines"""
        from datetime import datetime, timedelta
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            ticket = Ticket(
                ticket_number="TKT-000777",
                title="SLA Test",
                description="Test SLA deadline rendering",
                created_by=admin_user.id,
                type="incident",
                priority="high",
                category="Hardware",
                status="in_progress",
                sla_deadline=datetime.utcnow() + timedelta(hours=2),
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.get("/tickets?status=in_progress")
            assert response.status_code == 200
            assert b"TKT-000777" in response.data

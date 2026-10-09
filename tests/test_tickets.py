import pytest
from unittest.mock import patch
from app.models import Attachment, Comment, Ticket, User


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


class TestIndexFilters:
    """Characterize /tickets index filter branches (index:51,63,65)."""

    def test_user_index_shows_only_own_tickets(
        self, client, app, db, regular_user, admin_user
    ):
        """Regular user hits the created_by branch: foreign tickets hidden."""
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            db.session.add_all(
                [
                    Ticket(
                        ticket_number="TKT-200001",
                        title="Own ticket",
                        description="d",
                        created_by=regular_user.id,
                        type="incident",
                        priority="medium",
                        category="Hardware",
                    ),
                    Ticket(
                        ticket_number="TKT-200002",
                        title="Foreign ticket",
                        description="d",
                        created_by=admin_user.id,
                        type="incident",
                        priority="medium",
                        category="Hardware",
                    ),
                ]
            )
            db.session.commit()

            response = client.get("/tickets")
            assert response.status_code == 200
            assert b"TKT-200001" in response.data
            assert b"TKT-200002" not in response.data

    def test_index_category_filter(self, client, app, db, admin_user):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            db.session.add_all(
                [
                    Ticket(
                        ticket_number="TKT-200003",
                        title="Hardware ticket",
                        description="d",
                        created_by=admin_user.id,
                        type="incident",
                        priority="medium",
                        category="Hardware",
                    ),
                    Ticket(
                        ticket_number="TKT-200004",
                        title="Software ticket",
                        description="d",
                        created_by=admin_user.id,
                        type="incident",
                        priority="medium",
                        category="Software",
                    ),
                ]
            )
            db.session.commit()

            response = client.get("/tickets?category=Hardware")
            assert response.status_code == 200
            assert b"TKT-200003" in response.data
            assert b"TKT-200004" not in response.data

    def test_index_assigned_to_filter(
        self, client, app, db, admin_user, agent_user
    ):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            db.session.add_all(
                [
                    Ticket(
                        ticket_number="TKT-200005",
                        title="Assigned ticket",
                        description="d",
                        created_by=admin_user.id,
                        assigned_to=agent_user.id,
                        status="assigned",
                        type="incident",
                        priority="medium",
                        category="Hardware",
                    ),
                    Ticket(
                        ticket_number="TKT-200006",
                        title="Unassigned ticket",
                        description="d",
                        created_by=admin_user.id,
                        type="incident",
                        priority="medium",
                        category="Hardware",
                    ),
                ]
            )
            db.session.commit()

            response = client.get(f"/tickets?assigned_to={agent_user.id}")
            assert response.status_code == 200
            assert b"TKT-200005" in response.data
            assert b"TKT-200006" not in response.data

    def test_index_non_numeric_assigned_to_is_ignored(self, client, app, admin_user):
        # FIX (2026-10-08): non-numeric ?assigned_to no longer crashes
        # (was ValueError / 500, Debt Ledger). type=int coerces to None,
        # so the filter is skipped and all tickets render.
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.get("/tickets?assigned_to=abc")
            assert response.status_code == 200


class TestNewTicketBranches:
    """Characterize /tickets/new branches (new:120-121,140)."""

    def test_new_get_renders_form(self, client, app, admin_user):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.get("/tickets/new")
            assert response.status_code == 200
            assert b'name="title"' in response.data

    def test_new_post_invalid_renders_form(self, client, app, admin_user):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.post(
                "/tickets/new",
                data={"title": "", "description": ""},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"This field is required." in response.data

    def test_new_post_with_assignee_sets_assigned_status(
        self, client, app, db, admin_user, agent_user
    ):
        """assigned_to > 0 pins assigned_to and forces status='assigned'."""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.post(
                "/tickets/new",
                data={
                    "title": "Assign on create",
                    "description": "d",
                    "type": "incident",
                    "priority": "high",
                    "category": "Hardware",
                    "assigned_to": str(agent_user.id),
                },
                follow_redirects=False,
            )
            ticket = Ticket.query.filter_by(title="Assign on create").one()
            assert response.status_code == 302
            assert response.headers["Location"].endswith(f"/tickets/{ticket.id}")
            assert ticket.assigned_to == agent_user.id
            assert ticket.status == "assigned"

            page = client.get(response.headers["Location"])
            assert b"created successfully" in page.data


class TestEditRoute:
    """Characterize /tickets/<id>/edit (edit:178-210)."""

    def test_edit_forbidden_for_regular_user(
        self, client, app, db, regular_user, admin_user
    ):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            ticket = Ticket(
                ticket_number="TKT-210001",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            assert client.get(f"/tickets/{ticket.id}/edit").status_code == 403
            assert (
                client.post(
                    f"/tickets/{ticket.id}/edit",
                    data={
                        "title": "x",
                        "description": "x",
                        "type": "incident",
                        "priority": "low",
                        "category": "Other",
                    },
                ).status_code
                == 403
            )

    def test_edit_get_renders_form(self, client, app, db, admin_user):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = Ticket(
                ticket_number="TKT-210002",
                title="Editable",
                description="d",
                created_by=admin_user.id,
                status="new",
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.get(f"/tickets/{ticket.id}/edit")
            assert response.status_code == 200
            assert b"Editable" in response.data

    def test_edit_post_assign_moves_new_to_assigned(
        self, client, app, db, admin_user, agent_user
    ):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = Ticket(
                ticket_number="TKT-210003",
                title="Old title",
                description="old",
                created_by=admin_user.id,
                status="new",
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/edit",
                data={
                    "title": "New title",
                    "description": "new desc",
                    "type": "request",
                    "priority": "low",
                    "category": "Network",
                    "assigned_to": str(agent_user.id),
                },
                follow_redirects=False,
            )
            assert response.status_code == 302
            assert response.headers["Location"].endswith(f"/tickets/{ticket.id}")

            ticket = Ticket.query.get(ticket.id)
            assert ticket.title == "New title"
            assert ticket.type == "request"
            assert ticket.priority == "low"
            assert ticket.category == "Network"
            assert ticket.assigned_to == agent_user.id
            assert ticket.status == "assigned"

            from app.models import AuditLog

            assert (
                AuditLog.query.filter_by(
                    action="update", entity_type="ticket", entity_id=ticket.id
                ).count()
                == 1
            )

            page = client.get(f"/tickets/{ticket.id}")
            assert b"updated successfully" in page.data

    def test_edit_post_assign_keeps_non_new_status(
        self, client, app, db, admin_user, agent_user
    ):
        """Assign via edit only promotes new -> assigned; in_progress kept."""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = Ticket(
                ticket_number="TKT-210004",
                title="In flight",
                description="d",
                created_by=admin_user.id,
                status="in_progress",
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            client.post(
                f"/tickets/{ticket.id}/edit",
                data={
                    "title": "In flight",
                    "description": "d",
                    "type": "incident",
                    "priority": "medium",
                    "category": "Hardware",
                    "assigned_to": str(agent_user.id),
                },
            )
            ticket = Ticket.query.get(ticket.id)
            assert ticket.assigned_to == agent_user.id
            assert ticket.status == "in_progress"

    def test_edit_post_unassign_resets_status_to_new(
        self, client, app, db, admin_user, agent_user
    ):
        # CHARACTERIZED: unassigning (assigned_to=0) resets ANY status to
        # "new" — an in_progress ticket silently loses its workflow state;
        # suspected bug, see TECH-DEBT Debt Ledger
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = Ticket(
                ticket_number="TKT-210005",
                title="Mid work",
                description="d",
                created_by=admin_user.id,
                assigned_to=agent_user.id,
                status="in_progress",
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/edit",
                data={
                    "title": "Mid work",
                    "description": "d",
                    "type": "incident",
                    "priority": "medium",
                    "category": "Hardware",
                    "assigned_to": 0,
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"updated successfully" in response.data

            ticket = Ticket.query.get(ticket.id)
            assert ticket.assigned_to is None
            # CHARACTERIZED → fixed 2026-10-08: unassigning no longer resets a
            # progressed status to "new"; only None/new/assigned tickets
            # regress to "new", in_progress is preserved (unassign doesn't
            # destroy workflow state)
            assert ticket.status == "in_progress"


class TestUpdateStatusBranches:
    """Characterize /tickets/<id>/update-status (update_status:217,230,233,256)."""

    def _make_ticket(self, db, number, status="new", **kw):
        ticket = Ticket(
            ticket_number=number,
            title="Status target",
            description="d",
            created_by=kw.pop("created_by", 1),
            status=status,
            type="incident",
            priority="medium",
            category="Hardware",
            **kw,
        )
        db.session.add(ticket)
        db.session.commit()
        return ticket

    def test_update_status_forbidden_for_regular_user(
        self, client, app, db, regular_user, admin_user
    ):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            ticket = self._make_ticket(db, "TKT-220001", created_by=admin_user.id)
            response = client.post(
                f"/tickets/{ticket.id}/update-status", data={"status": "resolved"}
            )
            assert response.status_code == 403
            assert Ticket.query.get(ticket.id).status == "new"

    def test_update_status_resolved_sets_resolved_at(
        self, client, app, db, admin_user
    ):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._make_ticket(db, "TKT-220002", created_by=admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/update-status",
                data={"status": "resolved"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Ticket status updated to Resolved." in response.data

            ticket = Ticket.query.get(ticket.id)
            assert ticket.status == "resolved"
            assert ticket.resolved_at is not None
            assert ticket.first_response_at is None

            from app.models import AuditLog

            assert (
                AuditLog.query.filter_by(
                    action="status_change", entity_id=ticket.id
                ).count()
                == 1
            )

    def test_update_status_closed_sets_closed_at(self, client, app, db, admin_user):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._make_ticket(db, "TKT-220003", created_by=admin_user.id)

            client.post(
                f"/tickets/{ticket.id}/update-status",
                data={"status": "closed"},
                follow_redirects=True,
            )
            ticket = Ticket.query.get(ticket.id)
            assert ticket.status == "closed"
            assert ticket.closed_at is not None

    def test_update_status_json_invalid_returns_400(
        self, client, app, db, admin_user
    ):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._make_ticket(db, "TKT-220004", created_by=admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/update-status", json={"status": ""}
            )
            assert response.status_code == 400
            assert response.get_json() == {
                "success": False,
                "error": "Invalid status",
            }
            assert Ticket.query.get(ticket.id).status == "new"

    def test_update_status_rejects_bogus_status_value(
        self, client, app, db, admin_user
    ):
        # CHARACTERIZED → fixed 2026-10-08: update_status validates against
        # TICKET_STATUSES before assignment; a bogus status now flashes
        # "Invalid status." and leaves the ticket unchanged instead of
        # surfacing the DB CHECK IntegrityError as an HTTP 500
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._make_ticket(db, "TKT-220005", created_by=admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/update-status",
                data={"status": "bogus"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Invalid status" in response.data
            assert Ticket.query.get(ticket.id).status == "new"


class TestAssignEdges:
    """Characterize /tickets/<id>/assign edge branches (assign:265,273-275)."""

    def test_assign_forbidden_for_regular_user(
        self, client, app, db, regular_user, admin_user
    ):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            ticket = Ticket(
                ticket_number="TKT-230001",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/assign", data={"assigned_to": str(admin_user.id)}
            )
            assert response.status_code == 403
            assert Ticket.query.get(ticket.id).assigned_to is None

    def test_assign_non_numeric_assignee_flashes_invalid(
        self, client, app, db, admin_user
    ):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = Ticket(
                ticket_number="TKT-230002",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/assign",
                data={"assigned_to": "xyz"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Invalid assignee." in response.data
            assert Ticket.query.get(ticket.id).assigned_to is None


class TestCommentAuthz:
    """Characterize /tickets/<id>/comment authz (add_comment:317)."""

    def test_comment_forbidden_on_other_users_ticket(
        self, client, app, db, regular_user, admin_user
    ):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            ticket = Ticket(
                ticket_number="TKT-240001",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/comment", data={"content": "hello"}
            )
            assert response.status_code == 403

            from app.models import Comment

            assert Comment.query.filter_by(ticket_id=ticket.id).count() == 0


class TestAutomationAssign:
    """Characterize automation assign semantics (utils._execute_automation_rule)."""

    def test_automation_assign_resets_in_progress_to_assigned(
        self, client, app, db, admin_user, agent_user
    ):
        # CHARACTERIZED → fixed 2026-10-08: automation assign reuses
        # Ticket.promote_status_if_new() — an in_progress ticket keeps its
        # workflow state; only None/"new" tickets move to "assigned" (was:
        # unconditional reset to "assigned")
        from app.models import AutomationRule
        from app.utils import _execute_automation_rule

        with app.app_context():
            rule = AutomationRule(
                name="auto-assign",
                trigger_type="ticket_created",
                action_type="assign",
                action_config={"assign_to": agent_user.id},
                is_active=True,
                priority=10,
            )
            db.session.add(rule)
            db.session.commit()

            ticket = Ticket(
                ticket_number="TKT-300001",
                title="Automation target",
                description="d",
                created_by=admin_user.id,
                status="in_progress",
                assigned_to=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            _execute_automation_rule(ticket, rule)
            assert ticket.status == "in_progress"
            assert ticket.assigned_to == agent_user.id


class TestLinkAsset:
    """Characterize /tickets/<id>/link-asset (link_asset:344-365)."""

    def test_link_asset_forbidden_for_regular_user(
        self, client, app, db, regular_user, admin_user
    ):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            ticket = Ticket(
                ticket_number="TKT-250001",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/link-asset", data={"asset_id": "1"}
            )
            assert response.status_code == 403
            assert Ticket.query.get(ticket.id).asset_id is None

    def test_link_asset_success(self, client, app, db, admin_user):
        from app.models import Asset, AuditLog

        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            asset = Asset(name="Laptop-1", asset_type="laptop", status="active")
            db.session.add(asset)
            db.session.commit()
            ticket = Ticket(
                ticket_number="TKT-250002",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/link-asset",
                data={"asset_id": str(asset.id)},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Asset linked successfully." in response.data
            assert Ticket.query.get(ticket.id).asset_id == asset.id
            assert (
                AuditLog.query.filter_by(action="link_asset", entity_id=ticket.id)
                .count()
                == 1
            )

    def test_link_asset_non_numeric_asset_id_is_rejected(
        self, client, app, db, admin_user
    ):
        # FIX (2026-10-08): non-numeric asset_id no longer crashes
        # (was ValueError / 500, Debt Ledger); now flashes "Invalid asset."
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = Ticket(
                ticket_number="TKT-250003",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/tickets/{ticket.id}/link-asset",
                data={"asset_id": "abc"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Invalid asset." in response.data
            assert Ticket.query.get(ticket.id).asset_id is None


class TestAttachmentBranches:
    """Characterize upload validation branches (upload_attachment:402,406-409,
    418-419,422-431,457-458)."""

    def _ticket(self, db, number, created_by):
        ticket = Ticket(
            ticket_number=number,
            title="Attach target",
            description="d",
            created_by=created_by,
            type="incident",
            priority="medium",
            category="Hardware",
        )
        db.session.add(ticket)
        db.session.commit()
        return ticket

    def test_upload_forbidden_on_other_users_ticket(
        self, client, app, db, regular_user, admin_user
    ):
        import io

        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            ticket = self._ticket(db, "TKT-260001", admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/attachments",
                data={"file": (io.BytesIO(b"x"), "note.txt")},
                content_type="multipart/form-data",
            )
            assert response.status_code == 403
            assert Attachment.query.filter_by(ticket_id=ticket.id).count() == 0

    def test_upload_without_file_field_flashes_form_error(
        self, client, app, db, admin_user
    ):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._ticket(db, "TKT-260002", admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/attachments",
                data={},
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"This field is required." in response.data
            assert Attachment.query.filter_by(ticket_id=ticket.id).count() == 0

    def test_upload_forged_part_content_length_rejected(
        self, client, app, db, admin_user
    ):
        """The in-route size check reads the multipart part's own
        Content-Length header; a part claiming > MAX_CONTENT_LENGTH is
        rejected even though the overall request body is tiny."""
        import io

        from werkzeug.datastructures import FileStorage

        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._ticket(db, "TKT-260003", admin_user.id)
            fs = FileStorage(
                io.BytesIO(b"tiny"), filename="ok.txt", content_length=99999999
            )

            response = client.post(
                f"/tickets/{ticket.id}/attachments",
                data={"file": (fs, "ok.txt")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"File is too large." in response.data
            assert Attachment.query.filter_by(ticket_id=ticket.id).count() == 0

    def test_upload_disallowed_extension_rejected(
        self, client, app, db, admin_user
    ):
        import io

        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._ticket(db, "TKT-260004", admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/attachments",
                data={"file": (io.BytesIO(b"MZ"), "evil.exe")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"This file type is not allowed." in response.data
            assert Attachment.query.filter_by(ticket_id=ticket.id).count() == 0

    def test_upload_filename_without_extension_rejected(
        self, client, app, db, admin_user
    ):
        import io

        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._ticket(db, "TKT-260005", admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/attachments",
                data={"file": (io.BytesIO(b"data"), "README")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"This file type is not allowed." in response.data
            assert Attachment.query.filter_by(ticket_id=ticket.id).count() == 0

    def test_upload_mime_prefix_mismatch_rejected(
        self, client, app, db, admin_user
    ):
        import io

        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._ticket(db, "TKT-260006", admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/attachments",
                data={
                    "file": (
                        io.BytesIO(b"MZ\x90\x00"),
                        "note.txt",
                        "application/x-msdownload",
                    )
                },
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"This file type is not allowed." in response.data
            assert Attachment.query.filter_by(ticket_id=ticket.id).count() == 0

    def test_upload_path_traversal_guard_rejects(
        self, client, app, db, admin_user, tmp_path
    ):
        """Defense-in-depth: if the generated unique name escaped the upload
        dir, the realpath check flashes 'Invalid filename.' and saves nothing."""
        import io
        from types import SimpleNamespace
        from unittest import mock

        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._ticket(db, "TKT-260007", admin_user.id)
            app.config["UPLOAD_FOLDER"] = str(tmp_path)

            with mock.patch(
                "app.routes.tickets.uuid.uuid4",
                return_value=SimpleNamespace(hex="../escaped"),
            ):
                response = client.post(
                    f"/tickets/{ticket.id}/attachments",
                    data={"file": (io.BytesIO(b"payload"), "note.txt")},
                    content_type="multipart/form-data",
                    follow_redirects=True,
                )
            assert response.status_code == 200
            assert b"Invalid filename." in response.data
            assert Attachment.query.filter_by(ticket_id=ticket.id).count() == 0
            assert not (tmp_path.parent / "escaped_note.txt").exists()

    def test_upload_non_file_value_flashes_invalid(self, client, app, db, admin_user):
        # CHARACTERIZED → fixed 2026-10-08: a plain form field named 'file'
        # (a str, not multipart FileStorage) now flashes "Invalid file."
        # instead of raising AttributeError on .filename (HTTP 500)
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = self._ticket(db, "TKT-260008", admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/attachments",
                data={"file": "not-a-file"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Invalid file" in response.data
            assert Attachment.query.filter_by(ticket_id=ticket.id).count() == 0


class TestLargeRequestHandling:
    """RequestEntityTooLarge → friendly redirect/flash or JSON 413."""

    def test_oversize_upload_redirects_with_flash(self, client, app, db, admin_user):
        with app.app_context():
            app.config["MAX_CONTENT_LENGTH"] = 1024
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = Ticket(
                ticket_number="TKT-310001",
                title="Big upload",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            bulk = b"x" * 4096
            raw = (
                b"--boundary\r\n"
                b'Content-Disposition: form-data; name="file"; filename="big.bin"\r\n'
                b"Content-Type: application/octet-stream\r\n\r\n"
                + bulk
                + b"\r\n--boundary--\r\n"
            )
            response = client.post(
                f"/tickets/{ticket.id}/attachments",
                data=raw,
                content_type="multipart/form-data; boundary=boundary",
                headers={"Referer": f"http://localhost/tickets/{ticket.id}"},
            )
            assert response.status_code == 302
            assert f"/tickets/{ticket.id}" in response.headers["Location"]
            page = client.get(f"/tickets/{ticket.id}")
            assert page.status_code == 200
            assert b"too large" in page.data.lower()

    def test_oversize_api_body_returns_json_413(self, client, app, admin_user):
        with app.app_context():
            app.config["MAX_CONTENT_LENGTH"] = 1024
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.post(
                "/api/tickets",
                json={"title": "y" * 2048, "description": "d"},
            )
            assert response.status_code == 413
            assert response.get_json()["error"]


class TestDownloadBranches:
    """Characterize /attachments/<id> (download_attachment:492,498-501,503)."""

    def _attachment(self, db, ticket_id, uploader, filename, filepath):
        attachment = Attachment(
            ticket_id=ticket_id,
            filename=filename,
            filepath=filepath,
            file_size=4,
            mime_type="text/plain",
            uploaded_by=uploader,
        )
        db.session.add(attachment)
        db.session.commit()
        return attachment

    def test_download_forbidden_on_other_users_ticket(
        self, client, app, db, regular_user, admin_user
    ):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            ticket = Ticket(
                ticket_number="TKT-270001",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()
            attachment = self._attachment(
                db, ticket.id, admin_user.id, "secret.txt", "secret.txt"
            )

            response = client.get(f"/attachments/{attachment.id}")
            assert response.status_code == 403

    def test_download_path_traversal_in_db_returns_404(
        self, client, app, db, admin_user
    ):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = Ticket(
                ticket_number="TKT-270002",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()
            attachment = self._attachment(
                db, ticket.id, admin_user.id, "evil.txt", "../evil.txt"
            )

            response = client.get(f"/attachments/{attachment.id}")
            assert response.status_code == 404

    def test_download_missing_file_returns_404(
        self, client, app, db, admin_user
    ):
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            ticket = Ticket(
                ticket_number="TKT-270003",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()
            attachment = self._attachment(
                db, ticket.id, admin_user.id, "gone.txt", "missing_upload_xyz.txt"
            )

            response = client.get(f"/attachments/{attachment.id}")
            assert response.status_code == 404


class TestCanViewTicketHelper:
    """Pin _can_view_ticket's anonymous branch (tickets:371-372).

    No route reaches it (all callers sit behind @login_required), so it is
    exercised directly in a bare request context before any login occurs.
    """

    def test_anonymous_returns_false(self, app, db, admin_user):
        from app.routes.tickets import _can_view_ticket

        with app.app_context():
            ticket = Ticket(
                ticket_number="TKT-280001",
                title="Test",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Hardware",
            )
            db.session.add(ticket)
            db.session.commit()

            with app.test_request_context():
                assert _can_view_ticket(ticket) is False


class TestEmailSendGuards:
    """FIX (2026-10-08): a failing email send must not fail the request
    (was unguarded -> HTTP 500 after commit, Debt Ledger). Routes now
    route email through _notify(), which catches and logs."""

    def _login(self, client):
        client.post("/login", data={"username": "admin", "password": "Admin@123456"})

    def test_create_ticket_email_failure_still_redirects(self, client, app, db, admin_user):
        with app.app_context():
            self._login(client)
            with patch("app.email_utils.send_ticket_created", side_effect=Exception("SMTP down")):
                response = client.post(
                    "/tickets/new",
                    data={
                        "title": "Email-fail ticket",
                        "description": "d",
                        "type": "incident",
                        "priority": "medium",
                        "category": "Hardware",
                    },
                )
            assert response.status_code == 302
            assert Ticket.query.filter_by(title="Email-fail ticket").count() == 1

    def test_comment_email_failure_still_redirects(self, client, app, db, admin_user):
        with app.app_context():
            self._login(client)
            ticket = Ticket(
                ticket_number="TKT-290001",
                title="Comment target",
                description="d",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
            )
            db.session.add(ticket)
            db.session.commit()
            with patch("app.email_utils.send_ticket_comment", side_effect=Exception("SMTP down")):
                response = client.post(
                    f"/tickets/{ticket.id}/comment",
                    data={"content": "a note"},
)
            assert response.status_code == 302
            assert Comment.query.filter_by(ticket_id=ticket.id).count() == 1


class TestErrorFeedback:
    """K4/K5/K6: silent-failure and no-undo paths on the agent workflow."""

    def _make_ticket(self, db, created_by):
        ticket = Ticket(
            ticket_number="TKT-300001",
            title="Feedback test",
            description="d",
            created_by=created_by,
            type="incident",
            priority="medium",
            category="Hardware",
        )
        db.session.add(ticket)
        db.session.commit()
        return ticket

    def test_empty_comment_flashes_error(self, client, app, db, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            ticket = self._make_ticket(db, admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/comment",
                data={"content": "  "},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Comment cannot be empty." in response.data
            assert Comment.query.filter_by(ticket_id=ticket.id).count() == 0

    def test_edit_empty_title_shows_field_error(self, client, app, db, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            ticket = self._make_ticket(db, admin_user.id)

            response = client.post(
                f"/tickets/{ticket.id}/edit",
                data={
                    "title": "",
                    "description": "",
                    "type": "incident",
                    "priority": "medium",
                    "category": "Hardware",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"This field is required." in response.data

    def test_status_and_assign_require_explicit_apply(self, client, app, db, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            ticket = self._make_ticket(db, admin_user.id)

            response = client.get(f"/tickets/{ticket.id}")
            assert b"onchange" not in response.data
            assert response.data.count(b"Apply") == 2

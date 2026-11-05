import pytest
from app.models import Asset, User


class TestAssetManagement:
    """Test asset management functionality"""

    def test_assets_index_page(self, client):
        """Test assets index page loads"""
        response = client.get("/assets")
        assert response.status_code in [200, 302]

    def test_create_asset_as_agent(self, client, app, admin_user):
        """Test agent can create assets"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.post(
                "/assets/new",
                data={
                    "name": "Dell Laptop XPS 15",
                    "asset_type": "hardware",
                    "serial_number": "SN123456",
                    "model": "XPS 15",
                    "manufacturer": "Dell",
                    "location": "Office A",
                    "status": "active",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

            asset = Asset.query.filter_by(name="Dell Laptop XPS 15").first()
            assert asset is not None
            assert asset.serial_number == "SN123456"

    def test_view_asset(self, client, app, db, admin_user):
        """Test viewing asset details"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            asset = Asset(
                name="Test Asset",
                asset_type="hardware",
                serial_number="TEST001",
                status="active",
            )
            db.session.add(asset)
            db.session.commit()

            response = client.get(f"/assets/{asset.id}")
            assert response.status_code == 200

    def test_edit_asset(self, client, app, db, admin_user):
        """Test editing an asset"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            asset = Asset(
                name="Original Name",
                asset_type="hardware",
                serial_number="ORIG001",
                status="active",
            )
            db.session.add(asset)
            db.session.commit()

            response = client.post(
                f"/assets/{asset.id}/edit",
                data={
                    "name": "Updated Name",
                    "asset_type": "hardware",
                    "serial_number": "ORIG001",
                    "model": "",
                    "manufacturer": "",
                    "assigned_to": "",
                    "location": "Office B",
                    "status": "maintenance",
                    "notes": "",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

            asset = Asset.query.get(asset.id)
            assert asset.name == "Updated Name"
            assert asset.status == "maintenance"

    def test_assign_asset_to_user(self, client, app, db, admin_user, regular_user):
        """Test assigning asset to user"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            asset = Asset(
                name="Unassigned Laptop",
                asset_type="hardware",
                serial_number="ASSIGN001",
                status="available",
            )
            db.session.add(asset)
            db.session.commit()

            response = client.post(
                f"/assets/{asset.id}/edit",
                data={
                    "name": "Unassigned Laptop",
                    "asset_type": "hardware",
                    "serial_number": "ASSIGN001",
                    "model": "",
                    "manufacturer": "",
                    "assigned_to": str(regular_user.id),
                    "location": "",
                    "status": "active",
                    "notes": "",
                },
                follow_redirects=True,
            )

            assert response.status_code == 200

            asset = Asset.query.get(asset.id)
            assert asset.assigned_to == regular_user.id
            assert asset.status == "active"


    def test_delete_asset_with_linked_tickets(self, client, app, db, admin_user):
        """Test deleting asset safely unlinks tickets referencing it"""
        from app.models import Ticket

        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            asset = Asset(
                name="Server Rack A",
                asset_type="hardware",
                serial_number="SRV-RACK-01",
                status="active",
            )
            db.session.add(asset)
            db.session.commit()

            ticket = Ticket(
                ticket_number="TKT-999001",
                title="Rack overheating",
                description="Needs cooling check",
                type="incident",
                priority="high",
                created_by=admin_user.id,
                asset_id=asset.id,
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.post(
                f"/assets/{asset.id}/delete",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Asset deleted successfully." in response.data

            assert Asset.query.get(asset.id) is None
            updated_ticket = Ticket.query.get(ticket.id)
            assert updated_ticket is not None
            assert updated_ticket.asset_id is None

    def test_assign_and_unassign_asset_with_audit(
        self, client, app, db, admin_user, regular_user
    ):
        """Test assigning and unassigning asset creates audit records"""
        from app.models import AuditLog

        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )

            asset = Asset(
                name="Workstation 12",
                asset_type="hardware",
                serial_number="WS-12",
                status="active",
            )
            db.session.add(asset)
            db.session.commit()

            # Assign
            res = client.post(
                f"/assets/{asset.id}/assign",
                data={"user_id": str(regular_user.id)},
                follow_redirects=True,
            )
            assert res.status_code == 200
            assert Asset.query.get(asset.id).assigned_to == regular_user.id

            assign_log = (
                AuditLog.query.filter_by(action="assign_asset", entity_id=asset.id)
                .first()
            )
            assert assign_log is not None
            assert assign_log.details["assigned_to"] == regular_user.id

            # Unassign with empty string
            res = client.post(
                f"/assets/{asset.id}/assign",
                data={"user_id": ""},
                follow_redirects=True,
            )
            assert res.status_code == 200
            assert Asset.query.get(asset.id).assigned_to is None

            unassign_log = (
                AuditLog.query.filter_by(action="unassign_asset", entity_id=asset.id)
                .first()
            )
            assert unassign_log is not None
            assert unassign_log.details["previous_assigned_to"] == regular_user.id

    def test_asset_form_excludes_inactive_users(
        self, client, app, db, admin_user, regular_user
    ):
        """Test asset create form excludes inactive/disabled users"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            disabled_user = User(
                username="disabled_test_user",
                email="disabled@servicedesk.local",
                full_name="Disabled Person",
                role="user",
                is_active=False,
            )
            disabled_user.set_password("Pass@123456")
            db.session.add(disabled_user)
            db.session.commit()

            response = client.get("/assets/new")
            assert response.status_code == 200
            assert b"Disabled Person" not in response.data
            assert regular_user.full_name.encode() in response.data

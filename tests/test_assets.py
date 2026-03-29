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

    def test_view_asset(self, client, app, admin_user):
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
            app.db.session.add(asset)
            app.db.session.commit()

            response = client.get(f"/assets/{asset.id}")
            assert response.status_code == 200

    def test_edit_asset(self, client, app, admin_user):
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
            app.db.session.add(asset)
            app.db.session.commit()

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

    def test_assign_asset_to_user(self, client, app, admin_user, regular_user):
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
            app.db.session.add(asset)
            app.db.session.commit()

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

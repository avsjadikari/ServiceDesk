from app.models import Ticket, User


class TestAnalyticsDashboard:
    """Test Analytics and Operational Dashboard routes and APIs"""

    def test_analytics_agent_access(self, client, app, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            response = client.get("/analytics")
            assert response.status_code == 200
            assert b"Service Desk Analytics" in response.data

    def test_analytics_user_forbidden(self, client, app, regular_user):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            response = client.get("/analytics")
            assert response.status_code == 403

    def test_analytics_tickets_api(self, client, app, db, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            ticket = Ticket(
                ticket_number="TKT-000888",
                title="Analytics Test Ticket",
                description="Testing trend",
                created_by=admin_user.id,
                type="incident",
                priority="medium",
                category="Software",
                status="new",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.get("/analytics/tickets?days=7")
            assert response.status_code == 200
            data = response.get_json()
            assert "labels" in data
            assert "created" in data
            assert "resolved" in data
            assert len(data["labels"]) == 8  # 7 days + today

    def test_analytics_categories_api(self, client, app, db, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            ticket = Ticket(
                ticket_number="TKT-000889",
                title="Category Test Ticket",
                description="Testing categories",
                created_by=admin_user.id,
                type="incident",
                priority="low",
                category="Network",
                status="new",
            )
            db.session.add(ticket)
            db.session.commit()

            response = client.get("/analytics/categories")
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)
            assert any(item["category"] == "Network" for item in data)

    def test_analytics_sla_api(self, client, app, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            response = client.get("/analytics/sla")
            assert response.status_code == 200
            data = response.get_json()
            assert "compliance_rate" in data
            assert "mttr_hours" in data
            assert "active_breached" in data

    def test_main_dashboard_operational_view(self, client, app, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            response = client.get("/dashboard")
            assert response.status_code == 200
            assert b"Operational Dashboard" in response.data
            assert b"14-Day Activity Trend" in response.data

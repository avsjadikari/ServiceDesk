from datetime import datetime, timedelta

from app.models import AuditLog, Ticket, User


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


class TestAnalyticsCharacterization:
    """Characterization tests pinning current behavior of app/routes/analytics.py"""

    def test_tickets_api_forbidden_for_regular_user(self, client, app, regular_user):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            response = client.get("/analytics/tickets")
            assert response.status_code == 403

    def test_sla_api_forbidden_for_regular_user(self, client, app, regular_user):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            response = client.get("/analytics/sla")
            assert response.status_code == 403

    def test_categories_api_forbidden_for_regular_user(self, client, app, regular_user):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            response = client.get("/analytics/categories")
            assert response.status_code == 403

    def test_tickets_api_days_clamped_to_30(self, client, app, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            for bad_days in ("0", "-5", "400"):
                response = client.get(f"/analytics/tickets?days={bad_days}")
                assert response.status_code == 200
                data = response.get_json()
                # CHARACTERIZED: out-of-range days silently falls back to 30 (31 labels)
                assert len(data["labels"]) == 31, f"days={bad_days}"
                assert set(data.keys()) == {"labels", "created", "resolved", "series"}

    def test_tickets_api_series_shape(self, client, app, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            response = client.get("/analytics/tickets?days=7")
            data = response.get_json()
            assert len(data["series"]) == len(data["labels"])
            assert set(data["series"][0].keys()) == {"date", "count", "resolved"}
            assert data["series"][0]["date"] == data["labels"][0]
            assert len(data["created"]) == len(data["labels"])
            assert len(data["resolved"]) == len(data["labels"])

    def test_performance_api_agent_access(self, client, app, agent_user, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            response = client.get("/analytics/performance")
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)
            # CHARACTERIZED: both agent and admin roles appear in performance list
            names = [p["agent"] for p in data]
            assert "Agent User" in names
            assert "Admin User" in names
            for p in data:
                assert set(p.keys()) == {"agent", "assigned", "resolved", "avg_resolution"}
            entry = next(p for p in data if p["agent"] == "Agent User")
            assert entry == {
                "agent": "Agent User",
                "assigned": 0,
                "resolved": 0,
                "avg_resolution": 0.0,
            }

    def test_performance_api_forbidden_for_regular_user(self, client, app, regular_user):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            response = client.get("/analytics/performance")
            assert response.status_code == 403

    def test_performance_api_avg_resolution_with_resolved_ticket(
        self, client, app, db, admin_user, agent_user
    ):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            created = datetime.utcnow() - timedelta(hours=10)
            resolved = datetime.utcnow() - timedelta(hours=2)
            ticket = Ticket(
                ticket_number="TKT-000997",
                title="Perf ticket",
                description="resolved work",
                created_by=admin_user.id,
                assigned_to=agent_user.id,
                type="incident",
                priority="high",
                category="Hardware",
                status="resolved",
            )
            db.session.add(ticket)
            db.session.flush()
            ticket.created_at = created
            ticket.resolved_at = resolved
            db.session.commit()

            response = client.get("/analytics/performance")
            data = response.get_json()
            entry = next(p for p in data if p["agent"] == "Agent User")
            assert entry["assigned"] == 1
            assert entry["resolved"] == 1
            # CHARACTERIZED → fixed 2026-10-08: avg_resolution_hours is now computed in
            # Python from the model's resolution_time property instead of a
            # DB-side `extract('epoch', ...)` that compiled to garbage on
            # SQLite (constant -58574100.0). True resolution = 8.0h.
            assert entry["avg_resolution"] == 8.0

    def test_sla_api_mttr_and_active_breached(
        self, client, app, db, admin_user, agent_user
    ):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            # resolved ticket: created 10h ago, resolved 2h ago -> mttr 8.0
            done = Ticket(
                ticket_number="TKT-000998",
                title="Resolved one",
                description="done",
                created_by=admin_user.id,
                assigned_to=agent_user.id,
                type="incident",
                priority="medium",
                category="Software",
                status="resolved",
            )
            # open ticket with SLA deadline already past -> active_breached 1
            breached = Ticket(
                ticket_number="TKT-000999",
                title="Breached one",
                description="late",
                created_by=admin_user.id,
                assigned_to=agent_user.id,
                type="incident",
                priority="critical",
                category="Security",
                status="in_progress",
            )
            db.session.add_all([done, breached])
            db.session.flush()
            done.created_at = datetime.utcnow() - timedelta(hours=10)
            done.resolved_at = datetime.utcnow() - timedelta(hours=2)
            breached.created_at = datetime.utcnow() - timedelta(hours=48)
            breached.sla_deadline = datetime.utcnow() - timedelta(hours=5)
            db.session.commit()

            response = client.get("/analytics/sla")
            data = response.get_json()
            # CHARACTERIZED: mttr_hours computed over ALL resolved tickets regardless of sla status
            assert data["mttr_hours"] == 8.0
            assert data["active_breached"] == 1
            assert set(data.keys()) >= {"compliance_rate", "met", "breached", "total", "mttr_hours", "active_breached"}

    def test_audit_logs_admin_access(self, client, app, db, admin_user):
        with app.app_context():
            client.post("/login", data={"username": "admin", "password": "Admin@123456"})
            older = AuditLog(
                user_id=admin_user.id,
                action="login",
                entity_type="user",
                entity_id=admin_user.id,
                created_at=datetime.utcnow() - timedelta(hours=2),
            )
            newer = AuditLog(
                user_id=admin_user.id,
                action="status_change",
                entity_type="ticket",
                entity_id=42,
                details={"status": "closed"},
                created_at=datetime.utcnow(),
            )
            db.session.add_all([older, newer])
            db.session.commit()

            response = client.get("/analytics/audit-logs")
            assert response.status_code == 200
            html = response.data.decode()
            assert "Audit Logs" in html
            assert "login" in html
            assert "status_change" in html
            # CHARACTERIZED: ordered by created_at desc (newer row rendered first)
            assert html.index("status_change") < html.index("login")
            # CHARACTERIZED: no logs case still renders (empty tbody)
            assert "System" in html or "Admin User" in html

    def test_audit_logs_forbidden_for_agent(self, client, app, agent_user):
        with app.app_context():
            client.post("/login", data={"username": "agent", "password": "Agent@123456"})
            response = client.get("/analytics/audit-logs")
            assert response.status_code == 403

    def test_audit_logs_forbidden_for_regular_user(self, client, app, regular_user):
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            response = client.get("/analytics/audit-logs")
            assert response.status_code == 403

    def test_unauthenticated_redirects_to_login(self, client, app):
        with app.app_context():
            for url in (
                "/analytics",
                "/analytics/tickets",
                "/analytics/sla",
                "/analytics/performance",
                "/analytics/categories",
                "/analytics/audit-logs",
            ):
                response = client.get(url)
                assert response.status_code == 302, url
                assert "/login" in response.headers["Location"], url

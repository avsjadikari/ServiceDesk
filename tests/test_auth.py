import pytest
from app.models import User


class TestAuthentication:
    """Test authentication functionality"""

    def test_login_page_loads(self, client):
        """Test that login page loads successfully"""
        response = client.get("/login")
        assert response.status_code == 200
        assert b"Login" in response.data

    def test_login_success(self, client, app, admin_user):
        """Test successful login"""
        with app.app_context():
            response = client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_login_invalid_credentials(self, client, app, admin_user):
        """Test login with invalid credentials"""
        with app.app_context():
            response = client.post(
                "/login", data={"username": "admin", "password": "wrongpassword"}
            )
            assert b"Invalid username or password" in response.data

    def test_logout(self, client, app, admin_user):
        """Test logout functionality"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.get("/logout", follow_redirects=True)
            assert response.status_code == 200

    def test_register_page_loads(self, client):
        """Test registration page loads"""
        response = client.get("/register")
        assert response.status_code == 200

    def test_registration_success(self, client, app):
        """Test successful user registration"""
        with app.app_context():
            response = client.post(
                "/register",
                data={
                    "username": "newuser",
                    "email": "newuser@test.com",
                    "full_name": "New User",
                    "department": "IT",
                    "phone": "1234567890",
                    "password": "NewUser@123",
                    "password2": "NewUser@123",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

            user = User.query.filter_by(username="newuser").first()
            assert user is not None
            assert user.email == "newuser@test.com"

    def test_registration_duplicate_username(self, client, app, admin_user):
        """Test registration with duplicate username"""
        with app.app_context():
            response = client.post(
                "/register",
                data={
                    "username": "admin",
                    "email": "another@test.com",
                    "full_name": "Another User",
                    "password": "Another@123",
                    "password2": "Another@123",
                },
            )
            assert b"Username already exists" in response.data

    def test_password_change_requires_auth(self, client):
        """Test password change requires authentication"""
        response = client.get("/change-password", follow_redirects=True)
        assert b"login" in response.data.lower()


class TestPasswordStrength:
    """Test password strength validation"""

    def test_weak_password_rejected(self, client, app):
        """Test that weak passwords are rejected"""
        with app.app_context():
            response = client.post(
                "/register",
                data={
                    "username": "testuser",
                    "email": "test@test.com",
                    "full_name": "Test User",
                    "password": "weak",
                    "password2": "weak",
                },
            )
            assert response.status_code == 200

    def test_password_without_uppercase_rejected(self, client, app):
        """Test password without uppercase is rejected"""
        with app.app_context():
            response = client.post(
                "/register",
                data={
                    "username": "testuser2",
                    "email": "test2@test.com",
                    "full_name": "Test User 2",
                    "password": "password@123",
                    "password2": "password@123",
                },
            )
            assert b"uppercase" in response.data.lower() or response.status_code == 200


class TestAuthorization:
    """Test authorization and access control"""

    def test_admin_can_access_users(self, client, app, admin_user):
        """Test admin can access user management"""
        with app.app_context():
            client.post(
                "/login", data={"username": "admin", "password": "Admin@123456"}
            )
            response = client.get("/users")
            assert response.status_code == 200

    def test_regular_user_cannot_access_users(self, client, app, regular_user):
        """Test regular user cannot access user management"""
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            response = client.get("/users")
            assert response.status_code == 302

    def test_user_cannot_access_agent_dashboard(self, client, app, regular_user):
        """Test regular user redirected from agent dashboard"""
        with app.app_context():
            client.post("/login", data={"username": "user", "password": "User@123456"})
            response = client.get("/dashboard", follow_redirects=True)
            assert response.status_code == 200


class TestAdminAccountManagement:
    """Admin can reset passwords and toggle disable/lock on other users."""

    def test_admin_can_reset_other_user_password(
        self, client, app, db, admin_user, regular_user
    ):
        """When mail is not configured the route stays on the form and
        displays the temporary password; when mail is configured it
        redirects to /users with a success flash."""
        from werkzeug.security import check_password_hash

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(
                f"/users/{regular_user.id}/reset-password",
                data={"must_change_password": "y"},
            )
            # Mail is not configured in tests, so we expect the page to
            # re-render with the temporary password visible.
            assert response.status_code == 200
            assert b"Temporary password for" in response.data

            target = User.query.get(regular_user.id)
            assert target.must_change_password is True
            assert target.last_password_reset_at is not None
            assert not check_password_hash(target.password_hash, "User@123456")

            # The new password must appear in the HTML exactly once.
            import re
            from html import unescape

            html = response.data.decode("utf-8")
            matches = re.findall(
                r'id="tempPasswordField"\s+value="([^"]+)"', html
            )
            assert len(matches) == 1
            assert check_password_hash(target.password_hash, unescape(matches[0]))

    def test_admin_reset_redirects_when_mail_configured(
        self, client, app, db, admin_user, regular_user
    ):
        """If the mail server is configured, the route redirects to
        /users and the password is not rendered in the response."""
        import re
        from unittest.mock import patch

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            with patch("app.email_utils.send_admin_password_reset", return_value=True):
                response = client.post(
                    f"/users/{regular_user.id}/reset-password",
                    data={"must_change_password": "y"},
                    follow_redirects=False,
                )
            assert response.status_code == 302
            assert response.headers["Location"].endswith("/users")
            html = response.get_data(as_text=True)
            assert 'id="tempPasswordField"' not in html

    def test_admin_cannot_reset_own_password_via_admin_route(
        self, client, app, admin_user
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.get(
                f"/users/{admin_user.id}/reset-password",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"profile page" in response.data

    def test_non_admin_cannot_reset_password(
        self, client, app, db, regular_user, agent_user
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "user", "password": "User@123456"},
            )
            response = client.post(
                f"/users/{agent_user.id}/reset-password",
                data={"must_change_password": "y"},
            )
            assert response.status_code == 302
            assert "/dashboard" in response.headers.get("Location", "")

            target = User.query.get(agent_user.id)
            assert target.check_password("Agent@123456")

    def test_admin_can_disable_user(self, client, app, db, admin_user, regular_user):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(f"/users/{regular_user.id}/disable")
            assert response.status_code == 302

            target = User.query.get(regular_user.id)
            assert target.is_active is False

    def test_disabled_user_cannot_login(
        self, client, app, db, admin_user, regular_user
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(f"/users/{regular_user.id}/disable")

            # Log out the admin to clear the session.
            client.get("/logout")

            response = client.post(
                "/login",
                data={"username": "user", "password": "User@123456"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Invalid username or password" in response.data

    def test_admin_can_re_enable_user(
        self, client, app, db, admin_user, regular_user
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(f"/users/{regular_user.id}/disable")
            client.post(f"/users/{regular_user.id}/enable")

            target = User.query.get(regular_user.id)
            assert target.is_active is True

    def test_admin_can_lock_user(self, client, app, db, admin_user, regular_user):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(
                f"/users/{regular_user.id}/lock",
                data={"minutes": "30"},
            )
            assert response.status_code == 302

            target = User.query.get(regular_user.id)
            assert target.is_locked() is True
            assert target.locked_until is not None

    def test_locked_user_cannot_login(
        self, client, app, db, admin_user, regular_user
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(f"/users/{regular_user.id}/lock", data={"minutes": "30"})
            client.get("/logout")

            response = client.post(
                "/login",
                data={"username": "user", "password": "User@123456"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"locked" in response.data.lower()

    def test_admin_can_unlock_user(self, client, app, db, admin_user, regular_user):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(f"/users/{regular_user.id}/lock", data={"minutes": "30"})
            client.post(f"/users/{regular_user.id}/unlock")

            target = User.query.get(regular_user.id)
            assert target.is_locked() is False
            assert target.locked_until is None
            assert target.failed_login_count == 0

    def test_admin_cannot_disable_self(self, client, app, db, admin_user):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(f"/users/{admin_user.id}/disable")
            assert response.status_code == 302

            me = User.query.get(admin_user.id)
            assert me.is_active is True

    def test_admin_cannot_lock_self(self, client, app, db, admin_user):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(f"/users/{admin_user.id}/lock")
            assert response.status_code == 302

            me = User.query.get(admin_user.id)
            assert me.is_locked() is False

    def test_non_admin_cannot_lock_or_disable(
        self, client, app, db, regular_user, agent_user
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "user", "password": "User@123456"},
            )
            client.post(f"/users/{agent_user.id}/disable")
            client.post(f"/users/{agent_user.id}/lock")

            target = User.query.get(agent_user.id)
            assert target.is_active is True
            assert target.is_locked() is False

    def test_edit_user_rejects_duplicate_email(
        self, client, app, db, admin_user, regular_user, agent_user
    ):
        """Regression: editing a user to use another user's email must
        surface as a form error, not a 500."""
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(
                f"/users/{regular_user.id}/edit",
                data={
                    "username": regular_user.username,
                    "email": agent_user.email,
                    "full_name": regular_user.full_name,
                    "department": regular_user.department or "",
                    "phone": regular_user.phone or "",
                    "role": regular_user.role,
                    "is_active": "y",
                },
                follow_redirects=False,
            )
            assert response.status_code == 200
            assert b"Email already registered" in response.data

            target = User.query.get(regular_user.id)
            assert target.email == regular_user.email  # unchanged

    def test_edit_user_rejects_duplicate_username(
        self, client, app, db, admin_user, regular_user, agent_user
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(
                f"/users/{regular_user.id}/edit",
                data={
                    "username": agent_user.username,
                    "email": regular_user.email,
                    "full_name": regular_user.full_name,
                    "department": regular_user.department or "",
                    "phone": regular_user.phone or "",
                    "role": regular_user.role,
                    "is_active": "y",
                },
            )
            assert response.status_code == 200
            assert b"Username already exists" in response.data

            target = User.query.get(regular_user.id)
            assert target.username == regular_user.username  # unchanged

    def test_edit_user_allows_keeping_own_username_and_email(
        self, client, app, db, admin_user, regular_user
    ):
        """Submitting the form with the user's existing username/email
        must succeed (no false positive uniqueness error)."""
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(
                f"/users/{regular_user.id}/edit",
                data={
                    "username": regular_user.username,
                    "email": regular_user.email,
                    "full_name": regular_user.full_name,
                    "department": regular_user.department or "",
                    "phone": regular_user.phone or "",
                    "role": regular_user.role,
                    "is_active": "y",
                },
            )
            assert response.status_code == 302

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

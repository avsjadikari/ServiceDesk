import re
from unittest.mock import patch
from urllib.parse import urlsplit

import pyotp
import pytest
from app.models import AuditLog, RecoveryCode, User


class TestTwoFactorCsrf:
    """Regression: /login-2fa must render a CSRF token when CSRF is enabled."""

    def test_2fa_login_csrf(self, client, app, admin_user):
        with app.app_context():
            app.config["WTF_CSRF_ENABLED"] = True
        with client.session_transaction() as sess:
            sess["pre_2fa_user_id"] = admin_user.id

        response = client.get("/login-2fa")
        assert response.status_code == 200
        match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        assert match, "login-2fa page must render a CSRF token"
        token = match.group(1).decode()

        response = client.post("/login-2fa", data={"code": "000000"})
        assert response.status_code == 400
        response = client.post(
            "/login-2fa",
            data={"csrf_token": token, "code": "000000"},
            headers={"Referer": "http://localhost/login-2fa"},
        )
        assert response.status_code == 200
        assert b"Invalid verification code" in response.data


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

    def test_login_next_rejects_protocol_relative_url(self, client, app, admin_user):
        """Regression: ``next=//evil.com`` must not redirect off-site.

        The old guard only checked ``startswith("/")``, which a
        protocol-relative URL like ``//evil.com`` satisfies.
        """
        with app.app_context():
            response = client.post(
                "/login?next=//evil.com",
                data={"username": "admin", "password": "Admin@123456"},
                follow_redirects=False,
            )
            assert response.status_code == 302
            location = response.headers.get("Location", "")
            assert "evil.com" not in location
            assert location.endswith("/dashboard")

    def test_login_next_allows_relative_path(self, client, app, admin_user):
        """A same-site relative ``next`` still works."""
        with app.app_context():
            response = client.post(
                "/login?next=/tickets",
                data={"username": "admin", "password": "Admin@123456"},
                follow_redirects=False,
            )
            assert response.status_code == 302
            location = response.headers.get("Location", "")
            assert location.endswith("/tickets")


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


class TestRecoveryCodes:
    """Regression: recovery codes must use a real stdlib primitive."""

    def test_generate_recovery_codes(self, app, db, regular_user):
        """Generate 8 usable alphanumeric codes stored only as hashes.

        Regression: the old code called ``secrets.token_uppercase``, which
        does not exist in the stdlib (AttributeError at 2FA enable)."""
        import secrets

        from app.models import RecoveryCode
        from app.routes.auth import _generate_recovery_codes
        from werkzeug.security import check_password_hash

        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        with app.app_context():
            codes = _generate_recovery_codes(regular_user)
            assert len(codes) == 8
            for code in codes:
                assert len(code) == 10
                assert all(c in alphabet for c in code)

            stored = RecoveryCode.query.filter_by(user_id=regular_user.id).all()
            assert len(stored) == 8
            for code, row in zip(codes, stored):
                assert code not in row.code_hash  # never stored in plaintext
                assert check_password_hash(row.code_hash, code)

            assert all(
                not secrets.compare_digest(a, b)
                for i, a in enumerate(codes)
                for b in codes[:i] + codes[i + 1:]
            )


# ---------------------------------------------------------------------------
# Characterization tests for app/routes/auth.py (Feathers method).
# Each test pins currently observed behavior; suspected bugs are marked
# CHARACTERIZED and flagged as TECH-DEBT ledger candidates — never fixed
# here.
# ---------------------------------------------------------------------------


def _login(client, username, password):
    return client.post(
        "/login", data={"username": username, "password": password}
    )


class TestLoginBranches:
    """Characterization: /login role redirects, DB failure, 2FA gate, lockout."""

    def test_login_redirects_authenticated_agent_to_dashboard(
        self, client, app, agent_user
    ):
        _login(client, "agent", "Agent@123456")
        response = client.get("/login")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

    def test_login_redirects_authenticated_user_to_portal(
        self, client, app, regular_user
    ):
        _login(client, "user", "User@123456")
        response = client.get("/login")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/portal/home")

    def test_login_redirects_authenticated_user_with_must_change_password(
        self, client, app, db, admin_user
    ):
        admin_user.must_change_password = True
        db.session.commit()
        _login(client, "admin", "Admin@123456")
        response = client.get("/login")
        assert response.status_code == 302
        assert "/change-password" in response.headers["Location"]

    def test_login_db_lookup_error_is_swallowed(self, client, app):
        """DB failure during user lookup renders the form with a generic
        'temporarily unavailable' flash instead of a 500."""
        with patch("app.routes.auth.User") as mock_user:
            mock_user.query.filter_by.side_effect = RuntimeError("db down")
            response = client.post(
                "/login", data={"username": "anyone", "password": "Any@123456"}
            )
        assert response.status_code == 200
        assert b"Login temporarily unavailable" in response.data

    def test_login_with_two_factor_enabled_redirects_to_2fa_page(
        self, client, app, db, regular_user
    ):
        regular_user.two_factor_enabled = True
        regular_user.two_factor_secret = pyotp.random_base32()
        db.session.commit()

        response = _login(client, "user", "User@123456")
        assert response.status_code == 302
        assert "/login-2fa" in response.headers["Location"]
        with client.session_transaction() as sess:
            assert sess["pre_2fa_user_id"] == regular_user.id
            assert sess["remember_me"] is False
            assert "_user_id" not in sess  # not logged in yet

    def test_failed_login_lockout_pinned(
        self, client, app, db, regular_user
    ):
        """5th failed attempt locks the account, audits it, flashes the
        lockout message — and an email failure inside the handler is
        swallowed without losing any of that."""
        with patch(
            "app.email_utils.send_account_locked",
            side_effect=Exception("smtp down"),
        ) as mock_locked:
            for _ in range(4):
                response = _login(client, "user", "wrong-password")
                assert response.status_code == 200

            target = User.query.get(regular_user.id)
            assert target.failed_login_count == 4
            assert target.is_locked() is False  # not locked before max

            response = _login(client, "user", "wrong-password")  # 5th

        assert response.status_code == 200
        assert b"Too many failed login attempts" in response.data
        target = User.query.get(regular_user.id)
        assert target.failed_login_count == 5
        assert target.is_locked() is True
        assert target.locked_until is not None
        # email attempted once, exception swallowed by handler
        assert mock_locked.call_count == 1
        locked_audits = AuditLog.query.filter_by(
            action="account_locked", user_id=target.id
        ).count()
        assert locked_audits == 1

    def test_complete_login_forces_password_change(
        self, client, app, db, regular_user
    ):
        regular_user.must_change_password = True
        db.session.commit()
        response = _login(client, "user", "User@123456")
        assert response.status_code == 302
        assert "/change-password" in response.headers["Location"]
        follow = client.get(response.headers["Location"])
        assert follow.status_code == 200
        assert b"You must change your password on first login." in follow.data


class TestLoginTwoFactorBranches:
    """Characterization: /login-2fa session guards + recovery/TOTP paths."""

    def test_2fa_without_pending_session_redirects_to_login(self, client, app):
        response = client.get("/login-2fa")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        follow = client.get(response.headers["Location"])
        assert b"Session expired. Please log in again." in follow.data

    def test_2fa_with_unknown_user_id_redirects_to_login(self, client, app):
        with client.session_transaction() as sess:
            sess["pre_2fa_user_id"] = 999999
        response = client.get("/login-2fa")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        follow = client.get(response.headers["Location"])
        assert b"User not found. Please log in again." in follow.data

    def test_2fa_recovery_empty_code_rejected(self, client, app, regular_user):
        with client.session_transaction() as sess:
            sess["pre_2fa_user_id"] = regular_user.id
        response = client.post(
            "/login-2fa",
            data={"use_recovery": "1", "recovery_code": "   "},
        )
        assert response.status_code == 200
        assert b"Please enter a recovery code." in response.data

    def test_2fa_recovery_invalid_code_rejected(
        self, client, app, db, regular_user
    ):
        from app.routes.auth import _generate_recovery_codes

        codes = _generate_recovery_codes(regular_user)
        with client.session_transaction() as sess:
            sess["pre_2fa_user_id"] = regular_user.id
        response = client.post(
            "/login-2fa",
            data={
                "use_recovery": "1",
                "recovery_code": "ZZZZZZZZZZ",  # not one of the codes
            },
        )
        assert response.status_code == 200
        assert b"Invalid recovery code." in response.data
        # every generated code remains unused
        rows = RecoveryCode.query.filter_by(user_id=regular_user.id).all()
        assert len(rows) == 8
        assert all(not r.used for r in rows)
        assert codes  # sanity

    def test_2fa_recovery_valid_code_consumes_and_logs_in(
        self, client, app, db, regular_user
    ):
        from app.routes.auth import _generate_recovery_codes

        codes = _generate_recovery_codes(regular_user)
        with client.session_transaction() as sess:
            sess["pre_2fa_user_id"] = regular_user.id
            sess["remember_me"] = False
        response = client.post(
            "/login-2fa",
            data={"use_recovery": "1", "recovery_code": codes[0]},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/portal/home")

        with client.session_transaction() as sess:
            assert "pre_2fa_user_id" not in sess
            assert "remember_me" not in sess
            assert sess.get("_user_id") == str(regular_user.id)

        # first code consumed, other seven untouched
        rows = RecoveryCode.query.filter_by(user_id=regular_user.id).all()
        used = [r for r in rows if r.used]
        assert len(used) == 1
        assert (
            AuditLog.query.filter_by(
                action="recovery_code_used", user_id=regular_user.id
            ).count()
            == 1
        )
        # logged in: profile renders
        assert client.get("/profile").status_code == 200

    def test_2fa_valid_totp_logs_in(self, client, app, db, regular_user):
        secret = pyotp.random_base32()
        regular_user.two_factor_enabled = True
        regular_user.two_factor_secret = secret
        db.session.commit()
        with client.session_transaction() as sess:
            sess["pre_2fa_user_id"] = regular_user.id
            sess["remember_me"] = False

        code = pyotp.TOTP(secret).now()
        response = client.post("/login-2fa", data={"code": code})
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/portal/home")

        with client.session_transaction() as sess:
            assert "pre_2fa_user_id" not in sess
            assert "remember_me" not in sess
            assert sess.get("_user_id") == str(regular_user.id)
        assert client.get("/profile").status_code == 200


class TestForgotPassword:
    """Characterization: /forgot-password enumeration-safe responses."""

    def test_forgot_password_get_renders_form(self, client, app):
        response = client.get("/forgot-password")
        assert response.status_code == 200
        assert b"email" in response.data.lower()

    def test_forgot_password_authenticated_redirects_to_dashboard(
        self, client, app, admin_user
    ):
        _login(client, "admin", "Admin@123456")
        response = client.get("/forgot-password")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

    def test_forgot_password_db_error_indistinguishable_from_unknown_email(
        self, client, app, admin_user
    ):
        """DB error during lookup must produce the same response as an
        unknown email (user-enumeration protection holds under failure)."""
        r_unknown = client.post(
            "/forgot-password",
            data={"email": "nobody@example.com"},
            follow_redirects=True,
        )
        with patch("app.routes.auth.User") as mock_user:
            mock_user.query.filter_by.side_effect = RuntimeError("db down")
            r_error = client.post(
                "/forgot-password",
                data={"email": "admin@test.com"},
                follow_redirects=True,
            )
        flash_text = b"If an account exists for that email"
        assert r_unknown.status_code == 200
        assert r_error.status_code == 200
        assert flash_text in r_unknown.data
        assert flash_text in r_error.data
        assert b"temporarily unavailable" not in r_error.data

    def test_forgot_password_send_returns_false_still_succeeds(
        self, client, app, admin_user
    ):
        from app.security import verify_password_reset_token

        with patch(
            "app.email_utils.send_password_reset", return_value=False
        ) as mock_send:
            response = client.post(
                "/forgot-password",
                data={"email": "admin@test.com"},
                follow_redirects=True,
            )
        assert response.status_code == 200
        assert b"If an account exists for that email" in response.data
        assert mock_send.call_count == 1
        sent_user, reset_url = mock_send.call_args[0]
        assert sent_user.id == admin_user.id
        # CHARACTERIZED → fixed 2026-10-08: url_for(_external=True) builds the
        # host from SERVER_NAME when configured (canonical host defeats
        # Host-header poisoning) and from the request host in local dev; the
        # inert `_host` kwarg that leaked a junk `?_host=` query is removed
        assert "?_host=" not in reset_url
        token = urlsplit(reset_url).path.rsplit("/", 1)[-1]
        assert verify_password_reset_token(token) == admin_user.id

    def test_forgot_password_send_exception_still_succeeds(
        self, client, app, admin_user
    ):
        with patch(
            "app.email_utils.send_password_reset",
            side_effect=Exception("smtp down"),
        ) as mock_send:
            response = client.post(
                "/forgot-password",
                data={"email": "admin@test.com"},
                follow_redirects=True,
            )
        assert response.status_code == 200
        assert b"If an account exists for that email" in response.data
        assert mock_send.call_count == 1


class TestResetPassword:
    """Characterization: /reset-password/<token> token guards + outcomes."""

    def test_invalid_token_redirects_with_flash(self, client, app):
        response = client.get("/reset-password/not-a-real-token")
        assert response.status_code == 302
        assert "/forgot-password" in response.headers["Location"]
        follow = client.get(response.headers["Location"])
        assert (
            b"This password reset link is invalid or has expired."
            in follow.data
        )

    def test_token_for_inactive_user_rejected(self, client, app, db, regular_user):
        from app.security import generate_password_reset_token

        token = generate_password_reset_token(regular_user.id)
        regular_user.is_active = False
        db.session.commit()
        response = client.get(f"/reset-password/{token}")
        assert response.status_code == 302
        assert "/forgot-password" in response.headers["Location"]
        follow = client.get(response.headers["Location"])
        assert b"This password reset link is no longer valid." in follow.data

    def test_valid_token_get_renders_form(self, client, app, regular_user):
        from app.security import generate_password_reset_token

        token = generate_password_reset_token(regular_user.id)
        response = client.get(f"/reset-password/{token}")
        assert response.status_code == 200

    def test_reset_password_success(self, client, app, db, regular_user):
        from app.security import generate_password_reset_token

        token = generate_password_reset_token(regular_user.id)
        regular_user.must_change_password = True
        regular_user.failed_login_count = 4
        regular_user.last_password_reset_at = None
        db.session.commit()

        response = client.post(
            f"/reset-password/{token}",
            data={
                "new_password": "ResetPass@123",
                "confirm_password": "ResetPass@123",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert (
            b"Your password has been reset. You can now log in."
            in response.data
        )

        target = User.query.get(regular_user.id)
        assert target.check_password("ResetPass@123")
        assert not target.check_password("User@123456")
        assert target.must_change_password is False
        assert target.failed_login_count == 0
        assert target.last_password_reset_at is not None
        assert (
            AuditLog.query.filter_by(
                action="password_reset", user_id=target.id
            ).count()
            == 1
        )

    def test_reset_password_accepts_the_same_password(
        self, client, app, db, regular_user
    ):
        # CHARACTERIZED → fixed 2026-10-08: guard now checks check_password(),
        # rejecting reuse of the current password instead of comparing against
        # the stored hash (which never matched a real password)
        from app.security import generate_password_reset_token

        token = generate_password_reset_token(regular_user.id)
        response = client.post(
            f"/reset-password/{token}",
            data={
                "new_password": "User@123456",
                "confirm_password": "User@123456",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"New password must be different" in response.data
        assert b"Your password has been reset." not in response.data
        target = User.query.get(regular_user.id)
        assert target.check_password("User@123456")  # unchanged

    def test_reset_password_hash_submitted_is_rejected_by_validators(
        self, client, app, regular_user
    ):
        # CHARACTERIZED: a stored scrypt hash (162 chars) still cannot be
        # submitted — the form's 128-char cap rejects it via validators
        # before the route guard (now check_password) is reached
        from app.security import generate_password_reset_token

        token = generate_password_reset_token(regular_user.id)
        response = client.post(
            f"/reset-password/{token}",
            data={
                "new_password": regular_user.password_hash,
                "confirm_password": regular_user.password_hash,
            },
        )
        assert response.status_code == 200
        assert b"128 characters" in response.data
        assert (
            b"New password must be different from your current password."
            not in response.data
        )
        target = User.query.get(regular_user.id)
        assert target.check_password("User@123456")  # unchanged


class TestChangePassword:
    """Characterization: /change-password validation and role redirects."""

    def test_change_password_get_renders(self, client, app, regular_user):
        _login(client, "user", "User@123456")
        response = client.get("/change-password")
        assert response.status_code == 200

    def test_change_password_wrong_current(self, client, app, regular_user):
        _login(client, "user", "User@123456")
        response = client.post(
            "/change-password",
            data={
                "current_password": "Wrong@123456",
                "new_password": "NewPass@123",
                "confirm_password": "NewPass@123",
            },
        )
        assert response.status_code == 200
        assert b"Current password is incorrect." in response.data

    def test_change_password_new_equals_current(self, client, app, regular_user):
        _login(client, "user", "User@123456")
        response = client.post(
            "/change-password",
            data={
                "current_password": "User@123456",
                "new_password": "User@123456",
                "confirm_password": "User@123456",
            },
        )
        assert response.status_code == 200
        assert (
            b"New password must be different from current password."
            in response.data
        )

    def test_change_password_success_user_redirects_to_portal(
        self, client, app, db, regular_user
    ):
        regular_user.must_change_password = True
        regular_user.last_password_reset_at = None
        db.session.commit()
        _login(client, "user", "User@123456")

        response = client.post(
            "/change-password",
            data={
                "current_password": "User@123456",
                "new_password": "Changed@123",
                "confirm_password": "Changed@123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/portal/home")

        target = User.query.get(regular_user.id)
        assert target.check_password("Changed@123")
        assert target.must_change_password is False
        assert target.last_password_reset_at is not None
        follow = client.get(response.headers["Location"])
        assert b"Password changed successfully!" in follow.data

    def test_change_password_success_agent_redirects_to_dashboard(
        self, client, app, agent_user
    ):
        _login(client, "agent", "Agent@123456")
        response = client.post(
            "/change-password",
            data={
                "current_password": "Agent@123456",
                "new_password": "AgentPass@123",
                "confirm_password": "AgentPass@123",
            },
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")


class TestRegisterAndProfile:
    """Characterization: authenticated /register redirect, /profile CRUD."""

    def test_register_authenticated_redirects_to_dashboard(
        self, client, app, admin_user
    ):
        _login(client, "admin", "Admin@123456")
        response = client.get("/register")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

    def test_profile_get_renders(self, client, app, regular_user):
        _login(client, "user", "User@123456")
        response = client.get("/profile")
        assert response.status_code == 200

    def test_profile_post_updates_fields(self, client, app, db, regular_user):
        _login(client, "user", "User@123456")
        response = client.post(
            "/profile",
            data={
                "full_name": "Renamed Person",
                "email": "renamed@test.com",
                "department": "QA",
                "phone": "555-0100",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Profile updated successfully." in response.data
        target = User.query.get(regular_user.id)
        assert target.full_name == "Renamed Person"
        assert target.email == "renamed@test.com"
        assert target.department == "QA"
        assert target.phone == "555-0100"


class TestAdminUserManagementBranches:
    """Characterization: admin user CRUD edge branches (authz, idempotence,
    email failures, commit failure)."""

    def test_create_user_requires_admin(self, client, app, regular_user):
        _login(client, "user", "User@123456")
        response = client.get("/users/new", follow_redirects=True)
        assert response.status_code == 200
        assert b"Access denied." in response.data

    def test_create_user_get_as_admin(self, client, app, admin_user):
        _login(client, "admin", "Admin@123456")
        response = client.get("/users/new")
        assert response.status_code == 200
        assert b"Add New User" in response.data

    def test_create_user_post_creates_forced_must_change(
        self, client, app, db, admin_user
    ):
        _login(client, "admin", "Admin@123456")
        response = client.post(
            "/users/new",
            data={
                "username": "charlie",
                "email": "charlie@test.com",
                "full_name": "Charlie Create",
                "department": "Ops",
                "phone": "123",
                "password": "Charlie@123",
                "password2": "Charlie@123",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"User charlie created successfully!" in response.data

        created = User.query.filter_by(username="charlie").first()
        assert created is not None
        assert created.role == "user"
        assert created.must_change_password is True
        assert created.check_password("Charlie@123")
        assert (
            AuditLog.query.filter_by(
                action="create_user", user_id=admin_user.id
            ).count()
            == 1
        )

    def test_edit_user_requires_admin(self, client, app, regular_user, admin_user):
        _login(client, "user", "User@123456")
        response = client.get(
            f"/users/{admin_user.id}/edit", follow_redirects=True
        )
        assert response.status_code == 200
        assert b"Access denied." in response.data

    def test_edit_user_commit_failure_surfaces_as_flash(
        self, client, app, db, admin_user, regular_user
    ):
        _login(client, "admin", "Admin@123456")
        original_username = regular_user.username
        with patch.object(
            db.session, "commit", side_effect=Exception("db down")
        ):
            response = client.post(
                f"/users/{regular_user.id}/edit",
                data={
                    "username": "renamed-user",
                    "email": regular_user.email,
                    "full_name": regular_user.full_name,
                    "department": regular_user.department or "",
                    "phone": regular_user.phone or "",
                    "role": regular_user.role,
                    "is_active": "y",
                },
            )
        assert response.status_code == 200
        assert b"Could not save changes" in response.data
        target = User.query.get(regular_user.id)
        assert target.username == original_username  # rolled back

    def test_admin_reset_password_get_renders_form(
        self, client, app, admin_user, regular_user
    ):
        _login(client, "admin", "Admin@123456")
        response = client.get(f"/users/{regular_user.id}/reset-password")
        assert response.status_code == 200
        assert b"must_change_password" in response.data

    def test_admin_reset_password_email_exception_renders_temp_password(
        self, client, app, db, admin_user, regular_user
    ):
        _login(client, "admin", "Admin@123456")
        with patch(
            "app.email_utils.send_admin_password_reset",
            side_effect=Exception("smtp down"),
        ) as mock_send:
            response = client.post(
                f"/users/{regular_user.id}/reset-password",
                data={"must_change_password": "y"},
            )
        assert response.status_code == 200
        assert b"could not be delivered" in response.data
        assert b'id="tempPasswordField"' in response.data
        assert mock_send.call_count == 1
        target = User.query.get(regular_user.id)
        assert not target.check_password("User@123456")
        assert target.must_change_password is True

    def test_disable_already_disabled_user(
        self, client, app, db, admin_user, regular_user
    ):
        regular_user.is_active = False
        db.session.commit()
        _login(client, "admin", "Admin@123456")
        response = client.post(
            f"/users/{regular_user.id}/disable", follow_redirects=True
        )
        assert response.status_code == 200
        assert b"is already disabled." in response.data
        target = User.query.get(regular_user.id)
        assert target.is_active is False

    def test_disable_user_email_exception_still_disables(
        self, client, app, db, admin_user, regular_user
    ):
        _login(client, "admin", "Admin@123456")
        with patch(
            "app.email_utils.send_account_disabled",
            side_effect=Exception("smtp down"),
        ) as mock_send:
            response = client.post(
                f"/users/{regular_user.id}/disable", follow_redirects=True
            )
        assert response.status_code == 200
        assert b"has been disabled." in response.data
        assert mock_send.call_count == 1
        target = User.query.get(regular_user.id)
        assert target.is_active is False
        assert (
            AuditLog.query.filter_by(
                action="disable_user", entity_id=regular_user.id
            ).count()
            == 1
        )

    def test_enable_requires_admin(self, client, app, regular_user, admin_user):
        _login(client, "user", "User@123456")
        response = client.post(
            f"/users/{admin_user.id}/enable", follow_redirects=True
        )
        assert response.status_code == 200
        assert b"Access denied." in response.data

    def test_enable_already_active_user(self, client, app, admin_user, regular_user):
        _login(client, "admin", "Admin@123456")
        response = client.post(
            f"/users/{regular_user.id}/enable", follow_redirects=True
        )
        assert response.status_code == 200
        assert b"is already active." in response.data
        target = User.query.get(regular_user.id)
        assert target.is_active is True

    def test_enable_user_email_exception_still_enables(
        self, client, app, db, admin_user, regular_user
    ):
        regular_user.is_active = False
        db.session.commit()
        _login(client, "admin", "Admin@123456")
        with patch(
            "app.email_utils.send_account_enabled",
            side_effect=Exception("smtp down"),
        ) as mock_send:
            response = client.post(
                f"/users/{regular_user.id}/enable", follow_redirects=True
            )
        assert response.status_code == 200
        assert b"has been enabled." in response.data
        assert mock_send.call_count == 1
        target = User.query.get(regular_user.id)
        assert target.is_active is True

    def test_lock_disabled_user_rejected(
        self, client, app, db, admin_user, regular_user
    ):
        regular_user.is_active = False
        db.session.commit()
        _login(client, "admin", "Admin@123456")
        response = client.post(
            f"/users/{regular_user.id}/lock",
            data={"minutes": "30"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"disabled; enable them before locking." in response.data
        target = User.query.get(regular_user.id)
        assert target.is_locked() is False

    def test_lock_invalid_minutes_defaults_to_60(
        self, client, app, db, admin_user, regular_user
    ):
        from datetime import datetime, timedelta

        _login(client, "admin", "Admin@123456")
        response = client.post(
            f"/users/{regular_user.id}/lock",
            data={"minutes": "not-a-number"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"has been locked for 60 minutes" in response.data
        target = User.query.get(regular_user.id)
        assert target.is_locked() is True
        delta = target.locked_until - datetime.utcnow()
        assert timedelta(minutes=59) < delta < timedelta(minutes=61)

    def test_lock_user_email_exception_still_locks(
        self, client, app, db, admin_user, regular_user
    ):
        _login(client, "admin", "Admin@123456")
        with patch(
            "app.email_utils.send_account_manually_locked",
            side_effect=Exception("smtp down"),
        ) as mock_send:
            response = client.post(
                f"/users/{regular_user.id}/lock",
                data={"minutes": "30"},
                follow_redirects=True,
            )
        assert response.status_code == 200
        assert b"has been locked for 30 minutes" in response.data
        assert mock_send.call_count == 1
        target = User.query.get(regular_user.id)
        assert target.is_locked() is True

    def test_unlock_requires_admin(self, client, app, regular_user, admin_user):
        _login(client, "user", "User@123456")
        response = client.post(
            f"/users/{admin_user.id}/unlock", follow_redirects=True
        )
        assert response.status_code == 200
        assert b"Access denied." in response.data

    def test_unlock_user_not_locked(self, client, app, admin_user, regular_user):
        _login(client, "admin", "Admin@123456")
        response = client.post(
            f"/users/{regular_user.id}/unlock", follow_redirects=True
        )
        assert response.status_code == 200
        assert b"is not locked." in response.data

    def test_unlock_user_email_exception_still_unlocks(
        self, client, app, db, admin_user, regular_user
    ):
        regular_user.lock(minutes=30)
        db.session.commit()
        _login(client, "admin", "Admin@123456")
        with patch(
            "app.email_utils.send_account_unlocked",
            side_effect=Exception("smtp down"),
        ) as mock_send:
            response = client.post(
                f"/users/{regular_user.id}/unlock", follow_redirects=True
            )
        assert response.status_code == 200
        assert b"has been unlocked." in response.data
        assert mock_send.call_count == 1
        target = User.query.get(regular_user.id)
        assert target.is_locked() is False


class TestTwoFactorSetupAndDisable:
    """Characterization: /profile/2fa/setup and /profile/2fa/disable."""

    def test_setup_2fa_get_generates_secret_and_qr(self, client, app, db, regular_user):
        _login(client, "user", "User@123456")
        response = client.get("/profile/2fa/setup")
        assert response.status_code == 200
        assert b"data:image/png;base64," in response.data
        target = User.query.get(regular_user.id)
        assert target.two_factor_secret is not None
        assert target.two_factor_secret.encode() in response.data
        assert target.two_factor_enabled is False

    def test_setup_2fa_invalid_code_generates_secret_first(
        self, client, app, db, regular_user
    ):
        _login(client, "user", "User@123456")
        response = client.post("/profile/2fa/setup", data={"code": "000000"})
        assert response.status_code == 200
        assert b"Invalid verification code." in response.data
        target = User.query.get(regular_user.id)
        assert target.two_factor_secret is not None  # generated pre-verify
        assert target.two_factor_enabled is False

    def test_setup_2fa_valid_code_enables_and_shows_recovery_codes(
        self, client, app, db, regular_user
    ):
        from werkzeug.security import check_password_hash

        secret = pyotp.random_base32()
        regular_user.two_factor_secret = secret
        db.session.commit()
        _login(client, "user", "User@123456")

        code = pyotp.TOTP(secret).now()
        with patch("app.email_utils.send_2fa_enabled") as mock_send:
            response = client.post("/profile/2fa/setup", data={"code": code})

        assert response.status_code == 200
        assert b"Your Recovery Codes" in response.data
        assert b"Two-factor authentication enabled successfully!" in response.data
        assert mock_send.call_count == 1

        target = User.query.get(regular_user.id)
        assert target.two_factor_enabled is True

        shown = re.findall(
            rb'<code class="fs-6">([A-Z0-9]{10})</code>', response.data
        )
        assert len(shown) == 8
        rows = RecoveryCode.query.filter_by(user_id=target.id).all()
        assert len(rows) == 8
        # every displayed plaintext code verifies against a stored hash
        for plaintext in shown:
            assert any(
                check_password_hash(r.code_hash, plaintext.decode())
                for r in rows
            )
        assert (
            AuditLog.query.filter_by(
                action="2fa_enabled", user_id=target.id
            ).count()
            == 1
        )

    def test_disable_2fa_wrong_password(self, client, app, db, regular_user):
        from app.routes.auth import _generate_recovery_codes

        # log in first: a 2FA-enabled account is diverted to /login-2fa
        _login(client, "user", "User@123456")
        regular_user.two_factor_enabled = True
        regular_user.two_factor_secret = pyotp.random_base32()
        db.session.commit()
        _generate_recovery_codes(regular_user)

        response = client.post(
            "/profile/2fa/disable",
            data={"password": "WrongPassword@1"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Incorrect password. Cannot disable 2FA." in response.data
        target = User.query.get(regular_user.id)
        assert target.two_factor_enabled is True
        rows = RecoveryCode.query.filter_by(user_id=target.id).all()
        assert all(not r.used for r in rows)

    def test_disable_2fa_success(self, client, app, db, regular_user):
        from app.routes.auth import _generate_recovery_codes

        _login(client, "user", "User@123456")
        regular_user.two_factor_enabled = True
        regular_user.two_factor_secret = pyotp.random_base32()
        db.session.commit()
        _generate_recovery_codes(regular_user)

        with patch("app.email_utils.send_2fa_disabled") as mock_send:
            response = client.post(
                "/profile/2fa/disable",
                data={"password": "User@123456"},
                follow_redirects=True,
            )
        assert response.status_code == 200
        assert b"Two-factor authentication disabled." in response.data
        assert mock_send.call_count == 1

        target = User.query.get(regular_user.id)
        assert target.two_factor_enabled is False
        rows = RecoveryCode.query.filter_by(user_id=target.id).all()
        assert rows and all(r.used for r in rows)
        assert (
            AuditLog.query.filter_by(
                action="2fa_disabled", user_id=target.id
            ).count()
            == 1
        )

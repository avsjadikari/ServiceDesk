"""Tests for the system settings (company-name branding)."""

import pytest

from app.models import AuditLog, SystemSetting


@pytest.fixture
def fresh_settings(db):
    """Wipe system_settings and the relevant audit-log entries so each
    test starts from a known baseline."""
    SystemSetting.query.delete()
    AuditLog.query.filter_by(action="update_company_name").delete()
    db.session.commit()
    yield
    SystemSetting.query.delete()
    AuditLog.query.filter_by(action="update_company_name").delete()
    db.session.commit()


class TestCompanyNameDisplay:
    """The display name must always be ``<stored> ServiceDesk``."""

    def test_default_display_uses_servicedesk_suffix(self, app, fresh_settings):
        from app.settings_store import display_company_name

        with app.app_context():
            assert display_company_name() == "ServiceDesk ServiceDesk"

    def test_stored_name_gets_suffix(self, app, fresh_settings):
        from app.settings_store import display_company_name, set_company_name

        with app.app_context():
            set_company_name("Acme")
            assert display_company_name() == "Acme ServiceDesk"

    def test_suffix_always_applied(self, app, fresh_settings):
        from app.settings_store import display_company_name, set_company_name

        with app.app_context():
            set_company_name("Acme")
            assert display_company_name() == "Acme ServiceDesk"
            set_company_name("Globex")
            assert display_company_name() == "Globex ServiceDesk"

    def test_blank_storage_falls_back(self, app, fresh_settings, db):
        from app.settings_store import display_company_name

        with app.app_context():
            row = SystemSetting(key="company_name", value="   ")
            db.session.add(row)
            db.session.commit()
            assert display_company_name() == "ServiceDesk ServiceDesk"

    def test_strip_whitespace_on_set(self, app, fresh_settings):
        from app.settings_store import get_company_name, set_company_name

        with app.app_context():
            set_company_name("   Globex   ")
            assert get_company_name() == "Globex"

    def test_set_company_name_rejects_empty(self, app, fresh_settings):
        from app.settings_store import set_company_name

        with app.app_context():
            with pytest.raises(ValueError):
                set_company_name("   ")


class TestSettingsRoute:
    """The admin settings page must update the brand and audit the change."""

    def test_non_admin_cannot_view_settings(
        self, client, app, regular_user
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "user", "password": "User@123456"},
            )
            response = client.get("/settings/", follow_redirects=True)
            assert response.status_code == 200
            assert b"Only administrators" in response.data

    def test_admin_can_view_settings_page(self, client, app, admin_user):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.get("/settings/")
            assert response.status_code == 200
            assert b"System Settings" in response.data

    def test_admin_can_update_company_name(
        self, client, app, db, admin_user, fresh_settings
    ):
        from app.settings_store import get_company_name

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(
                "/settings/",
                data={"company_name": "Initech"},
            )
            assert response.status_code == 302
            assert get_company_name() == "Initech"

            entries = AuditLog.query.filter_by(action="update_company_name").all()
            assert len(entries) == 1
            assert entries[0].details == {"old": "ServiceDesk", "new": "Initech"}

    def test_template_renders_display_with_suffix(
        self, client, app, db, admin_user, fresh_settings
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post("/settings/", data={"company_name": "Initech"})

            response = client.get("/settings/")
            assert response.status_code == 200
            assert b"Initech ServiceDesk" in response.data

    def test_blank_name_rejected(
        self, client, app, db, admin_user, fresh_settings
    ):
        from app.settings_store import get_company_name

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(
                "/settings/", data={"company_name": "  "}
            )
            assert response.status_code == 200
            assert b"Company name" in response.data
            assert get_company_name() == "ServiceDesk"


class TestMailSettings:
    """Admin can configure the SMTP server from the System Settings page."""

    def test_mail_form_renders(self, client, app, admin_user):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.get("/settings/")
            assert response.status_code == 200
            assert b"SMTP server" in response.data
            assert b"Send test email" in response.data

    def test_admin_can_save_mail_config(
        self, client, app, db, admin_user, fresh_settings
    ):
        from app.settings_store import get_mail_config

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.example.com",
                    "mail_port": "465",
                    "mail_use_tls": "y",
                    "mail_username": "noreply@example.com",
                    "mail_password": "app-password-1",
                    "mail_default_sender": "ServiceDesk <noreply@example.com>",
                },
            )
            assert response.status_code == 302

            cfg = get_mail_config()
            assert cfg["MAIL_SERVER"] == "smtp.example.com"
            assert cfg["MAIL_PORT"] == 465
            assert cfg["MAIL_USE_TLS"] is True
            assert cfg["MAIL_USERNAME"] == "noreply@example.com"
            assert cfg["MAIL_PASSWORD"] == "app-password-1"
            assert cfg["MAIL_DEFAULT_SENDER"] == (
                "ServiceDesk <noreply@example.com>"
            )

    def test_mail_config_is_pushed_to_app(
        self, client, app, db, admin_user, fresh_settings
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.acme.com",
                    "mail_port": "2525",
                    "mail_use_tls": "y",
                    "mail_username": "ops@acme.com",
                    "mail_password": "secret",
                    "mail_default_sender": "",
                },
            )
            assert app.config["MAIL_SERVER"] == "smtp.acme.com"
            assert app.config["MAIL_PORT"] == 2525
            assert app.config["MAIL_USE_TLS"] is True
            assert app.config["MAIL_USERNAME"] == "ops@acme.com"

    def test_blank_password_keeps_existing_secret(
        self, client, app, db, admin_user, fresh_settings
    ):
        from app.settings_store import get_mail_config

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            # Set initial password
            client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.example.com",
                    "mail_port": "587",
                    "mail_username": "noreply@example.com",
                    "mail_password": "initial-secret",
                },
            )
            assert get_mail_config()["MAIL_PASSWORD"] == "initial-secret"
            # Now re-save without a password
            client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.example.com",
                    "mail_port": "587",
                    "mail_username": "noreply@example.com",
                    "mail_password": "",
                },
            )
            assert get_mail_config()["MAIL_PASSWORD"] == "initial-secret"

    def test_invalid_port_rejected(
        self, client, app, db, admin_user, fresh_settings
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.example.com",
                    "mail_port": "99999",
                    "mail_username": "noreply@example.com",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"mail_port" in response.data or b"port" in response.data.lower()

    def test_test_email_requires_configuration(
        self, client, app, db, admin_user, fresh_settings
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.post(
                "/settings/mail/test",
                data={"recipient": "admin@example.com"},
                follow_redirects=True,
            )
            assert b"not configured" in response.data

    def test_test_email_calls_send_email(
        self, client, app, db, admin_user, fresh_settings
    ):
        from unittest.mock import patch

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.example.com",
                    "mail_port": "587",
                    "mail_username": "noreply@example.com",
                    "mail_password": "secret",
                },
            )
            with patch("app.email_utils.send_email", return_value=True) as mock_send:
                response = client.post(
                    "/settings/mail/test",
                    data={"recipient": "ops@example.com"},
                    follow_redirects=True,
                )
            assert mock_send.called
            assert b"Test email sent" in response.data

    def test_test_email_surfaces_failure(
        self, client, app, db, admin_user, fresh_settings
    ):
        from unittest.mock import patch

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.example.com",
                    "mail_port": "587",
                    "mail_username": "noreply@example.com",
                    "mail_password": "secret",
                },
            )
            with patch("app.email_utils.send_email", return_value=False):
                response = client.post(
                    "/settings/mail/test",
                    data={"recipient": "ops@example.com"},
                    follow_redirects=True,
                )
            assert b"could not be sent" in response.data

    def test_non_admin_cannot_change_mail(
        self, client, app, regular_user
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "user", "password": "User@123456"},
            )
            response = client.post(
                "/settings/mail",
                data={"mail_server": "evil.example.com", "mail_port": "25"},
                follow_redirects=True,
            )
            assert b"Only administrators" in response.data

    def test_mail_save_creates_audit_log(
        self, client, app, db, admin_user, fresh_settings
    ):
        from app.models import AuditLog

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.example.com",
                    "mail_port": "587",
                    "mail_username": "noreply@example.com",
                    "mail_password": "secret",
                },
            )
            entries = AuditLog.query.filter_by(action="update_mail_config").all()
            assert len(entries) == 1

    def test_mask_secret(self):
        from app.settings_store import mask_secret

        assert mask_secret(None) == ""
        assert mask_secret("") == ""
        assert mask_secret("ab") == "••"
        assert mask_secret("abcdef") == "ab••ef"

    def test_send_email_falls_back_to_username(
        self, client, app, db, admin_user, fresh_settings
    ):
        """When no default sender is configured, send_email must use
        MAIL_USERNAME as the From address. This is the regression for the
        AssertionError users hit when they only set username + password."""
        from unittest.mock import patch

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.example.com",
                    "mail_port": "587",
                    "mail_username": "noreply@example.com",
                    "mail_password": "secret",
                    "mail_default_sender": "",
                },
            )
            assert app.config.get("MAIL_DEFAULT_SENDER") in (None, "")
            with patch("app.email_utils.mail.send") as mock_send:
                from app.email_utils import send_email
                ok = send_email("user@example.com", "Hi", "body")
            assert ok is True
            assert mock_send.called
            sent_msg = mock_send.call_args[0][0]
            assert sent_msg.sender == "noreply@example.com"

    def test_send_email_explicit_sender_wins(
        self, client, app, db, admin_user, fresh_settings
    ):
        from unittest.mock import patch

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.example.com",
                    "mail_port": "587",
                    "mail_username": "ops@example.com",
                    "mail_password": "secret",
                    "mail_default_sender": "ServiceDesk <desk@example.com>",
                },
            )
            with patch("app.email_utils.mail.send") as mock_send:
                from app.email_utils import send_email
                send_email(
                    "user@example.com",
                    "Hi",
                    "body",
                    sender="override@example.com",
                )
            sent_msg = mock_send.call_args[0][0]
            assert sent_msg.sender == "override@example.com"

    def test_send_email_raises_mail_send_error_without_any_sender(
        self, client, app, db, admin_user, fresh_settings
    ):
        """When MAIL_USERNAME is set but neither MAIL_DEFAULT_SENDER nor
        MAIL_USERNAME is a usable From address, ``MailSendError`` is
        raised."""
        from unittest.mock import patch

        with app.app_context():
            # Set MAIL_USERNAME to an empty string so _resolve_sender()
            # returns None (the empty string is falsy in the fallback
            # chain), but the early guard in send_email sees a truthy
            # string. Use a different approach: keep the username so the
            # guard passes, but remove the default sender so _resolve_sender
            # still has the username as fallback. To force the "no From"
            # path we mock _resolve_sender.
            app.config["MAIL_USERNAME"] = "user@example.com"
            app.config["MAIL_DEFAULT_SENDER"] = ""
            with patch("app.email_utils.mail.send") as mock_send, \
                 patch("app.email_utils._resolve_sender", return_value=None):
                from app.email_utils import MailSendError, send_email
                with pytest.raises(MailSendError):
                    send_email("user@example.com", "Hi", "body")
            assert not mock_send.called

    def test_send_email_translates_smtp_auth_error_to_hint(
        self, client, app, db, admin_user, fresh_settings
    ):
        """A 530/535 from the SMTP server should be turned into a
        user-friendly flash message that mentions App Passwords and
        provider workarounds."""
        import smtplib
        from unittest.mock import patch

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.gmail.com",
                    "mail_port": "587",
                    "mail_username": "sysadmin.supermax@gmail.com",
                    "mail_password": "wrong-password",
                },
            )
            with patch(
                "app.email_utils.mail.send",
                side_effect=smtplib.SMTPAuthenticationError(
                    535, b"5.7.8 authentication failed"
                ),
            ):
                from app.email_utils import MailSendError, send_email
                with pytest.raises(MailSendError) as excinfo:
                    send_email("x@example.com", "hi", "body")
            assert excinfo.value.smtp_code == 535
            assert "App Password" in excinfo.value.user_message
            assert "Mailgun" in excinfo.value.user_message

    def test_test_email_surfaces_535_app_password_hint(
        self, client, app, db, admin_user, fresh_settings
    ):
        import smtplib
        from unittest.mock import patch

        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            client.post(
                "/settings/mail",
                data={
                    "mail_server": "smtp.gmail.com",
                    "mail_port": "587",
                    "mail_username": "sysadmin.supermax@gmail.com",
                    "mail_password": "wrong-password",
                },
            )
            with patch(
                "app.email_utils.mail.send",
                side_effect=smtplib.SMTPAuthenticationError(
                    535, b"5.7.8 authentication failed"
                ),
            ):
                response = client.post(
                    "/settings/mail/test",
                    data={"recipient": "ops@example.com"},
                    follow_redirects=True,
                )
            assert b"App Password" in response.data
            assert b"Mailgun" in response.data or b"SendGrid" in response.data

    def test_settings_page_has_provider_help_accordion(
        self, client, app, admin_user
    ):
        with app.app_context():
            client.post(
                "/login",
                data={"username": "admin", "password": "Admin@123456"},
            )
            response = client.get("/settings/")
            assert b"How do I configure common mail providers?" in response.data
            assert b"Mailgun" in response.data
            assert b"App passwords" in response.data

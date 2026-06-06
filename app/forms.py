from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SelectField,
    TextAreaField,
    DateField,
    IntegerField,
    FileField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)
from app.models import User
from app import db


_PASSWORD_REGEX_MSG = (
    "Password must contain at least: 1 uppercase, 1 lowercase, "
    "1 number, 1 special character (@$!%*?&)"
)
_PASSWORD_REGEX = (
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]"
)


class SetupForm(FlaskForm):
    company_name = StringField(
        "Company Name",
        validators=[DataRequired(), Length(min=2, max=64)],
    )

    db_type = SelectField(
        "Database Type",
        choices=[
            ("sqlite", "SQLite (Development)"),
            ("postgresql", "PostgreSQL (Production)"),
        ],
        default="sqlite",
    )
    db_host = StringField("Database Host", default="localhost")
    db_port = StringField("Database Port", default="5432")
    db_name = StringField("Database Name", default="servicedesk")
    db_user = StringField("Database User", default="servicedesk")
    db_password = PasswordField("Database Password")

    admin_username = StringField(
        "Admin Username", validators=[DataRequired(), Length(min=3, max=64)]
    )
    admin_email = StringField("Admin Email", validators=[DataRequired(), Email()])
    admin_full_name = StringField(
        "Admin Full Name", validators=[DataRequired(), Length(max=128)]
    )
    admin_password = PasswordField(
        "Admin Password", validators=[DataRequired(), Length(min=6)]
    )


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")


class RegistrationForm(FlaskForm):
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=3, max=64)]
    )
    email = StringField("Email", validators=[DataRequired(), Email()])
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=128)])
    department = StringField("Department", validators=[Optional(), Length(max=64)])
    phone = StringField("Phone", validators=[Optional(), Length(max=20)])
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, max=128),
            Regexp(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]",
                message="Password must contain at least: 1 uppercase, 1 lowercase, 1 number, 1 special character (@$!%*?&)",
            ),
        ],
    )
    password2 = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password")]
    )

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError("Username already exists.")

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError("Email already registered.")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=8, max=128),
            Regexp(
                r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]",
                message="Password must contain at least: 1 uppercase, 1 lowercase, 1 number, 1 special character (@$!%*?&)",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password", validators=[DataRequired(), EqualTo("new_password")]
    )


class UserEditForm(FlaskForm):
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=3, max=64)]
    )
    email = StringField("Email", validators=[DataRequired(), Email()])
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=128)])
    department = StringField("Department", validators=[Optional(), Length(max=64)])
    phone = StringField("Phone", validators=[Optional(), Length(max=20)])
    role = SelectField(
        "Role", choices=[("user", "User"), ("agent", "Agent"), ("admin", "Admin")]
    )
    is_active = BooleanField("Active")

    def __init__(self, *args, editing_user_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._editing_user_id = editing_user_id

    def validate_username(self, username):
        query = User.query.filter(
            db.func.lower(User.username) == username.data.lower()
        )
        if self._editing_user_id is not None:
            query = query.filter(User.id != self._editing_user_id)
        if query.first():
            raise ValidationError("Username already exists.")

    def validate_email(self, email):
        query = User.query.filter(db.func.lower(User.email) == email.data.lower())
        if self._editing_user_id is not None:
            query = query.filter(User.id != self._editing_user_id)
        if query.first():
            raise ValidationError("Email already registered.")


class TicketForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[DataRequired()])
    type = SelectField(
        "Type",
        choices=[
            ("incident", "Incident"),
            ("request", "Request"),
            ("problem", "Problem"),
        ],
    )
    priority = SelectField(
        "Priority",
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
    )
    category = SelectField(
        "Category",
        choices=[
            ("Hardware", "Hardware"),
            ("Software", "Software"),
            ("Network", "Network"),
            ("Security", "Security"),
            ("Email", "Email"),
            ("Account/Access", "Account/Access"),
            ("Application", "Application"),
            ("Database", "Database"),
            ("Other", "Other"),
        ],
    )
    assigned_to = SelectField("Assign To", coerce=int, validators=[Optional()])


class TicketFilterForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[
            ("", "All"),
            ("new", "New"),
            ("assigned", "Assigned"),
            ("in_progress", "In Progress"),
            ("pending", "Pending"),
            ("resolved", "Resolved"),
            ("closed", "Closed"),
        ],
        validators=[Optional()],
    )
    priority = SelectField(
        "Priority",
        choices=[
            ("", "All"),
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        validators=[Optional()],
    )
    category = SelectField(
        "Category",
        choices=[
            ("", "All"),
            ("Hardware", "Hardware"),
            ("Software", "Software"),
            ("Network", "Network"),
            ("Security", "Security"),
            ("Email", "Email"),
            ("Account/Access", "Account/Access"),
            ("Application", "Application"),
            ("Database", "Database"),
            ("Other", "Other"),
        ],
        validators=[Optional()],
    )
    assigned_to = SelectField("Assigned To", coerce=int, validators=[Optional()])


class CommentForm(FlaskForm):
    content = TextAreaField("Comment", validators=[DataRequired()])
    is_internal = BooleanField("Internal Note")


class ArticleForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    content = TextAreaField("Content", validators=[DataRequired()])
    category = SelectField(
        "Category",
        choices=[
            ("Hardware", "Hardware"),
            ("Software", "Software"),
            ("Network", "Network"),
            ("Security", "Security"),
            ("Email", "Email"),
            ("Account/Access", "Account/Access"),
            ("Application", "Application"),
            ("Database", "Database"),
            ("Other", "Other"),
        ],
    )
    tags = StringField("Tags (comma separated)")
    status = SelectField(
        "Status",
        choices=[
            ("draft", "Draft"),
            ("published", "Published"),
            ("archived", "Archived"),
        ],
    )


class ArticleSearchForm(FlaskForm):
    search = StringField("Search")
    category = SelectField(
        "Category",
        choices=[
            ("", "All Categories"),
            ("Hardware", "Hardware"),
            ("Software", "Software"),
            ("Network", "Network"),
            ("Security", "Security"),
            ("Email", "Email"),
            ("Account/Access", "Account/Access"),
            ("Application", "Application"),
            ("Database", "Database"),
            ("Other", "Other"),
        ],
        validators=[Optional()],
    )


class AssetForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    asset_type = SelectField(
        "Type",
        choices=[
            ("hardware", "Hardware"),
            ("software", "Software"),
            ("network", "Network"),
            ("other", "Other"),
        ],
    )
    serial_number = StringField(
        "Serial Number", validators=[Optional(), Length(max=100)]
    )
    model = StringField("Model", validators=[Optional(), Length(max=100)])
    manufacturer = StringField("Manufacturer", validators=[Optional(), Length(max=100)])
    assigned_to = SelectField("Assigned To", coerce=int, validators=[Optional()])
    location = StringField("Location", validators=[Optional(), Length(max=200)])
    status = SelectField(
        "Status",
        choices=[
            ("active", "Active"),
            ("maintenance", "Maintenance"),
            ("retired", "Retired"),
            ("available", "Available"),
        ],
    )
    purchase_date = DateField("Purchase Date", validators=[Optional()])
    warranty_expiry = DateField("Warranty Expiry", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()])


class AutomationRuleForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional()])
    trigger_type = SelectField(
        "Trigger Type",
        choices=[
            ("ticket_created", "Ticket Created"),
            ("ticket_updated", "Ticket Updated"),
            ("sla_breach", "SLA Breach Imminent"),
            ("status_changed", "Status Changed"),
        ],
    )
    action_type = SelectField(
        "Action Type",
        choices=[
            ("assign", "Auto Assign"),
            ("notify", "Send Notification"),
            ("escalate", "Escalate"),
            ("update_field", "Update Field"),
        ],
    )
    is_active = BooleanField("Active")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=8, max=128),
            Regexp(_PASSWORD_REGEX, message=_PASSWORD_REGEX_MSG),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password")],
    )


class AttachmentForm(FlaskForm):
    file = FileField(
        "File",
        validators=[
            DataRequired(),
        ],
    )


class AdminResetPasswordForm(FlaskForm):
    """Confirmation form for an admin-initiated password reset.

    The new password is generated server-side (never typed by the admin)
    and is emailed to the user, so this form only carries the policy
    checkbox.
    """
    must_change_password = BooleanField(
        "Force user to change password on next login",
        default=True,
    )


class SystemSettingsForm(FlaskForm):
    company_name = StringField(
        "Company name",
        validators=[DataRequired(), Length(min=2, max=64)],
        description=(
            "Displayed as \"<value> ServiceDesk\" on every page and dashboard."
        ),
    )


class MailSettingsForm(FlaskForm):
    mail_server = StringField(
        "SMTP server",
        validators=[Optional(), Length(max=255)],
        description="Hostname of your SMTP relay (e.g. smtp.gmail.com).",
    )
    mail_port = IntegerField(
        "SMTP port",
        validators=[Optional(), NumberRange(min=1, max=65535)],
        description="Common values: 25, 465 (SSL), 587 (TLS).",
    )
    mail_use_tls = BooleanField("Use TLS/STARTTLS")
    mail_username = StringField(
        "Username",
        validators=[Optional(), Length(max=255)],
        description="Usually your full email address.",
    )
    mail_password = PasswordField(
        "Password",
        validators=[Optional(), Length(max=255)],
        description="For Gmail/Outlook use an app password.",
    )
    mail_default_sender = StringField(
        "Default sender",
        validators=[Optional(), Length(max=255)],
        description=(
            "From-address shown to recipients. Either a plain email "
            "(noreply@acme.com) or 'Name <noreply@acme.com>'."
        ),
    )


class TestEmailForm(FlaskForm):
    recipient = StringField(
        "Send test email to",
        validators=[DataRequired(), Email(), Length(max=255)],
    )

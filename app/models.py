from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256))
    full_name = db.Column(db.String(128))
    role = db.Column(db.String(20), default="user")
    department = db.Column(db.String(64))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=False)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tickets_created = db.relationship(
        "Ticket", foreign_keys="Ticket.created_by", backref="creator", lazy="dynamic"
    )
    tickets_assigned = db.relationship(
        "Ticket", foreign_keys="Ticket.assigned_to", backref="assignee", lazy="dynamic"
    )
    articles = db.relationship("Article", backref="author", lazy="dynamic")
    comments = db.relationship("Comment", backref="user", lazy="dynamic")
    assets = db.relationship("Asset", backref="owner", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == "admin"

    def is_agent(self):
        return self.role in ["admin", "agent"]

    def get_totp_uri(self):
        import pyotp

        return pyotp.totp.TOTP(self.two_factor_secret or "").provisioning_uri(
            self.username, issuer_name="ServiceDesk"
        )

    def verify_totp(self, code):
        import pyotp

        if not self.two_factor_secret:
            return False
        totp = pyotp.totp.TOTP(self.two_factor_secret)
        return totp.verify(code)

    def __repr__(self):
        return f"<User {self.username}>"


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type = db.Column(db.String(20), default="incident")
    status = db.Column(db.String(20), default="new", index=True)
    priority = db.Column(db.String(20), default="medium", index=True)
    category = db.Column(db.String(64), index=True)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))

    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"))

    sla_deadline = db.Column(db.DateTime)
    first_response_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    comments = db.relationship(
        "Comment", backref="ticket", lazy="dynamic", cascade="all, delete-orphan"
    )
    attachments = db.relationship(
        "Attachment", backref="ticket", lazy="dynamic", cascade="all, delete-orphan"
    )
    audit_logs = db.relationship("AuditLog", backref="ticket", lazy="dynamic")

    @property
    def is_sla_breached(self):
        if self.sla_deadline and datetime.utcnow() > self.sla_deadline:
            if self.status not in ["resolved", "closed"]:
                return True
        return False

    @property
    def response_time(self):
        if self.first_response_at and self.created_at:
            return (self.first_response_at - self.created_at).total_seconds() / 3600
        return None

    @property
    def resolution_time(self):
        if self.resolved_at and self.created_at:
            return (self.resolved_at - self.created_at).total_seconds() / 3600
        return None

    def __repr__(self):
        return f"<Ticket {self.ticket_number}>"


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Comment {self.id} on Ticket {self.ticket_id}>"


class Article(db.Model):
    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(64), index=True)
    tags = db.Column(db.JSON)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), default="draft", index=True)
    version = db.Column(db.Integer, default=1)
    view_count = db.Column(db.Integer, default=0)
    helpful_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    versions = db.relationship(
        "ArticleVersion",
        backref="article",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Article {self.title}>"


class ArticleVersion(db.Model):
    __tablename__ = "article_versions"

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    def __repr__(self):
        return f"<ArticleVersion {self.article_id} v{self.version}>"


class Asset(db.Model):
    __tablename__ = "assets"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    asset_type = db.Column(db.String(50))
    serial_number = db.Column(db.String(100), unique=True)
    model = db.Column(db.String(100))
    manufacturer = db.Column(db.String(100))
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))
    location = db.Column(db.String(200))
    status = db.Column(db.String(20), default="active", index=True)
    purchase_date = db.Column(db.Date)
    warranty_expiry = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    tickets = db.relationship("Ticket", backref="asset", lazy="dynamic")

    def __repr__(self):
        return f"<Asset {self.name}>"


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    filepath = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Attachment {self.filename}>"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"))
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User", backref="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} on {self.entity_type} {self.entity_id}>"


class AutomationRule(db.Model):
    __tablename__ = "automation_rules"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    trigger_type = db.Column(db.String(50), nullable=False)
    trigger_conditions = db.Column(db.JSON)
    action_type = db.Column(db.String(50), nullable=False)
    action_config = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<AutomationRule {self.name}>"


class Settings(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    category = db.Column(db.String(50), default="general")
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Settings {self.key}>"

    @classmethod
    def get(cls, key, default=None):
        from app import db

        setting = cls.query.filter_by(key=key).first()
        if setting:
            return setting.value
        return default

    @classmethod
    def set(cls, key, value, category="general"):
        from app import db

        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = cls(key=key, value=value, category=category)
            db.session.add(setting)
        try:
            db.session.commit()
        except:
            db.session.rollback()
            raise

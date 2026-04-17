import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def get_database_uri():
    db_type = os.environ.get("DB_TYPE", "sqlite")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "servicedesk")
    db_user = os.environ.get("DB_USER", "servicedesk")
    db_password = os.environ.get("DB_PASSWORD", "")
    db_ssl_mode = os.environ.get("DB_SSL_MODE", "prefer")

    if db_type == "postgresql":
        uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        if db_ssl_mode != "disable":
            uri += f"?sslmode={db_ssl_mode}"
        return uri
    else:
        return "sqlite:///servicedesk.db"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is required")

    COMPANY_NAME = os.environ.get("COMPANY_NAME", "ServiceDesk")

    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 587)
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ["true", "on", "1"]
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() in [
        "true",
        "on",
        "1",
    ]
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER", "noreply@servicedesk.local"
    )

    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    SLA_CONFIG = {
        "critical": {"response_hours": 1, "resolution_hours": 4},
        "high": {"response_hours": 4, "resolution_hours": 8},
        "medium": {"response_hours": 8, "resolution_hours": 24},
        "low": {"response_hours": 24, "resolution_hours": 72},
    }

    UPLOAD_FOLDER = "uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    IT_CATEGORIES = [
        "Hardware",
        "Software",
        "Network",
        "Security",
        "Email",
        "Account/Access",
        "Application",
        "Database",
        "Other",
    ]

    TICKET_TYPES = ["incident", "request", "problem"]
    TICKET_STATUSES = [
        "new",
        "assigned",
        "in_progress",
        "pending",
        "resolved",
        "closed",
    ]
    TICKET_PRIORITIES = ["low", "medium", "high", "critical"]


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost"
    RATELIMIT_ENABLED = False
    # Use in-memory storage so tests don't need Redis
    RATELIMIT_STORAGE_URI = "memory://"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}

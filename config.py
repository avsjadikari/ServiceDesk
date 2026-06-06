import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def get_database_uri():
    db_type = os.environ.get("DB_TYPE", "sqlite").lower()

    if db_type == "postgresql":
        db_host = os.environ.get("DB_HOST", "localhost")
        db_port = os.environ.get("DB_PORT", "5432")
        db_name = os.environ.get("DB_NAME", "servicedesk")
        db_user = os.environ.get("DB_USER", "servicedesk")
        db_password = os.environ.get("DB_PASSWORD")

        if not db_password:
            raise ValueError(
                "DB_PASSWORD environment variable is required when DB_TYPE=postgresql. "
                "Set it in your .env file or deployment environment."
            )

        return f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    return "sqlite:///servicedesk.db"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is required")

    COMPANY_NAME = os.environ.get("COMPANY_NAME", "ServiceDesk")

    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

    MAIL_SERVER = os.environ.get("MAIL_SERVER") or "smtp.gmail.com"
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 587)
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ["true", "on", "1"]
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")

    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    WTF_CSRF_TIME_LIMIT = 60 * 60 * 4

    # Account lockout
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))
    PASSWORD_RESET_MAX_AGE = int(
        os.environ.get("PASSWORD_RESET_MAX_AGE", str(30 * 60))
    )  # 30 min

    # Markdown sanitization
    MARKDOWN_ALLOWED_TAGS = os.environ.get("MARKDOWN_ALLOWED_TAGS")

    # File upload restrictions
    UPLOAD_ALLOWED_EXTENSIONS = {
        "png", "jpg", "jpeg", "gif", "webp", "svg",
        "pdf",
        "txt", "csv", "log", "md",
        "doc", "docx", "xls", "xlsx", "ppt", "pptx",
        "odt", "ods", "odp",
        "zip", "gz", "tar",
    }
    UPLOAD_ALLOWED_MIME_PREFIXES = (
        "image/",
        "text/",
        "application/pdf",
        "application/zip",
        "application/x-gzip",
        "application/x-tar",
        "application/msword",
        "application/vnd.openxmlformats-officedocument",
        "application/vnd.ms-",
        "application/vnd.oasis.opendocument",
    )

    # Sentry (optional)
    SENTRY_DSN = os.environ.get("SENTRY_DSN")
    SENTRY_TRACES_SAMPLE_RATE = float(
        os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")
    )

    SLA_CONFIG = {
        "critical": {"response_hours": 1, "resolution_hours": 4},
        "high": {"response_hours": 4, "resolution_hours": 8},
        "medium": {"response_hours": 8, "resolution_hours": 24},
        "low": {"response_hours": 24, "resolution_hours": 72},
    }

    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
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
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    TALISMAN_ENABLED = False


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_ECHO = False
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    TALISMAN_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    TALISMAN_ENABLED = True
    TALISMAN_FORCE_HTTPS = os.environ.get("TALISMAN_FORCE_HTTPS", "true").lower() in (
        "true",
        "1",
        "yes",
    )


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

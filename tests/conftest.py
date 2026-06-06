import os
import sys
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-123456789")
os.environ.setdefault("FLASK_CONFIG", "testing")
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ["COMPANY_NAME"] = "ServiceDesk"

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


@pytest.fixture(scope="function")
def app(tmp_path):
    """Build a Flask app with a fresh, isolated SQLite database.

    The URI is set on the testing config **before** ``create_app`` runs so
    that ``db.init_app`` binds the engine to the temporary file rather
    than to the application's real database file.
    """
    import tempfile

    from app import create_app, db
    from config import TestingConfig

    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite", dir=str(tmp_path))
    os.close(db_fd)

    TestingConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

    app = create_app("testing")
    app.config["SERVER_NAME"] = "localhost"

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(scope="function")
def client(app, admin_user):
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["setup_complete"] = True
    return test_client


@pytest.fixture(scope="function")
def db(app):
    from app import db as database

    yield database


@pytest.fixture(scope="function")
def admin_user(app, db):
    from app.models import User

    user = User(
        username="admin",
        email="admin@test.com",
        full_name="Admin User",
        role="admin",
        department="IT",
        is_active=True,
    )
    user.set_password("Admin@123456")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture(scope="function")
def agent_user(app, db):
    from app.models import User

    user = User(
        username="agent",
        email="agent@test.com",
        full_name="Agent User",
        role="agent",
        department="Support",
        is_active=True,
    )
    user.set_password("Agent@123456")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture(scope="function")
def regular_user(app, db):
    from app.models import User

    user = User(
        username="user",
        email="user@test.com",
        full_name="Regular User",
        role="user",
        department="Operations",
        is_active=True,
    )
    user.set_password("User@123456")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture(scope="function")
def authenticated_client(client, app, admin_user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_user.id)
        sess["_fresh"] = True
        sess["setup_complete"] = True
    return client

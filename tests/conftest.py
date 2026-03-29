import os
import sys
import pytest

os.environ["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "test-secret-key-for-testing-123456789"
)
os.environ["FLASK_ENV"] = "testing"
os.environ["DB_TYPE"] = "sqlite"

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


@pytest.fixture(scope="session")
def app():
    from app import create_app, db

    app = create_app("development")
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SERVER_NAME"] = "localhost"

    with app.app_context():
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    from app import db as database

    with app.app_context():
        database.session.rollback()
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
    return client

import os
import sys
import pytest

# Set env vars BEFORE importing anything from the app
os.environ["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "test-secret-key-for-testing-123456789"
)
os.environ["FLASK_CONFIG"] = "testing"
os.environ["DB_TYPE"] = "sqlite"

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


@pytest.fixture(scope="session")
def app():
    from app import create_app, db as _db

    _app = create_app("testing")

    with _app.app_context():
        _db.create_all()

    yield _app

    with _app.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def db(app):
    """Provide a clean DB session per test using savepoints / rollback."""
    from app import db as _db

    with app.app_context():
        # Delete all rows before each test for isolation
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()
        yield _db
        _db.session.rollback()


@pytest.fixture(scope="function")
def admin_user(app, db):
    from app.models import User

    with app.app_context():
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
        # Re-query to get a bound instance within this context
        return db.session.get(User, user.id)


@pytest.fixture(scope="function")
def agent_user(app, db):
    from app.models import User

    with app.app_context():
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
        return db.session.get(User, user.id)


@pytest.fixture(scope="function")
def regular_user(app, db):
    from app.models import User

    with app.app_context():
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
        return db.session.get(User, user.id)


@pytest.fixture(scope="function")
def authenticated_client(client, app, admin_user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_user.id)
        sess["_fresh"] = True
    return client

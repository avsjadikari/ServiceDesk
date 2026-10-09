"""Flask extension singletons. Kept in one module so the app factory wires
them and every other module imports the same instances (e.g. ``from app import
db`` still resolves here via the package re-export)."""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()
# ponytail: blanket per-IP guard only. A NAT'd office shares one budget, so
# keep this generous and leave the tight limits on auth/write endpoints.
limiter = Limiter(
    key_func=get_remote_address, default_limits=["1000 per hour", "10000 per day"]
)

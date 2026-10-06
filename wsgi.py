"""WSGI entry point for production servers (gunicorn / uWSGI)."""
import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

app = create_app(os.environ.get("FLASK_CONFIG", "production"))

# Embedded nginx (Alpine image) and any TLS-terminating proxy set forwarded
# headers; trust them so request.remote_addr / request.is_secure / Talisman
# redirects behave correctly. Harmless with no proxy in front.
app = ProxyFix(app, x_for=1, x_proto=1)

"""WSGI entry point for production servers (gunicorn / uWSGI)."""
import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

app = create_app(os.environ.get("FLASK_CONFIG", "production"))

import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    if app.config.get("ENV") == "production" and debug:
        raise RuntimeError(
            "Refusing to start: FLASK_DEBUG=true is not allowed in production."
        )
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))
    app.run(host=host, port=port, debug=debug)

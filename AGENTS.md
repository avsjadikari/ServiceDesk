# Repository Guidelines

## Project Structure & Module Organization
`app/` contains the Flask application. Core setup lives in `app/__init__.py`, data models in `app/models.py`, shared form and utility code in `app/forms.py` and `app/utils.py`, and feature routes under `app/routes/` (`auth.py`, `tickets.py`, `assets.py`, `knowledge.py`, `analytics.py`, `portal.py`, `api.py`, `setup.py`). Jinja templates are grouped by feature in `app/templates/`. Tests live in `tests/` with shared fixtures in `tests/conftest.py`. Top-level config and entry points are `config.py` and `run.py`. Local runtime data is stored under `instance/`.

## Build, Test, and Development Commands
Create an environment and install dependencies with `python -m venv .venv && source .venv/bin/activate` and `pip install -r requirements.txt`. Run the app locally with `python run.py`, then complete first-time setup at `/setup`. Run the full test suite with `pytest`. Generate coverage locally with `pytest --cov=app --cov-report=html`.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, `snake_case` for functions and variables, `PascalCase` for SQLAlchemy models and WTForms classes, and short route modules named by feature. Keep templates grouped by feature and name them by action, for example `tickets/view.html` or `auth/login.html`. Match the repository’s current style before introducing new abstractions. No formatter or linter is configured here, so keep changes PEP 8-aligned and consistent with adjacent code.

## Testing Guidelines
Tests use `pytest`, `pytest-flask`, and `pytest-cov`. Add new tests in `tests/test_<feature>.py` and reuse fixtures from `tests/conftest.py` where possible. The test suite uses an in-memory SQLite database and disables CSRF, so feature tests should prefer client requests over manual unit scaffolding. Run `pytest` before opening a PR; use coverage output when touching app factory, auth, or persistence logic.

The `client` fixture depends on `admin_user` so the setup-gate middleware always finds at least one admin. The `authenticated_client` fixture pre-populates the flask-login session. Test session state set in `session_transaction()` is wiped by `auth.complete_login()` (which calls `session.clear()` to prevent session fixation), so any code that depends on session values surviving across `client.post("/login", ...)` must be re-set inside the test.

## Commit & Pull Request Guidelines
Recent history uses short, imperative commit subjects such as `Fix db_init to support SQLite` and `Add Python virtual environment for development dependencies`. Keep commits focused and describe the user-visible or technical change directly. Pull requests should include a concise summary, impacted areas, test results, and screenshots for template/UI changes. Link the relevant issue or requirement when one exists.

## Security & Configuration Tips
Do not commit real secrets in `.env`. Use SQLite for local development and PostgreSQL for production as documented in `README.md`. Review `SECURITY.md` when changing authentication, rate limiting, session handling, or setup flows.

The app uses `secrets` for password reset tokens (`app/security.py`), Flask-Limiter for per-IP and per-endpoint rate limits, Flask-Talisman in production for security headers and HSTS, and `itsdangerous` to sign reset tokens. The default seed accounts in `__init__.py` get randomly generated passwords logged at startup; never set a hardcoded default password. Account lockout (`LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCKOUT_MINUTES`) is enforced in `auth.login`. Markdown rendered into pages goes through the `| markdown_safe` Jinja filter, which sanitises with bleach.

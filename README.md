# ServiceDesk Application

Enterprise IT Service Management system built with Python Flask.

## Features

- **Ticket Management**: Create, assign, track, and resolve support tickets
- **Knowledge Base**: Self-service articles with full-text search
- **Asset Management**: Track IT assets and link to tickets
- **Automation**: Auto-assignment, SLA management, workflow rules
- **Analytics**: Dashboard with metrics, charts, and SLA compliance
- **Self-Service Portal**: Customer-facing ticket submission and tracking
- **Multi-theme Support**: Blue, green, purple, red, light, and dark themes
- **Two-Factor Authentication (2FA)**: TOTP-based 2FA using authenticator apps
- **Rate Limiting**: Protection against brute-force attacks
- **Email Notifications**: Automatic notifications for ticket events

## Tech Stack

- **Backend**: Python 3.10+, Flask 3.x
- **Database**: SQLite (dev), PostgreSQL (prod)
- **ORM**: SQLAlchemy
- **Authentication**: Flask-Login
- **Frontend**: Bootstrap 5, Chart.js
- **Forms**: Flask-WTF
- **Security**: Flask-Limiter, PyOTP (2FA)

## Prerequisites

- Python 3.10 or higher
- PostgreSQL (for production)
- pip

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ServiceDesk
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
# Database Configuration
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=servicedesk
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# Security - Generate a secure key:
# python -c "import secrets; print(secrets.token_hex(64))"
SECRET_KEY=your-generated-secret-key

# Company Name
COMPANY_NAME=YourCompany

# Flask
FLASK_ENV=development
FLASK_DEBUG=true
```

### 5. Run the Application

```bash
python run.py
```

The application will be available at `http://localhost:5000`

### 6. First-Time Setup

1. Open `http://localhost:5000/setup` in your browser
2. Enter your company name
3. Configure database settings
4. Create admin account
5. Complete setup

## Default Users

After initial setup, the following users are created (password must be changed on first login):

| Username | Password | Role |
|----------|----------|------|
| admin | Admin@123456 | Admin |
| agent | Agent@123456 | Agent |
| user | User@123456 | User |

## Password Requirements

- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character (@$!%*?&)

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-flask

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

## Project Structure

```
ServiceDesk/
├── app/
│   ├── __init__.py          # App factory
│   ├── models.py            # Database models
│   ├── forms.py             # WTForms
│   ├── utils.py             # Utility functions
│   ├── routes/
│   │   ├── auth.py          # Authentication
│   │   ├── main.py          # Dashboard
│   │   ├── tickets.py       # Ticket management
│   │   ├── knowledge.py     # Knowledge base
│   │   ├── assets.py        # Asset management
│   │   ├── analytics.py     # Reporting
│   │   ├── portal.py       # Self-service portal
│   │   ├── api.py           # REST API
│   │   └── setup.py         # Setup wizard
│   └── templates/           # Jinja2 templates
├── tests/                   # Test suite
├── config.py                # Configuration
├── run.py                   # Application entry point
├── requirements.txt         # Dependencies
├── .env                     # Environment variables
├── SECURITY.md              # Security documentation
└── SPEC.md                  # Application specification
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Current user

### Tickets
- `GET /api/tickets` - List tickets
- `POST /api/tickets` - Create ticket
- `GET /api/tickets/<id>` - Get ticket
- `PUT /api/tickets/<id>` - Update ticket
- `DELETE /api/tickets/<id>` - Delete ticket

### Knowledge Base
- `GET /api/articles` - List articles
- `POST /api/articles` - Create article
- `GET /api/articles/<id>` - Get article
- `GET /api/articles/search?q=` - Search articles

### Assets
- `GET /api/assets` - List assets
- `POST /api/assets` - Create asset
- `GET /api/assets/<id>` - Get asset
- `PUT /api/assets/<id>` - Update asset

### Analytics
- `GET /api/analytics/dashboard` - Dashboard metrics
- `GET /api/analytics/tickets` - Ticket analytics
- `GET /api/analytics/sla` - SLA compliance

## Enterprise Features

### Implemented
- Role-based access control (Admin, Agent, User)
- SLA management with configurable response/resolution times
- Audit logging
- Multi-theme support
- Database backup/restore

### Recommended for Production
- Enable HTTPS/SSL
- Configure LDAP/AD integration
- Set up email notifications
- Implement 2FA
- Add API rate limiting
- Configure log aggregation
- Set up database encryption at rest
- Configure automated backups

## Security Considerations

See [SECURITY.md](SECURITY.md) for detailed security recommendations.

## Troubleshooting

### Database Connection Issues

1. Ensure PostgreSQL is running
2. Verify credentials in `.env`
3. Check database exists: `createdb servicedesk`

### Import Errors

```bash
pip install -r requirements.txt
```

### Session Errors

Make sure `SECRET_KEY` is set in `.env`

## License

MIT License

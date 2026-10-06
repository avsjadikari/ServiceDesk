# ServiceDesk Application Specification

## 1. Project Overview

- **Project Name**: ServiceDesk Pro
- **Type**: Full-stack Web Application (Python Flask)
- **Core Functionality**: Enterprise IT Service Management system for managing incidents, requests, problems, knowledge base, and IT assets
- **Target Users**: IT Support Teams, End Users, IT Managers, System Administrators

## 2. Technology Stack

- **Backend**: Python 3.10+, Flask 3.x
- **Database**: SQLite (development), PostgreSQL (production-ready)
- **ORM**: SQLAlchemy with Flask-SQLAlchemy & Flask-Migrate (Alembic)
- **Authentication**: Flask-Login with role-based access control and account lockout
- **Forms**: Flask-WTF with CSRF protection
- **Internationalization (i18n)**: Lightweight zero-dependency JSON catalogs (`app/i18n.py`)
- **Frontend**: Bootstrap 5 (with RTL direction support), Chart.js, HTML5 Drag-and-Drop API, DataTables
- **Security**: Flask-Limiter, Flask-Talisman, Bleach, itsdangerous, PyOTP (2FA)
- **Email**: Flask-Mail
- **API**: RESTful Flask API & asynchronous JSON endpoints

## 3. UI/UX Specification

### Layout Structure
- **Navigation**: Fixed top navbar with collapsible sidebar, theme selector, and language switcher dropdown
- **Dashboard**: Operational grid with 14-day trendline chart, real-time SLA breach alert banner, and agent metrics
- **Kanban Board**: 5-column HTML5 drag-and-drop workflow board (`/tickets/board`) with instant status transitions
- **Customer Portal**: Search hero, quick action service category cards, KB spotlight, and 5-stage ticket lifecycle stepper
- **Content Areas**: Responsive containers with breadcrumbs and view toggles
- **Tables**: DataTables with search, sort, pagination, and status badges

### Visual Design
- **Color Palette**:
  - Primary: `#2563eb` (Blue)
  - Secondary: `#64748b` (Slate)
  - Success: `#10b981` (Green)
  - Warning: `#f59e0b` (Amber)
  - Danger: `#ef4444` (Red)
  - Background: `#f8fafc` (Light gray)
  - Card Background: `#ffffff`
  - Text Primary: `#1e293b`
  - Text Secondary: `#64748b`

- **Typography**:
  - Font Family: 'Inter', system-ui, sans-serif
  - Headings: 600 weight, 1.25rem-2rem
  - Body: 400 weight, 0.875rem-1rem

- **Spacing**: 8px base unit (0.5rem, 1rem, 1.5rem, 2rem)

- **Visual Effects**:
  - Card shadows: `0 1px 3px rgba(0,0,0,0.1)`
  - Hover transitions: 150ms ease
  - Border radius: 0.375rem

### Internationalization & Directionality
- **Supported Directions**: Left-to-Right (`ltr`) for default languages, Right-to-Left (`rtl`) for Arabic (`ar`)
- **Direction Attribute**: Dynamic `<html lang="{{ current_lang }}" dir="{{ current_lang_dir }}">`
- **RTL Styling**: Automatic margin/padding mirroring and text alignment adjustment for RTL languages

### Responsive Breakpoints
- Mobile: < 768px
- Tablet: 768px - 1024px
- Desktop: > 1024px


## 4. Component Specification

### 4.1 Ticket Management System

#### Ticket Types
- **Incident**: Unplanned interruption to IT service
- **Request**: User's request for information or assistance
- **Problem**: Underlying cause of one or more incidents

#### Ticket Fields
| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Auto-generated ticket number |
| title | String(200) | Brief description |
| description | Text | Detailed information |
| type | Enum | incident/request/problem |
| status | Enum | open/in_progress/pending/resolved/closed |
| priority | Enum | low/medium/high/critical |
| category | String | Issue category |
| assigned_to | FK(User) | Assigned agent |
| created_by | FK(User) | Requester |
| sla_deadline | DateTime | SLA target time |
| resolved_at | DateTime | Resolution timestamp |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Last update |

#### SLA Configuration
- Critical: 1 hour response, 4 hours resolution
- High: 4 hours response, 8 hours resolution
- Medium: 8 hours response, 24 hours resolution
- Low: 24 hours response, 72 hours resolution

#### Ticket Lifecycle
```
New → Assigned → In Progress → Pending → Resolved → Closed
         ↓
      Reopened (if needed)
```

#### Views & Workflow Interaction
- **Table List View**: Paginated, sortable, filterable DataTables view
- **Kanban Workflow Board (`/tickets/board`)**: Visual 5-stage drag-and-drop board (`open`, `in_progress`, `pending`, `resolved`, `closed`) with AJAX status synchronization (`POST /tickets/<id>/update-status`) and optimistic UI updates
- **Ticket Lifecycle Stepper**: 5-step visual progress stepper on ticket detail view (`app/templates/tickets/view.html`, `app/templates/portal/view_ticket.html`)

### 4.2 Knowledge Base

#### Article Fields
| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Auto-generated ID |
| title | String(200) | Article title |
| content | Text | Markdown content |
| category | String | Article category |
| tags | JSON | Array of tags |
| author | FK(User) | Author |
| status | Enum | draft/published/archived |
| version | Integer | Version number |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Last update |

#### Features
- Full-text search
- Tag-based filtering
- Version history tracking
- Related articles suggestions
- Article voting/rating

### 4.3 Self-Service Portal

#### User Features
- Search hero for instant knowledge discovery
- Service category quick-action cards
- Submit new tickets (incident/request)
- View own tickets with 5-stage visual lifecycle stepper
- Search knowledge base
- Update ticket details
- Add comments/notes
- Attach files
- Rate resolution

### 4.4 Automation & Workflow Engine

#### Automation Rules
| Rule Type | Trigger | Action |
|-----------|---------|--------|
| Auto-assign | New ticket created | Assign to team/agent |
| Auto-categorize | Ticket created | Set category based on keywords |
| Escalation | SLA breach imminent | Notify supervisor |
| Notification | Status changed | Email/SMS to requester |
| Approval | High-value request | Send for approval |

#### Workflow Templates
- New Employee Onboarding
- Password Reset
- Hardware Request
- Software Installation
- Access Request

### 4.5 Reporting & Analytics

#### Operational Dashboard (`/`)
- Real-time SLA breach alert banner with quick filter/jump
- 14-day ticket activity trend chart (Created vs. Resolved daily velocity)
- Agent performance metrics (Resolved count, Avg resolution time, Open load)

#### Interactive Analytics Suite (`/analytics`)
- Dynamic timeframe filtering: 7 Days, 30 Days, 90 Days
- Time-series ticket volume chart (Created vs. Resolved)
- Category volume distribution breakdown chart
- SLA compliance metrics and Mean Time to Resolution (MTTR in hours)
- One-click CSV export (`/analytics/export?days=N`)

### 4.6 Communication Tools

#### Internal Features
- Ticket comments/notes
- @mentions for agents
- Activity timeline
- Internal announcements

#### External Channels
- Email integration (SMTP)
- Web form submissions
- Phone ticket entry (placeholder)

### 4.7 Asset Management

#### Asset Fields
| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Asset ID |
| name | String(200) | Asset name |
| type | String | Hardware/Software |
| serial_number | String | Serial number |
| assigned_to | FK(User) | Current owner |
| location | String | Physical location |
| status | Enum | active/maintenance/retired |
| purchase_date | Date | Purchase date |
| warranty_expiry | Date | Warranty end |

#### Asset-Ticket Linking
- Tickets can be linked to assets
- Asset history shows related tickets

### 4.8 Internationalization (i18n) System

#### Architecture
- **Catalog Format**: Lightweight zero-dependency JSON catalogs located in `app/translations/`
- **Supported Locales**:
  - `en` – English (default, LTR)
  - `es` – Spanish (Español, LTR)
  - `fr` – French (Français, LTR)
  - `de` – German (Deutsch, LTR)
  - `ja` – Japanese (日本語, LTR)
  - `ar` – Arabic (العربية, RTL layout)
  - `si` – Sinhala (සිංහල, LTR)
- **Language Resolution Order**:
  1. Query parameter (`?lang=<code>`)
  2. User session (`session['lang']`)
  3. HTTP header negotiation (`request.accept_languages.best_match()`)
  4. Fallback default (`en`)
- **Template Helpers**: Jinja2 translation function `t(key, **kwargs)` with parameter interpolation
- **Context Processors**: `current_lang`, `current_lang_dir`, `supported_languages`
- **Security & Redirection**:
  - Route `GET /set-lang/<lang_code>`
  - Allow-list validation prevents path traversal or locale catalog injection
  - Referrer origin verification against `request.host_url` prevents open redirect attacks


## 5. Database Schema

### Users Table
- id, username, email, password_hash, full_name, role, department, created_at

### Tickets Table
- id, title, description, type, status, priority, category, sla_deadline, created_by, assigned_to, resolved_at, created_at, updated_at

### Articles Table
- id, title, content, category, tags, author, status, version, created_at, updated_at

### Comments Table
- id, ticket_id, user_id, content, created_at

### Assets Table
- id, name, type, serial_number, assigned_to, location, status, purchase_date, warranty_expiry

### Audit Logs Table
- id, user_id, action, entity_type, entity_id, details, created_at

## 6. Endpoints & Feature Routes

### Authentication
- GET /login (LoginPage) / POST /login (email+password credentials; redirects to 2FA when enabled)
- GET|POST /login-2fa (TOTP code or recovery-code verification; CSRF token rendered & enforced)
- POST /auth/logout
- GET /forgot-password
- POST /reset-password/<token>
- GET /api/auth/me

### Tickets & Workflow
- GET /tickets
- POST /tickets/create
- GET /tickets/<id>
- POST /tickets/<id>/edit
- GET /tickets/board (Visual HTML5 drag-and-drop Kanban workflow board)
- POST /tickets/<id>/update-status (AJAX status synchronization with JSON payload)
- POST /tickets/<id>/comments
- POST /tickets/<id>/attachments
- GET /attachments/<id>
- GET /api/tickets (REST)
- POST /api/tickets (REST)
- GET /api/tickets/<id> (REST)
- PUT /api/tickets/<id> (REST)
- DELETE /api/tickets/<id> (REST)

### Internationalization
- GET /set-lang/<lang_code> (Language switcher with safe referrer redirection)

### Knowledge Base
- GET /knowledge
- POST /knowledge/create
- GET /knowledge/<id>
- GET /api/articles
- POST /api/articles
- GET /api/articles/<id>
- PUT /api/articles/<id>
- GET /api/articles/search?q=

### Assets
- GET /assets
- POST /assets/create
- GET /assets/<id>
- GET /api/assets
- POST /api/assets
- GET /api/assets/<id>
- PUT /api/assets/<id>

### Analytics
- GET /analytics/ (Interactive analytics suite UI with timeframe filters)
- GET /analytics/tickets?days=N (Time-series created vs resolved JSON)
- GET /analytics/categories (Category distribution volume JSON)
- GET /analytics/sla (SLA compliance percentage & MTTR metrics JSON)
- GET /analytics/export?days=N (Streaming CSV export of analytics data)
- GET /api/analytics/dashboard (REST)

## 7. Acceptance Criteria

### Core Functionality
- [x] Users can register and login
- [x] Agents can create, assign, and resolve tickets
- [x] Users can submit and track their tickets
- [x] SLA timers track and display correctly
- [x] Knowledge base articles can be created and searched
- [x] Dashboard displays accurate operational metrics
- [x] Kanban board enables visual drag-and-drop workflow status updates
- [x] Interactive analytics provides 7/30/90-day timeframes, MTTR metrics, and CSV export
- [x] Multi-language support functions across 7 languages including RTL layout for Arabic
- [x] Open redirect protection enforced on language switcher

### UI/UX
- [x] Responsive design works on mobile/tablet/desktop
- [x] Navigation is intuitive with theme switcher and language selector
- [x] Forms validate input properly with CSRF protection
- [x] Loading states shown appropriately
- [x] Error messages are clear
- [x] Customer self-service portal provides quick category access and 5-stage lifecycle stepper

### Automation
- [x] Auto-assignment rules work
- [x] Email notifications sent on status change
- [x] SLA breach alert banner and warnings displayed

### Analytics
- [x] Charts render correctly (14-day trendline, velocity, category breakdown)
- [x] Data refreshes dynamically based on selected timeframe
- [x] Date filters and timeframe selectors work
- [x] CSV export streams ticket metrics reliably

## 8. Project Structure

```
ServiceDesk/
├── app/
│   ├── __init__.py          # App factory, extension registration, gatekeeper
│   ├── models.py            # SQLAlchemy models (User, Ticket, Article, Asset, …)
│   ├── forms.py             # WTForms form classes & validators
│   ├── utils.py             # Helper functions (ticket numbers, SLA, automation)
│   ├── i18n.py              # Zero-dependency JSON i18n engine & context processor
│   ├── sanitize.py          # Bleach HTML/markdown sanitization filter
│   ├── security.py          # Token serialization & password reset security
│   ├── email_utils.py       # Notification mailer utilities
│   ├── translations/        # Lightweight JSON localization catalogs
│   │   ├── en.json          # English (default)
│   │   ├── es.json          # Spanish
│   │   ├── fr.json          # French
│   │   ├── de.json          # German
│   │   ├── ja.json          # Japanese
│   │   ├── ar.json          # Arabic (RTL)
│   │   └── si.json          # Sinhala
│   ├── routes/
│   │   ├── auth.py          # Authentication, 2FA, password reset
│   │   ├── main.py          # Operational dashboard, /set-lang
│   │   ├── tickets.py       # Ticket CRUD, Kanban board, AJAX status updates
│   │   ├── knowledge.py     # Knowledge base articles
│   │   ├── assets.py        # IT asset management
│   │   ├── analytics.py     # Interactive analytics, timeframes, CSV export
│   │   ├── portal.py        # Customer self-service portal
│   │   ├── api.py           # REST API endpoints
│   │   └── setup.py         # First-time setup wizard
│   ├── templates/           # Jinja2 UI templates (grouped by feature)
│   └── static/
│       ├── css/             # Stylesheets & RTL adjustments
│       ├── js/              # Client-side scripts (Kanban DND, charts, etc.)
│       └── img/             # Static assets
├── migrations/              # Flask-Migrate / Alembic database migrations
├── tests/                   # Pytest suite (119 tests covering all features)
├── config.py                # Configuration classes (development / production)
├── run.py                   # Application entry point
├── requirements.txt         # Python dependencies
├── SECURITY.md              # Security review & hardening documentation
├── SPEC.md                  # System specifications
└── README.md                # Project overview and setup guide
```


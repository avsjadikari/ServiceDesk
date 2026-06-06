# ServiceDesk Application Specification

## 1. Project Overview

- **Project Name**: ServiceDesk Pro
- **Type**: Full-stack Web Application (Python Flask)
- **Core Functionality**: Enterprise IT Service Management system for managing incidents, requests, problems, knowledge base, and IT assets
- **Target Users**: IT Support Teams, End Users, IT Managers, System Administrators

## 2. Technology Stack

- **Backend**: Python 3.10+, Flask 3.x
- **Database**: SQLite (development), PostgreSQL (production-ready)
- **ORM**: SQLAlchemy with Flask-SQLAlchemy
- **Authentication**: Flask-Login
- **Forms**: Flask-WTF
- **Frontend**: Bootstrap 5, Chart.js, DataTables
- **Email**: Flask-Mail
- **Task Queue**: Celery (optional for async tasks)
- **API**: RESTful Flask API

## 3. UI/UX Specification

### Layout Structure
- **Navigation**: Fixed top navbar with collapsible sidebar
- **Dashboard**: Grid-based card layout with charts
- **Content Areas**: Responsive containers with breadcrumbs
- **Tables**: DataTables with search, sort, pagination

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
- Submit new tickets (incident/request)
- View own tickets with status
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

#### Dashboard Metrics
- Total tickets (open/closed)
- Average response time
- Average resolution time
- SLA compliance rate
- Tickets by category/priority
- Agent performance
- Trend over time

#### Charts
- Line chart: Tickets over time
- Bar chart: Tickets by category
- Pie chart: Tickets by status
- Gauge: SLA compliance

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

## 6. API Endpoints

### Authentication
- POST /api/auth/login
- POST /api/auth/logout
- GET /api/auth/me

### Tickets
- GET /api/tickets
- POST /api/tickets
- GET /api/tickets/<id>
- PUT /api/tickets/<id>
- DELETE /api/tickets/<id>
- POST /api/tickets/<id>/comments

### Knowledge Base
- GET /api/articles
- POST /api/articles
- GET /api/articles/<id>
- PUT /api/articles/<id>
- GET /api/articles/search?q=

### Assets
- GET /api/assets
- POST /api/assets
- GET /api/assets/<id>
- PUT /api/assets/<id>

### Analytics
- GET /api/analytics/dashboard
- GET /api/analytics/tickets
- GET /api/analytics/sla

## 7. Acceptance Criteria

### Core Functionality
- [ ] Users can register and login
- [ ] Agents can create, assign, and resolve tickets
- [ ] Users can submit and track their tickets
- [ ] SLA timers track and display correctly
- [ ] Knowledge base articles can be created and searched
- [ ] Dashboard displays accurate metrics

### UI/UX
- [ ] Responsive design works on mobile/tablet/desktop
- [ ] Navigation is intuitive
- [ ] Forms validate input properly
- [ ] Loading states shown appropriately
- [ ] Error messages are clear

### Automation
- [ ] Auto-assignment rules work
- [ ] Email notifications sent on status change
- [ ] SLA warnings displayed

### Analytics
- [ ] Charts render correctly
- [ ] Data refreshes appropriately
- [ ] Date filters work

## 8. Project Structure

```
servicedesk/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── forms.py
│   ├── utils.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── main.py
│   │   ├── tickets.py
│   │   ├── knowledge.py
│   │   ├── assets.py
│   │   ├── analytics.py
│   │   └── api.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── auth/
│   │   ├── tickets/
│   │   ├── knowledge/
│   │   ├── assets/
│   │   └── analytics/
│   └── static/
│       ├── css/
│       ├── js/
│       └── img/
├── migrations/
├── tests/
├── requirements.txt
├── config.py
├── run.py
└── README.md
```

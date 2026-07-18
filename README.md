# RequestFlow
[![CI](https://github.com/ForhaadM/requestflow/actions/workflows/ci.yml/badge.svg)](https://github.com/ForhaadM/requestflow/actions/workflows/ci.yml)

A full-stack internal request management system for tracking approvals, reviews, and SLAs.

**Live site:** https://requestflow-app.com
**Backend API:** https://api.requestflow-app.com

## Overview / Problem Statement

Internal teams routinely need a way to submit requests (access, hardware, software, bug reports), route them to the right reviewer, and track their status from submission to resolution. RequestFlow models this end-to-end workflow, including a conditional business rule requiring justification on rejected requests, SLA deadlines by priority, and a full audit trail of who reviewed what and when.

This project was built to demonstrate both software engineering skills (schema design, REST API development, authentication, containerization, cloud deployment) and business analysis skills (requirements modeling, workflow design, deliberate scoping decisions) relevant to both SWE and BA roles.

## Features

- **Request submission** — requesters submit categorized requests (access, hardware, software, bug report, and more) with a priority level
- **Request comments** — requesters can add follow-up comments to their own existing requests (e.g. to add info they forgot), with a 750-character limit
- **Request cancellation** — a requester can withdraw their own open request, tracked distinctly from reviewer-driven closures
- **Review workflow** — reviewers claim, then approve or reject requests; rejections (and any override of a prior decision) require a written justification, enforced at the application layer
- **SLA tracking** — deadlines computed from priority (Urgent: 2h, High: 12h, Medium: 7d, Low: 2wk from creation), with a live countdown badge visible to requesters, reviewers, and admins on any request detail view, plus aggregate compliance stats on the admin dashboard
- **Role-based access** — requester, reviewer, and admin roles with distinct permissions
- **Authentication** — JWT-based auth with bcrypt password hashing; identity for all actions is derived from a verified token, never from client-supplied input; login is rate-limited to slow down brute-force attempts
- **AI chatbot assistant ("Flowy Assistant")** — a chat widget (Claude, tool-calling), scoped to the requester role, guides users through creating a request conversationally or answers general questions about request types; supports cancelling out of the guided flow at any point via button or natural language ("nevermind," "cancel," etc.); degrades gracefully to a "use the form instead" message if the Anthropic API is unavailable
- **Proactive duplicate detection** — before a request is created (via the form or the chatbot), it's checked against the requester's own open/in-progress requests and flagged if it looks like a likely duplicate
- **Admin analytics dashboard** — volume trends by category, unusual-activity spikes, average time-to-resolution, and SLA compliance, all by category/priority
- **Admin dashboard** — full visibility into all requests and reviews across the system, with the same expandable detail view available to requesters and reviewers, plus the ability to comment on any ticket and override a previous decision
- **Audit trail** — every review is its own timestamped record tied to the reviewer and the request
- **Threaded comments with role-aware access** — requesters can comment on their own requests; the reviewer currently holding a claim, or any admin, can also reply — even after a ticket is closed. Comments always show the real commenter's name, not just "you."

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy 2.0
- **Database:** PostgreSQL
- **Frontend:** React, Vite, Tailwind CSS
- **Authentication** — JWT-based auth with bcrypt password hashing; identity for all actions is derived from a verified token, never from client-supplied input; the token is stored in `sessionStorage` (scoped per-tab, cleared on tab close) rather than `localStorage`; login is rate-limited to slow down brute-force attempts
- **AI:** Anthropic Claude API (chatbot tool-calling, duplicate-detection classification)
- **Testing:** pytest + FastAPI TestClient (backend), Vitest + React Testing Library (frontend)
- **Infra:** Docker, Docker Compose, GitHub Actions (CI/CD)
- **Cloud:** AWS (RDS, EC2, Application Load Balancer, S3, CloudFront, Route 53, ACM)

## Data Model / Architecture

Four core entities: `users`, `requests`, `reviews`, and `comments`.

```
users                      requests                    reviews
─────                      ────────                    ───────
user_id (PK)         ┌───▶ request_id (PK)        ┌───▶ review_id (PK)
name                 │     requester_reference (FK)│     request_reference (FK)
email (unique)       │     request_type            │     reviewer_reference (FK)
password (hashed)    │     description             │     decision
role                 │     priority                │     comment_text
│     urgency_justification    │     reviewed_at
│     status                  │
│     claimed_by (FK)          │
│     created_at (tz-aware)     │
└──────┬───────────────────────┘
│
▼
comments
────────
comment_id (PK)
request_reference (FK)
commenter_reference (FK)
comment_text
created_at (tz-aware)
```

**Key design decisions:**
- **Reviews are a separate table, not a status column on requests** — a review is a distinct event with its own actor and timestamp, not a fixed attribute of a request. This also allows the audit trail to show *who* reviewed *what* and *when*, independent of the request itself.
- **Comments are a separate table**, following the same reasoning — a request can accumulate multiple comments over time, each with its own author and timestamp.
- **Roles live in a single `users` table with a `role` column**, rather than separate tables per role — all users share the same core attributes (name, email, password), and role is just a classification, not a structurally different entity.
- **Comment justification on rejection is enforced in application logic, not a database constraint** — this is a conditional rule (required only when `decision = 'NOT APPROVED'`) that depends on the relationship between two columns, which a simple `CHECK` constraint can't express cleanly. The database still enforces `NOT NULL`/`CHECK` constraints for everything that *is* a fixed, structural rule (foreign keys, allowed enum values).
- **Status is system-controlled, not client-controlled** — a request always starts at `open` via the database default; every subsequent transition goes through a role-checked route (claim, unclaim, review decision, cancellation, or a direct status update), and a request that's already been `approved`/`rejected` can only change via the review-override flow (admin-only, comment required) — never by a raw client-supplied status.
- **Timestamps are timezone-aware (`timestamptz`), not naive** — an earlier version used naive `timestamp` columns, which caused the browser to misinterpret UTC values as local time, silently shifting every displayed timestamp by the viewer's UTC offset. Migrated affected columns after confirming the database session's timezone was UTC throughout, making the conversion lossless.

## Live Deployment

RequestFlow is fully deployed on AWS with a custom domain and end-to-end HTTPS:

- **Frontend:** React (Vite) build hosted on S3, served via CloudFront (CDN + HTTPS), on `requestflow-app.com`
- **Backend:** FastAPI running in a Docker container on an EC2 instance, behind an Application Load Balancer terminating HTTPS on `api.requestflow-app.com`
- **Database:** Managed PostgreSQL via Amazon RDS, reachable only from the EC2 instance
- **Domain & certificates:** registered via Route 53; free TLS certificate issued and validated through AWS Certificate Manager

**Infrastructure decisions:**
- **RDS over self-managed Postgres** — managed backups, patching, and monitoring without operational overhead
- **EC2 + Docker over a managed container service** — chosen deliberately to build hands-on familiarity with core EC2 networking, security groups, and manual container deployment
- **Application Load Balancer for HTTPS termination** — rather than running TLS directly on the app or the EC2 instance, the ALB handles certificate management and HTTPS termination, forwarding plain HTTP internally to the container — the standard pattern for this kind of setup
- **Security groups scoped per-resource, least-privilege** — RDS only accepts connections from the EC2 instance's security group, EC2's application port only accepts connections from the ALB's security group (not the public internet directly), SSH access to EC2 is restricted to a known IP, and only the ALB's HTTPS port is open publicly
- **Environment-variable-driven configuration throughout** — no hardcoded credentials or hosts anywhere in the codebase; local development and production deployment run the same code with different `.env` files

For the full step-by-step deployment process, see [docs/deployment-runbook.md](docs/deployment-runbook.md).

## Getting Started (local development)

**Backend:**
1. Clone the repo
2. `cd backend`, copy `.env.example` to `.env` and fill in local values (`ANTHROPIC_API_KEY` is optional — the chatbot and duplicate-detection features just no-op/degrade gracefully without it)
3. From the project root: `docker compose up -d` (starts PostgreSQL)
4. `python3 -m venv venv && source venv/bin/activate`
5. `pip install -r requirements.txt --break-system-packages`
6. `alembic upgrade head` (applies database migrations — see [Database Migrations](#database-migrations) below)
7. `uvicorn main:app --reload`
8. API docs available at `http://127.0.0.1:8000/docs`

**Frontend:**
1. `cd frontend`, copy `.env.example` to `.env`
2. `npm install`
3. `npm run dev`

**Tests:**
```bash
# Backend
cd backend
pytest
pytest --cov=. --cov-report=term-missing

# Frontend
cd frontend
npm test
```

## Database Migrations

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/), reading DB connection info from the same `POSTGRES_*` environment variables used by `database.py` (no separate/hardcoded connection string in `alembic.ini`).

**Applying migrations (local dev):**
```bash
cd backend
alembic upgrade head
```

**Making a schema change:**
1. Edit `backend/models.py`
2. Generate a migration from the diff: `alembic revision --autogenerate -m "short description"`
3. **Review the generated file in `backend/alembic/versions/`** — autogenerate is a starting point, not a guarantee (e.g. it doesn't detect column renames, and won't know if a type/nullability change is actually safe against existing data)
4. Apply it locally: `alembic upgrade head`
5. Commit the migration file alongside the model change

Schema changes should **always** go through this workflow now — not manual `ALTER TABLE` statements against RDS. Manual DDL is exactly what caused a schema-drift incident (columns present in `models.py` but missing in production), which motivated adopting Alembic.

**CI enforces this automatically:** every push/PR runs `alembic upgrade head` followed by `alembic check` against a real Postgres instance, which fails the build if `models.py` and the migration history have diverged — so a forgotten migration is caught in CI instead of surfacing as a drift incident in production again.

## Project Structure
```
requestFlow/
├── backend/
│   ├── main.py                 # FastAPI routes
│   ├── models.py               # SQLAlchemy models (single source of truth for schema + enums)
│   ├── database.py             # DB connection, session management
│   ├── auth.py                 # Password hashing, JWT, auth dependency
│   ├── request_service.py      # Request/review business logic shared by routes + chatbot tools
│   ├── chat.py                 # /chat route
│   ├── chatbot.py              # Claude tool-calling loop (create/check requests, cancel flow)
│   ├── duplicate_detection.py  # Proactive duplicate-check (Claude classification)
│   ├── analytics.py            # Admin analytics aggregation, SLA compliance
│   ├── sla.py                  # SLA deadline computation by priority
│   ├── rate_limit.py           # In-memory per-process rate limiting
│   ├── timeutils.py            # Timezone-aware now() helper
│   ├── name_validation.py      # Registration name format validation
│   ├── password_rules.py       # Shared password requirement rules (client + server)
│   ├── alembic/                # Database migration scripts (env.py, versions/)
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tests/                  # pytest unit + integration tests
├── frontend/
│   ├── src/
│   │   ├── pages/       # Route-level components
│   │   ├── components/  # Shared UI components
│   │   ├── api/         # API client functions
│   │   ├── context/     # Auth + shared user-directory state
│   │   ├── lib/         # Client-side validation, SLA, sorting, nav-visibility utilities
│   │   └── test/        # Vitest setup
│   └── package.json
├── .github/workflows/ci.yml    # CI pipeline (backend tests + migration check, frontend tests + build)
├── docker-compose.yaml         # Local PostgreSQL container
└── docs/deployment-runbook.md  # AWS deployment runbook
```

## Screenshots

**Login / Registration** — real-time password requirements checklist
![Login page](docs/screenshots/register.png)

**New Request** — proactive duplicate detection
![New request form](docs/screenshots/request.png)

**My Requests** — SLA countdown, urgency justification, and comments
![My requests page](docs/screenshots/request.png)

**Flowy Assistant** — AI-guided request creation
![Chatbot main menu](docs/screenshots/flowy1.png)
![Chatbot creating a request](docs/screenshots/flowy2.png)

**Reviewer Queue** — SLA badges and requester contact info
![Reviewer queue](docs/screenshots/reviewer.png)

**Admin Dashboard** — analytics, volume trends, and SLA compliance
![Admin dashboard overview](docs/screenshots/admin1.png)
![Admin dashboard SLA compliance](docs/screenshots/admin2.png)
## Future Enhancements

- ~~Conversational agent for guided request submission via natural-language Q&A~~ — done, see [Features](#features)
- ~~Proactive duplicate detection~~ — done, see [Features](#features)
- ~~Admin analytics dashboard~~ — done, see [Features](#features)
- ~~Database migrations (Alembic)~~ — done. A real schema-drift incident (columns in `models.py` missing from production, caused by manual `ALTER TABLE` statements) motivated adopting Alembic; see [Database Migrations](#database-migrations)
- ~~SLA tracking~~ — done, see [Features](#features)
- ~~Request comments~~ — done, see [Features](#features)
- **Live queue updates** — list views (reviewer queue, admin dashboard, my requests) fetch once on page load; a request created elsewhere (e.g. via the chatbot, or by another user) doesn't appear until the page is refreshed. Polling or a WebSocket/SSE-based live-update mechanism is the natural next step — deliberately deferred as a v1 scoping decision given the added infrastructure complexity, not an oversight.
- **Invite/approval-based role assignment** — registration currently lets anyone self-select `requester`/`reviewer`/`admin` at signup (`RegisterPage.jsx`), which is intentional for a portfolio demo ("pick the role you want to demo") but is the first thing to change before this touches anything real
- **Shared-store rate limiting** — login/chat/duplicate-check are rate-limited (`rate_limit.py`), but the limiter is in-memory and per-process, so it only holds under a single backend instance; a multi-instance deployment needs a shared store (e.g. Redis) instead
- Audit history table tracking full status-change history per request (currently only the terminal decision is recorded)
- Auto-scaling / multi-AZ for the backend and database (currently single-instance, appropriate for a portfolio project but a documented gap versus production-grade HA)
- Reviewer/admin-specific chatbot capabilities (e.g. natural-language queue queries for reviewers, natural-language analytics queries for admins) — the chatbot is currently scoped to the requester role only, since its existing capabilities (request creation, status Q&A) have no real use case for the other two roles

## Author / Contact

Forhaad Miah |
[LinkedIn](https://linkedin.com/in/forhaad-miah) · [GitHub](https://github.com/ForhaadM) 

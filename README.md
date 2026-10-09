# SecureHelpDesk

[![Backend tests](https://github.com/Nonhlanhla111/securehelpdesk/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/Nonhlanhla111/securehelpdesk/actions/workflows/backend-tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Secure IT Help Desk & Incident Management System — FastAPI · React · SQLAlchemy · SQL Server

**Status: Phase 1 (backend API) and Phase 2 (React frontend) complete.**
Backend: authentication, RBAC, tickets, comments, attachments, audit logging,
security-event monitoring, dashboards, reports, 98 automated tests.
Frontend: login/register, role-aware dashboard, ticket list/detail with the
full workflow, admin screens for users and audit/security logs, light and
dark mode.

[![Security: A+](https://img.shields.io/badge/Security%20Headers-A%2B-brightgreen)](docs/security-assessment.md)

## Everything here is free

| Tool | Cost | Notes |
|---|---|---|
| VS Code, Git, GitHub | Free | GitHub free plan includes private repos |
| Python, FastAPI, SQLAlchemy, Pydantic, Pytest | Free / open source | |
| SQL Server **Express** or **Developer** edition | Free | Express: 10 GB DB limit. Developer: full features, non-production use |
| SSMS, ODBC Driver 18 | Free | |
| OWASP ZAP, Burp Suite **Community** | Free | |
| SonarQube for IDE (SonarLint), Snyk | Free | Snyk free tier has monthly test limits |

## Quick start (about 5 minutes, no database install needed)

Open the `securehelpdesk` folder in VS Code, then in the VS Code terminal (PowerShell):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
```

Generate a real secret and paste it into `.env` as `SECRET_KEY=...`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Run the tests, create your first admin, start the API:

```powershell
python -m pytest
python -m scripts.create_admin
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for the interactive Swagger UI. Click **Authorize** and paste a
token from `POST /api/auth/login`. You can also use `backend/api-tests.http` with the free
*REST Client* extension.

> If PowerShell blocks the activate script, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Running the frontend

In a **second** terminal (leave the backend running in the first one):

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Register an employee account there, or log
in with the admin account you created with `create_admin`. See
`frontend/README.md` for more detail.

## Deploying a free live demo (Render + Vercel)

- **Backend → [Render](https://render.com)**: a free Web Service. Free
  instances spin down after 15 minutes idle and take up to a minute to wake
  on the next request — expected for a demo, not a bug.
- **Frontend → [Vercel](https://vercel.com)**: a free static deploy, root
  directory `frontend`.
- **Database**: the demo runs on SQLite by default, which resets on every
  redeploy. That's fine for a portfolio demo; an `ADMIN_BOOTSTRAP_*` set of
  environment variables (see `.env.example`) recreates your admin login
  automatically every time, so the demo is never locked out.

Order matters a little because of CORS:
1. Deploy the backend first and note its URL.
2. Deploy the frontend with `VITE_API_URL` set to that backend URL.
3. Go back to Render and set `CORS_ORIGINS` to include the frontend's URL,
   then redeploy the backend once more.

## Switching to SQL Server (SSMS)

1. Install **SQL Server 2022 Express** (or Developer) and **SSMS**.
2. Install **ODBC Driver 18 for SQL Server** (Microsoft, free).
3. In SSMS, connect to `localhost\SQLEXPRESS`, right-click *Databases → New Database…* and name it `SecureHelpDesk`.
4. `pip install -r requirements-mssql.txt`
5. In `.env`, comment out the SQLite line and enable the SQL Server one:
   ```
   DATABASE_URL=mssql+pyodbc://@localhost\SQLEXPRESS/SecureHelpDesk?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes
   ```
6. Start the API. Tables are created automatically; refresh the database in SSMS to see them.

Troubleshooting: if the connection is refused, open *SQL Server Configuration Manager* and enable
**TCP/IP** and the **SQL Server Browser** service, or use `localhost,1433` instead of `localhost\SQLEXPRESS`.

> **Honest note:** the automated tests run on SQLite. The models avoid SQL Server pitfalls
> (NVARCHAR for user text, no multiple-cascade FKs), but the SQL Server path itself has not been
> exercised yet. Treat your first run against it as a test, and tell me about any error you see.

## Roles and what they can do

| | Employee | IT Support Agent | Administrator |
|---|---|---|---|
| Create tickets, comment, upload files | ✅ own | ✅ | ✅ |
| See tickets | own only | unassigned queue + own assigned | all |
| Accept / assign tickets | ❌ | accept for self | assign to anyone |
| Change priority / category / status | ❌ (can confirm or reject a resolution) | on assigned tickets | any |
| Internal (staff-only) notes, ticket history | ❌ | ✅ | ✅ |
| Manage users & roles, audit logs, security events | ❌ | ❌ | ✅ |
| Delete tickets | ❌ | ❌ | ✅ |

Workflow: **Open → Assigned → In Progress → Resolved → Closed** (see `docs/database.md` for diagrams).

## Security controls implemented (and tested)

| Control | Where | How it is tested |
|---|---|---|
| Argon2id password hashing | `security.py` | hash format asserted; never returned by the API |
| JWT auth with server-side logout (revocation list) | `deps.py`, `routers/auth.py` | token dead after logout |
| Password change revokes *all* sessions (`token_version`) | `models.User` | old tokens on two "devices" rejected |
| Role & active flag re-read from DB every request | `deps.get_current_user` | deactivate / role change takes effect instantly |
| RBAC on every route (`require_roles`) | `deps.py` | parametrized 403/401 matrix |
| Object-level auth (anti-IDOR): 404 for foreign tickets | `services.get_visible_ticket` | 5 probe types + attachments |
| Account lockout + per-IP rate limiting | `routers/auth.py`, `rate_limit.py` | 5 failures → lock; 11th request → 429 |
| No user enumeration (same message, equal timing) | login | responses compared |
| Input validation (types, lengths, enums, control chars) | `schemas.py` | 422 matrix |
| SQL injection safe (ORM parameters, LIKE wildcards escaped) | all queries | 5 payloads × search/login |
| XSS: JSON only, `nosniff`, strict CSP, output escaping left to React | `main.py` | header + content-type asserted |
| Safe file uploads (allow-list, size cap, magic bytes, random names, forced download) | `routers/attachments.py` | spoofing, traversal, oversize |
| Validation errors don't echo passwords; 500s don't leak internals | `main.py` | asserted |
| Audit log + security events (failed logins, lockouts, unauthorised access, role changes, rate limits, bad uploads) | `audit.py` | asserted per event |

I also broke five of these controls on purpose (mutation testing) and confirmed the test suite fails each time.

## Project layout

```
backend/
  app/
    main.py            app setup, security headers, error handlers
    config.py          settings from .env
    database.py        SQLAlchemy engine (SQLite or SQL Server)
    models.py          all tables
    schemas.py         request/response validation
    security.py        Argon2 + JWT
    deps.py            authentication + RBAC dependencies
    audit.py           audit-log & security-event helpers
    rate_limit.py      sliding-window limiter
    services.py        ticket access rules & history
    routers/           auth, users, tickets, attachments, logs, dashboard
  tests/               98 pytest tests
  scripts/create_admin.py
  api-tests.http       manual tests (REST Client)
frontend/
  src/
    api/client.js        axios instance (auth header, 401 handling)
    auth/AuthContext.jsx  login/register/logout state
    components/           sidebar, layout, chips, icons, loading states
    pages/                Login, Register, Dashboard, TicketList, TicketDetail,
                          NewTicket, Reports, AdminUsers, AdminLogs
    styles.css            design tokens + all styling (no CSS framework)
docs/database.md       ER + workflow diagrams (Mermaid)
```
## Security

This project includes RBAC, Argon2id password hashing, JWT auth, audit
logging, rate limiting, and object-level authorization (anti-IDOR checks).
The live deployment was also assessed against the
[Mozilla HTTP Observatory](https://observatory.mozilla.org) — see the full
[security assessment](security-assessment.md) for findings and fixes
(improved from a C/50 to an A+/115 score).


## Security testing tools (free) — suggested next steps

The header-based assessment above (Mozilla HTTP Observatory) covers HTTP
response header hardening. For deeper testing — crawling the running app
for vulnerabilities, intercepting live requests, static code analysis, and
dependency scanning — the following free tools are recommended:

1. **OWASP ZAP**: start the API, then *Automated Scan* against `http://localhost:8000`, or import `http://localhost:8000/openapi.json` for an API scan. *(Note: Windows SmartScreen may flag the installer as unrecognized — this is a known false positive for less-common installers; choose "More info → Run anyway" to proceed.)*
2. **Burp Community**: proxy your browser/REST calls; try Repeater on ticket IDs while logged in as a different employee.
3. **SonarQube for IDE**: install in VS Code; it flags issues as you type.
4. **Snyk**: `snyk test --file=backend/requirements.txt` (free account) for dependency vulnerabilities.

## Known limitations / roadmap

- [x] ~~Phase 2 — React frontend~~ (login, ticket list/detail, dashboards, admin screens)
- [ ] Password **reset** flow (needs an email step; can log the link in development)
- [ ] Unassign / release ticket; agent-to-agent reassignment
- [ ] Alembic migrations (tables currently come from `create_all`)
- [ ] Rate limiter is in-memory (single process); use Redis for multi-worker deployments
- [ ] Behind a reverse proxy, configure trusted proxy headers so audit logs record real client IPs
- [ ] Tokens are returned in JSON; the React phase should decide between memory storage and httpOnly cookies (+CSRF)

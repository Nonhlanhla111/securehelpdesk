# Threat Model — SecureHelpDesk

## Overview

This document is a STRIDE-based threat model for SecureHelpDesk, an IT Help
Desk & Incident Management System. It identifies the main threats the
system is exposed to, maps each to the specific controls implemented to
mitigate it, and notes residual risk where a control is partial or a future
improvement is planned.

**System summary:** FastAPI backend + React frontend, three roles
(Employee, IT Support Agent, Administrator), JWT-based authentication,
Argon2id password hashing, role-based access control (RBAC), audit
logging, security event monitoring, and rate limiting.

**Methodology:** [STRIDE](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats#stride-model) —
a threat classification framework covering six categories: **S**poofing,
**T**ampering, **R**epudiation, **I**nformation disclosure, **D**enial of
service, and **E**levation of privilege.

## Assets

- User credentials (hashed passwords, JWT session tokens)
- Ticket data (may contain sensitive employee/IT information)
- User roles and permissions
- Audit and security event logs
- The application and database availability

## Actors / Trust Boundaries

| Actor | Trust level | Notes |
|---|---|---|
| Unauthenticated visitor | Untrusted | Can reach login/register endpoints only |
| Employee | Authenticated, low privilege | Can create and view only their own tickets |
| IT Support Agent | Authenticated, elevated privilege | Can view/manage tickets assigned or escalated to them |
| Administrator | Authenticated, highest privilege | Full access: user management, all tickets, audit logs |

The trust boundary sits at the API layer: every request crossing from the
browser into the backend is treated as untrusted until the JWT is
validated and the role is checked against the requested resource.

## STRIDE Analysis

### 1. Spoofing (impersonating a user)

**Threat:** An attacker attempts to authenticate as another user, or forge
a session, to act with that user's identity and privileges.

**Mitigations:**
- Passwords are hashed with **Argon2id** (memory-hard, resistant to GPU
  cracking), never stored or logged in plaintext.
- Authentication issues a signed **JWT**; the backend verifies the
  signature and expiry on every request — tokens cannot be forged without
  the server's signing key.
- Login attempts are **rate-limited** (sliding window), so credential
  stuffing / brute-force password guessing is slowed significantly.
- Failed login attempts are recorded as **security events**, so repeated
  spoofing attempts are visible to an administrator.

**Residual risk:** The current build stores the JWT in memory rather than
`localStorage`, which reduces (but does not eliminate) exposure to
token-theft via XSS — the token is lost on page refresh, limiting the
attack window. A move to short-lived access tokens + refresh tokens with
httpOnly cookies would further reduce this risk and is a natural next
hardening step.

### 2. Tampering (modifying data without authorization)

**Threat:** A user modifies a ticket, role, or other data they shouldn't
be able to touch — either their own records in unauthorized ways, or
someone else's.

**Mitigations:**
- Every write endpoint re-validates the requester's role and ownership
  server-side (never trusting client-submitted role/user IDs).
- Pydantic schemas validate and constrain all incoming request bodies,
  rejecting unexpected fields or malformed data before it reaches the
  database layer.
- SQLAlchemy's ORM with parameterized queries is used throughout,
  eliminating SQL injection as a tampering vector.
- All state-changing actions are written to the **audit log** (who, what,
  when), so unauthorized tampering is detectable after the fact even if a
  control gap is later found.

**Residual risk:** Audit logs themselves are stored in the same database
as application data; a full compromise of the database would allow an
attacker to also tamper with the audit trail. Shipping logs to a separate,
append-only store (e.g. a managed logging service) would close this gap in
a production deployment.

### 3. Repudiation (denying an action was taken)

**Threat:** A user denies having performed an action (e.g. an agent claims
they never closed a ticket, or an admin claims they never changed a role).

**Mitigations:**
- The **audit log** records the acting user's ID, the action, the affected
  resource, and a timestamp for all significant state changes (ticket
  creation/update/status change, role changes, user creation).
- JWT-based authentication ties every request to a specific authenticated
  identity — there's no shared/anonymous write path.

**Residual risk:** Logs are currently only reviewable by Administrators
through the application itself; there's no tamper-evidence (e.g.
cryptographic chaining/hashing of log entries) to prove the log itself
wasn't altered. Acceptable for a demo project; a production system
handling compliance-sensitive data would want append-only, signed logs.

### 4. Information Disclosure (exposing data to unauthorized parties)

**Threat:** A user reads ticket data, user data, or system internals they
aren't authorized to see — including via guessing resource IDs (IDOR).

**Mitigations:**
- **Object-level authorization** on every ticket-read endpoint: a user
  requesting a ticket ID they don't own/can't access receives a generic
  **404 Not Found** rather than a 403 Forbidden. This intentionally avoids
  confirming whether a given ticket ID exists at all, preventing an
  attacker from enumerating valid IDs by observing 403-vs-404 responses —
  a classic Insecure Direct Object Reference (IDOR) mitigation.
- Each denied/IDOR-style access attempt is logged as a **security event**,
  so a pattern of ID-guessing is visible to an administrator even though
  the attacker sees nothing out of the ordinary.
- API documentation (`/docs`, `/redoc`, `/openapi.json`) is **disabled in
  production**, reducing the information available to an attacker
  reconnoitering the API surface.
- CORS is explicitly restricted to the known frontend origin(s) rather
  than `*`, preventing arbitrary third-party sites from making
  credentialed cross-origin requests against the API.
- The deployed frontend sends a **Content-Security-Policy** header
  restricting which origins scripts/styles/connections may come from,
  reducing the blast radius if a script-injection bug is ever introduced.

**Residual risk:** Error messages and stack traces are suppressed in
production mode, but this depends on `is_production` being correctly set
in the hosting environment — a misconfigured environment variable would
silently re-expose debug details. Worth a startup-time assertion/alert in
a future iteration.

### 5. Denial of Service (degrading or blocking availability)

**Threat:** An attacker floods the login endpoint, ticket-creation
endpoint, or the API generally, to exhaust resources or lock out
legitimate users.

**Mitigations:**
- **Rate limiting** is applied (in-memory sliding window) per
  client/endpoint, capping request volume on sensitive endpoints like
  login and registration.
- Password validation (`StrongPassword`) is enforced client- and
  server-side before expensive hashing operations run, reducing wasted
  Argon2id compute from malformed submissions.

**Residual risk:** The current rate limiter is in-memory and per-process —
on a multi-instance deployment it would not share state across instances,
and on Render's free tier the single instance also cold-starts/sleeps,
which is itself an availability limitation (though not a security one). A
production deployment would want a shared store (e.g. Redis) for rate
limiting across instances, plus a WAF or platform-level DDoS protection in
front of the API.

### 6. Elevation of Privilege (gaining more access than granted)

**Threat:** An Employee account gains IT Support Agent or Administrator
capabilities; or an Agent gains Admin capabilities.

**Mitigations:**
- **RBAC** is enforced at the API layer on every protected route — role is
  read from the validated JWT/database record, never trusted from client
  input, and checked against an explicit allow-list per endpoint.
- Role changes (e.g. promoting a user) are restricted to Administrator-only
  endpoints and are themselves audit-logged.
- The registration endpoint only ever creates **Employee**-role accounts;
  there is no client-controllable way to self-register as Agent or Admin.
  The one Administrator account creation path outside the UI (the
  environment-variable "bootstrap admin," used for the initial account on
  a fresh deployment) is idempotent and only runs against an empty state.

**Residual risk:** None identified beyond what's already covered under
Tampering (a full database compromise would allow direct role
manipulation, which is an infrastructure-security concern rather than an
application-logic gap).

## Summary table

| STRIDE category | Primary control(s) | Status |
|---|---|---|
| Spoofing | Argon2id, JWT, rate limiting | Implemented |
| Tampering | Server-side validation, ORM/parameterized queries, audit log | Implemented |
| Repudiation | Audit log tied to authenticated identity | Implemented (not tamper-evident) |
| Information Disclosure | Anti-IDOR (404s), security event logging, CORS, disabled prod docs, CSP | Implemented |
| Denial of Service | Rate limiting | Implemented (single-instance only) |
| Elevation of Privilege | Server-side RBAC, audit-logged role changes, restricted registration | Implemented |

## Out of scope / not yet addressed

- Multi-factor authentication (2FA/TOTP) — not yet implemented
- Centralized, tamper-evident logging (log shipping to an external store)
- Distributed rate limiting (Redis-backed) for multi-instance deployments
- Automated dependency vulnerability scanning in CI (Dependabot/Snyk)
- Dynamic application security testing (OWASP ZAP/Burp) against the live
  deployment — header-level testing has been completed (see
  [security assessment](security-assessment.md)); endpoint-level dynamic
  scanning is a planned next step.

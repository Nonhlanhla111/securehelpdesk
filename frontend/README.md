# SecureHelpDesk — Frontend (Phase 2)

A React (Vite) single-page app for the SecureHelpDesk API.

## Run it

```
npm install
npm run dev
```

Then open http://localhost:5173. Make sure the backend is running first (see
`../backend/README.md`) at http://localhost:8000 — if yours runs somewhere
else, copy `.env.example` to `.env` and change `VITE_API_URL`.

## What's here

- **Login / Register** — `src/pages/Login.jsx`, `Register.jsx`
- **Dashboard** — role-aware stats (`src/pages/Dashboard.jsx`)
- **Tickets** — list with search/filters, detail view with status workflow,
  assignment, comments (incl. staff-only internal notes), attachments, and
  history (`src/pages/TicketList.jsx`, `TicketDetail.jsx`, `NewTicket.jsx`)
- **Reports** — ticket statistics for staff (`src/pages/Reports.jsx`)
- **Admin** — user management, audit log, security events
  (`src/pages/AdminUsers.jsx`, `AdminLogs.jsx`)

## Notes

- The session token is kept in memory only (not `localStorage`), so
  refreshing the page logs you out. This avoids a stolen-token risk from XSS
  reading browser storage. If you'd rather trade that off for persistence
  across refreshes, the change is in `src/auth/AuthContext.jsx` and
  `src/api/client.js`.
- The UI only offers status transitions the backend will actually accept
  (see `STAFF_TRANSITIONS` / `EMPLOYEE_TRANSITIONS` in `TicketDetail.jsx`) —
  but the backend is still the real enforcement point, exactly as tested in
  the backend's pytest suite.

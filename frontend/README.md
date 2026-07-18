# RequestFlow — Frontend

React (Vite) frontend for RequestFlow, a small internal request/review
system. Talks to the FastAPI backend in `../backend`.

## Folder structure

```
src/
  api/            Thin fetch wrappers, one file per backend resource
    client.js       Shared fetch helper: attaches the bearer token, throws
                     on non-2xx with the backend's `detail` message
    auth.js          POST /users, POST /login, GET /users
    requests.js       GET/POST /requests, GET /requests/me
    reviews.js         GET/POST /reviews
  context/
    AuthContext.jsx  Holds the JWT + current user, exposes signIn/signOut
  components/
    Layout.jsx        Page shell (NavBar + content)
    NavBar.jsx         Role-aware navigation, user name/role, logout
    ProtectedRoute.jsx  Redirects to /login if unauthenticated; can also
                         gate a route to specific roles
    Badge.jsx          Status/priority/decision pill components
    Alert.jsx, Spinner.jsx  Small shared UI primitives
  pages/
    LoginPage.jsx, RegisterPage.jsx
    NewRequestPage.jsx, MyRequestsPage.jsx        (requester)
    ReviewQueuePage.jsx                            (reviewer/admin)
    AdminDashboardPage.jsx                         (admin)
    HomePage.jsx        Redirects "/" to the right view for the user's role
    NotFoundPage.jsx
  App.jsx            Route table
```

## Running locally

1. Backend must be running first (see `../backend`), reachable at
   `http://127.0.0.1:8000` by default.
2. `cp .env.example .env` (already done) — set `VITE_API_URL` if your
   backend runs elsewhere.
3. Install and run:

   ```
   npm install
   npm run dev
   ```

4. Open the printed URL (default `http://localhost:5173`).

## Auth / JWT handling

The backend returns a bare `access_token` from `POST /login` with no
refresh token or `/users/me` endpoint. Given that:

- **Storage**: the token is kept in `sessionStorage` (see
  `context/AuthContext.jsx`), scoped per-tab rather than shared across
  every tab for the site — useful for local dev/testing, since it lets
  different tabs stay independently signed into different accounts. The
  tradeoff is that the session doesn't survive closing the tab (no
  "stay logged in" across browser restarts), which is accepted here. This
  is still a `Web Storage` choice rather than a backend-issued httpOnly
  cookie, so the underlying XSS-exposure tradeoff also still applies (a
  cookie + `SameSite`/`HttpOnly` would be more robust against that, but
  requires backend support that doesn't exist here). Since this is a
  portfolio project against a trusted local backend, this keeps the auth
  flow simple and is a documented tradeoff, not an oversight.
- **Who is logged in**: the JWT's `sub` claim only carries the user id, not
  name/role, and there's no `/users/me` endpoint. On login, the frontend
  decodes the JWT payload client-side to get the id, then cross-references
  it against `GET /users` (which is public/unauthenticated on the backend)
  to resolve `name`/`role` for display and route-gating. This is purely a
  UI convenience — every actual permission check still happens
  server-side on each request, so a forged/stale client-side role can't
  grant real access.
- **Route protection**: `ProtectedRoute` redirects to `/login` if there's
  no token, or resolves no user (expired/invalid token → treated as
  logged out). It optionally takes `allowedRoles` to gate a route
  (unauthorized roles are redirected to `/`).

## Backend changes made alongside this frontend

Two small backend changes were needed for this to work, made in
`backend/main.py`:

1. **CORS**: added `CORSMiddleware` allowing `http://localhost:5173` /
   `http://127.0.0.1:5173`, since the backend had none and browsers block
   cross-origin requests by default.
2. **Reviewer access to `GET /requests`**: this endpoint was admin-only,
   but reviewers need to see the pool of requests to build a review queue.
   It's now `admin` or `reviewer` (still 403s for `requester`).

## Manual test checklist (against the real backend)

With the backend running (`uvicorn main:app --reload` from `backend/`,
Postgres up via `docker compose up -d`) and this dev server running:

1. **Register** — go to `/register`, create a `requester` account. Should
   log you straight in and land on "My requests" (empty state).
2. **Submit a request** — "New Request" → fill form → submit. Redirects
   to "My requests" showing it with `status: open`.
3. **Register a second account** with role `reviewer` (log out first).
   Logging in should land you on the review queue, showing the request
   from step 2.
4. **Review it**:
   - Try "Reject" with no comment — should show an inline error and NOT
     submit (matches the backend's 400 rule).
   - Add a comment and reject, or approve — request should disappear from
     the queue.
5. **Register a third account** with role `admin`. Log in → lands on
   Admin Dashboard — should show the request/review from above in the
   tables, plus correct by-status/by-type counts.
6. **Log out and back in** as the original requester — "My requests"
   should still show the request (status still `open`, since status
   updates are system-controlled, not driven by review decisions in this
   version).
7. **Bad login** — try a wrong password on `/login`, confirm the inline
   error message renders instead of a blank/broken page.

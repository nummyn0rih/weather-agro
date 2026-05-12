# Architecture Decision Records (ADR)

Lightweight log of non-obvious architectural choices. New entries go at the
top. Each ADR: context, decision, consequences.

---

## ADR-006 — OpenWeatherMap forecast aggregates by location-local TZ

**Status:** accepted — 2026-05-12
**Scope:** `backend/app/services/weather/openweathermap.py`,
`backend/app/db/models/location.py::Location.timezone`,
`backend/app/schemas/location.py`.

### Context

Task 6.1.1 (`TASKS.md` §6.1.1). The free-tier endpoint
`/data/2.5/forecast` returns 3-hour buckets stamped with a UTC `dt`. The
initial `fetch_forecast` implementation (6.1) binned those buckets by
`datetime.fromtimestamp(dt, tz=UTC).date()` — i.e. the UTC calendar day.

For locations east of the meridian this misfiles edge-of-day readings.
Example: Krasnodar is UTC+3 year-round; a forecast bucket at 23:00 UTC
on 2026-04-01 represents 02:00 local on 2026-04-02. A freezing reading
in that bucket would land in the 2026-04-01 row, while the operator
expects "frost on the morning of April 2". Once the alerts engine starts
consuming OWM forecasts (the explicit blocker named in the task), this
silently produces wrong alert dates.

### Decision

1. Add `Location.timezone: str` (nullable=False, `server_default='UTC'`,
   `String(64)` for an IANA name like `Europe/Moscow`). Migration `0013`.
2. `fetch_forecast(..., timezone: str = "UTC")` converts each bucket's
   UTC timestamp into the location TZ via `zoneinfo.ZoneInfo` *before*
   taking `.date()`, then bins by the resulting local date.
3. `fetch_current(..., timezone: str = "UTC")` does the same, for
   symmetry — a single snapshot at 23:00 UTC must file under the local
   day, not UTC, for the same reason as forecast buckets.
4. Unknown / malformed TZ names fall back to UTC with a warning log; we
   do not refuse the request.

The TZ travels as a parameter rather than being looked up inside the
client because the client must remain stateless (it does not own a DB
session). Schedulers and ingest code read `Location.timezone` and pass
it in.

### Consequences

- Stored data (`weather_forecast.time`) now reflects the
  operator-meaningful calendar day. Alert rules that join on `time` line
  up with the user's mental model.
- Existing rows (none in this codebase — OWM is not yet wired into the
  scheduler) are not migrated; the column has a default of `'UTC'` so
  pre-existing locations behave exactly as before until their TZ is set
  by an admin via `PUT /api/locations/{id}`.
- TZ is a required-but-defaulted field at the API surface; clients can
  omit it and get UTC. `LocationCreate.timezone` is validated against
  `zoneinfo` at request time to surface typos early.

### Alternatives considered

- **Resolve TZ via `timezonefinder` from (lat, lon).** Rejected for now
  — adds a 50 MB+ data dep for a single lookup, and TZ rarely changes
  per location. The column-only approach keeps things lean; a follow-up
  task may add auto-resolve on `POST /api/locations` if manual entry
  proves painful.
- **Always use UTC; let the alert engine shift.** Rejected — pushes the
  TZ concern into every downstream consumer (alerts, charts, exports),
  multiplying the surface area. Fix once, at the ingest boundary.
- **Use `Location.region` to infer TZ.** Rejected — `region` is a free
  string, not an IANA name; the two concepts should not be conflated.

---

## ADR-005 — Invite URL contract is path-form `/accept-invite/{token}`

**Status:** accepted — 2026-05-12
**Scope:** `backend/app/services/invites.py::build_invite_url`,
`frontend/src/pages/AcceptInvitePage.tsx`,
`frontend/src/components/admin/CreateInviteDialog.tsx`.

### Context

Task 6.3.0.1 (`TASKS.md` §6.3.0.1) added the invite system. Stage 2 of the
frontend (`6.3.0-FE.2`) registered the accept-invite page under the path
route `/accept-invite/:token`, while the backend `build_invite_url`
initially returned the query-form `${FRONTEND_URL}/accept-invite?token=...`.
The discrepancy was masked because the admin UI assembled the invite link
client-side from `token` and ignored the server-supplied `invite_url`.

As soon as out-of-band delivery (email, Telegram) ships in 6.4, the server
will start sending links that the SPA cannot parse — the route would 404.

### Decision

`build_invite_url` returns the path-form
`${FRONTEND_URL}/accept-invite/{token}`. The frontend route
`/accept-invite/:token` is the canonical contract for invite links.

The admin UI must use `response.invite_url` verbatim from
`POST /api/admin/invites` instead of self-assembling the URL.

### Consequences

- One URL shape end-to-end. Email/Telegram delivery in 6.4 can send the
  server-built link without further work.
- Existing path route in `AcceptInvitePage` is the source of truth; future
  link generators (server-side or template-side) must call
  `build_invite_url` rather than concatenating strings.
- The query-form is not silently accepted as a fallback — if a legacy
  link surfaces, the SPA 404s on `/accept-invite` (no `:token`), which
  surfaces the bug rather than hiding it.

### Alternatives considered

- **Keep query-form, change the FE route.** Rejected: the path-form is
  already shipped in the FE and used by the admin UI; reverting it would
  invalidate any links already created.
- **Accept both shapes.** Rejected: two contracts is worse than one. We
  control both ends, so a single shape is achievable.

---

## ADR-004 — Admin CRUD for dictionaries lives under `/api/<entity>`, and PUT is partial

**Status:** accepted — 2026-05-11
**Scope:** `backend/app/api/crops.py` and future dictionary CRUDs (e.g. crop
types, regions). Does **not** apply to resources with a dedicated admin
namespace (`/api/admin/users`, `/api/admin/invites` from 6.3.0 stay where
they are).

### Context

Task 6.3.2 (`TASKS.md` §6.3.2) added admin CRUD over the `crops` dictionary.
Two design questions surfaced during implementation:

1. **Where do admin write-methods for a dictionary live?** Option A — a
   separate `/api/admin/<entity>` router parallel to the public
   `/api/<entity>`. Option B — keep one router under `/api/<entity>` and
   attach `require_admin` to the write methods only.
2. **Are PUT semantics full-replace or partial?** The task spec uses `PUT`
   for update; the implementation does partial via
   `model_dump(exclude_unset=True)` (effectively PATCH-on-PUT). This pattern
   is repeated elsewhere in the project (`admin_users.update_user`, etc.)
   and risks being "fixed" by a later task that takes REST orthodoxy at
   face value.

### Decision

**Decision A — admin write-methods sit on the public router.**

For short dictionaries (Crop and similar lookups), admin POST/PUT/DELETE
live under `/api/<entity>` next to the public GET. Authorization is
attached per-method via `Depends(require_admin)`. No separate
`/api/admin/<entity>` is created for dictionaries. Admin reuses the
existing GET — no separate admin-listing endpoint.

**Decision B — `PUT /api/<entity>/{id}` means partial update.**

In this project, `PUT` updates only the fields supplied in the request body
(`model_dump(exclude_unset=True)`). Full-replace is not offered as a
separate method because there is no caller that needs it. Future tasks
must not "correct" this to strict-REST semantics — it is intentional.

### Consequences

- One router per dictionary, one Swagger tag, no duplication. Admin gets
  list/detail "for free" through the public GET.
- The auth gate is scattered across methods, so a new write method can
  ship without `require_admin` by oversight. This is closed by a
  mandatory `test_<entity>_forbidden_for_regular_user` test on **every**
  write endpoint (already enforced for crops:
  `test_create_crop_forbidden_for_regular_user`,
  `test_put_crop_forbidden_for_regular_user`,
  `test_delete_crop_forbidden_for_regular_user`).
- Diverges from strict REST (`PUT` should replace, `PATCH` should patch).
  Acceptable trade-off: one method instead of two, clients send only what
  they want to change, no `null` ambiguity. Documented here so future
  tasks don't try to split into PUT+PATCH.
- Resources with their own admin namespace (users, invites) are not
  retro-fitted; this ADR is forward-looking guidance for dictionaries.

### Alternatives considered

- **Separate `/api/admin/crops` router with its own GET/POST/PUT/DELETE.**
  Rejected: duplicates the public GET, splits the Swagger tag, and adds a
  second place to keep in sync when the schema changes.
- **Strict REST: `PUT` = full replace, add `PATCH` for partial.**
  Rejected: no caller needs full-replace today; two methods means two test
  matrices and a foot-gun where omitting a field silently wipes it.

---

## ADR-003 — Password change does not invalidate existing JWTs (MVP)

**Status:** superseded by 6.3.0-DEBT.2 — 2026-05-12
**Supersedes note:** the limitation described below was closed by
`6.3.0-DEBT.2`. Migration `0012_user_tokens_invalidated_at.py` adds the
`users.tokens_invalidated_at` column; `change_password` and
`users_service.update_user` (on `is_active=False`) stamp it with
`datetime.now(timezone.utc)`; `app/api/deps.py::_token_invalidated` rejects
tokens whose `iat` falls in or before the invalidation second
(`int(iat) <= int(tokens_invalidated_at.timestamp())`); `POST /auth/refresh`
now performs the same user-state + iat check so refresh tokens issued
before deactivation cannot mint new access tokens. See
`backend/tests/test_jwt_invalidation.py` for the three covered scenarios.
The historical context below is kept for reference.

**Scope:** `backend/app/api/auth.py` (`POST /api/auth/change-password`),
`backend/app/core/security.py`, `backend/app/api/deps.py`

### Context

Task 6.3.1 (`TASKS.md` §6.3.1) introduces `POST /api/auth/change-password`.
Refresh and access tokens are stateless JWTs signed with `SECRET_KEY` via
`python-jose` (`backend/app/core/security.py`). There is no server-side token
store, no revocation list, and no per-user "tokens issued before X" marker
on the `users` table.

A natural expectation around password change is that previously issued
tokens stop working — particularly the long-lived refresh token (7 days).
Without server-side state that is not enforceable today.

### Decision

For MVP, `POST /api/auth/change-password` updates only `users.password_hash`.
Existing access and refresh tokens keep working until their natural `exp`:

- access — `ACCESS_TOKEN_EXPIRE_MINUTES` (15 min by default).
- refresh — `REFRESH_TOKEN_EXPIRE_DAYS` (7 days by default).

We accept this as a known limitation, document it in the endpoint's
docstring/OpenAPI description, and track the full fix as
`6.3.0-DEBT.2` (`TASKS.md` §6.3.0-DEBT.2): add
`User.tokens_invalidated_at` (or `password_changed_at`) and reject any
token whose `iat < tokens_invalidated_at` inside `get_current_user`. Same
column also covers admin deactivation (a deactivated user's still-valid
access token is rejected by `is_active` check, but a refresh issued
before deactivation could still mint new access tokens until the deactivation
is materialized — `6.3.0-DEBT.2` closes that path too).

### Consequences

- A user whose password was compromised cannot self-rescue immediately:
  attacker keeps the refresh token until it expires (≤ 7 days). Mitigation
  options today: rotate `SECRET_KEY` (invalidates *all* sessions globally —
  blunt instrument) or wait for `6.3.0-DEBT.2`.
- Admin deactivation through `/api/admin/users/{id}` partially helps:
  `get_current_user` rejects inactive users on the access path, so the
  attacker's existing access token stops being honored on the next call.
  The refresh token remains technically valid; on `/auth/refresh`, no
  `is_active` check runs (refresh issues a new access token without DB
  lookup), so a new access token can be minted — but it will be rejected
  by `get_current_user` as inactive on the next request. Net effect:
  attacker burns one access token per refresh until refresh expires.
  `6.3.0-DEBT.2` removes this loophole entirely.
- The change-password endpoint description and its docstring explicitly
  state "existing JWT tokens remain valid until natural expiry" so callers
  (frontend, future API consumers) cannot assume otherwise.
- No schema migration is required for 6.3.1. The migration that adds
  `tokens_invalidated_at` is bundled with `6.3.0-DEBT.2`.

### Alternatives considered

- **Add `tokens_invalidated_at` now, in 6.3.1.** Rejected: out of scope
  for 6.3.1 (the task explicitly defers it). Mixing schema migration into
  a logic-only ticket would also violate the layered task model in
  `CLAUDE.md`.
- **Rotate `SECRET_KEY` on every password change.** Rejected: would invalidate
  every other user's session as a side effect — unacceptable once the system
  is multi-user.
- **Server-side refresh token store (DB or Redis).** Deferred. More invasive
  than the `tokens_invalidated_at` approach and unnecessary for MVP scale
  (one to a handful of users).

---

## ADR-002 — Settings API: grouped endpoints, env→DB precedence, masked secrets

**Status:** accepted — 2026-05-03
**Scope:** `backend/app/api/settings.py` (to be created in task 6.3), `app/services/settings/`, `app/core/config.py`

### Context

Task 6.3 (`PRD.md` §7.9, `TASKS.md` §6.3) requires a Settings API covering four
heterogeneous concerns:

1. **Data sources** — priority order of weather providers, average-mode flag.
2. **API keys** — `OPENWEATHERMAP_API_KEY`, `YANDEX_DISK_TOKEN` (or webdav
   user/password).
3. **Telegram** — `BOT_TOKEN`. (`chat_id` lives on `User`, managed elsewhere.)
4. **Backup** — Yandex.Disk path, retention (30 daily / 12 monthly).

The original DoD says `GET /api/settings` + `PUT /api/settings` over a single
key/value-shaped `settings` table (`PRD.md` §6). That under-specifies six
design questions which materially affect FE-F (6.4) and security:

- Q1 — One endpoint vs grouped endpoints?
- Q2 — Source of truth for secrets: `.env` (per `PRD.md` §11) or DB (per 6.3 DoD,
  Fernet-encrypted)?
- Q3 — How are secrets masked on `GET`? How does `PUT` distinguish "keep" vs
  "replace"?
- Q4 — Telegram settings — what fields exactly?
- Q5 — Backup settings — what fields exactly?
- Q6 — Authorization: any authenticated user, or admin-only? Audit trail?

### Decision

**Q1 — Grouped endpoints, not a monolith.**

```
GET /api/settings/sources       PUT /api/settings/sources
GET /api/settings/api-keys      PUT /api/settings/api-keys
GET /api/settings/telegram      PUT /api/settings/telegram
GET /api/settings/backup        PUT /api/settings/backup
```

Each group is a separate Pydantic schema. Storage is still one row per group
in the existing `settings(key, value JSONB)` table (`key` ∈
`{sources, api_keys, telegram, backup}`).

**Q2 — env→DB precedence; DB overrides env when present.**

- `.env` remains the bootstrap source: a fresh deployment reads
  `OPENWEATHERMAP_API_KEY` etc. from env so the system works before anyone
  touches the UI.
- DB row, when set, takes precedence at read time.
- `app/services/settings/resolver.py` exposes
  `get_secret(name) -> str | None` that returns DB value if present (and
  decrypted), else `os.environ` value, else `None`.
- This resolves the apparent conflict between `PRD.md` §11 ("API-ключи и
  секреты — в `.env`") and 6.3 DoD ("шифрование чувствительных полей в БД"):
  env is the floor, DB is the override.

**Q3 — Mask `last4`, sentinel-based PUT.**

- `GET` returns secrets as `"***" + value[-4:]` (e.g. `"***ab12"`); empty/
  missing → `null`.
- `PUT` semantics:
  - Field absent or `null` → no change.
  - Field equals current masked value (starts with `***`) → no change
    (idempotent re-submit of GET payload).
  - Any other string → replace; encrypt with Fernet (`SECRET_KEY`-derived
    key) before storing.
- Empty string `""` → explicit clear (delete from DB; resolver falls back
  to env).

**Q4 — Telegram settings = `{bot_token: str}` only.**

- `chat_id` is per-`User` (`User.telegram_chat_id`) and managed via existing
  `/api/auth/telegram/*` endpoints — it is not part of `/api/settings`.
- `bot_token` is a secret; same masking as Q3.

**Q5 — Backup settings.**

```python
{
  "yandex_disk_token": str,          # secret, masked
  "yandex_disk_path": str,           # plain, e.g. "/weather-agro-backups"
  "retention_daily": int = 30,
  "retention_monthly": int = 12,
}
```

WebDAV user/password is an alternative auth scheme for Yandex.Disk; we
standardize on OAuth token to avoid storing the user's account password.

**Q6 — Admin-only + audit log on PUT.**

- All settings endpoints require `is_admin=True` on the authenticated user.
  `User.is_admin` is added in task 6.3.0 (see `TASKS.md`); the seeded admin
  is `is_admin=True`.
- Every `PUT` writes a structured log entry (`structlog`, level `info`):
  `{event: "settings.updated", group, user_id, changed_keys: [...], at}`.
  Secret values are **never** logged — only field names.
- For MVP we log to stdout (captured by Docker). A dedicated
  `settings_audit` table can be added later if compliance requires it; the
  log shape is forward-compatible.

### Consequences

- FE (task 6.4) calls four endpoints, one per tab. No need to merge/split
  client-side.
- Adding a new settings group = new schema + new key + new endpoint pair;
  no schema migration.
- Operators can rotate a secret by editing `.env` and restarting (env path)
  **or** through the UI (DB path). The two never disagree silently because
  the resolver always prefers DB-set values.
- Masked GET payloads are safe to log on the client and safe to round-trip
  back to PUT without leaking secrets.
- `is_admin` is a forward-compat field. In MVP there is one user
  (`PRD.md` §11), so the gate is functionally equivalent to "authenticated"
  today. When multi-user lands, no API redesign is needed.
- Fernet key derivation uses the existing `SECRET_KEY` (HKDF). Rotation
  would require re-encrypting DB rows — out of scope for MVP, documented
  as a known limitation.

### Alternatives considered

- **Single `GET/PUT /api/settings` returning all groups.** Rejected: makes
  partial updates clumsy, forces FE to re-send unrelated groups, and bloats
  the response payload (4 secrets vs 1).
- **Secrets only in `.env`, DB stores only non-secret config.** Rejected:
  blocks the UX requirement that the user can rotate the OpenWeatherMap key
  from the Settings page (`PRD.md` §7.9) without SSH access.
- **DB-only secrets, ignore `.env`.** Rejected: bootstrapping a fresh
  deployment then requires a manual UI step before anything works; also
  conflicts with §11.
- **Mask as `"***"` (no last-4).** Rejected: operator has no way to
  visually confirm "the right key is loaded" without revealing it.
- **`PATCH` with explicit field-presence flags.** Rejected: sentinel approach
  (mask round-trip = no-op, empty string = clear) is simpler for the FE
  form layer and behaves intuitively.
- **Separate `roles` table for authorization.** Rejected for MVP — single
  user, single role. `is_admin` boolean is enough until a real RBAC need
  surfaces.

### Amendment — 2026-05-12 (implementation of task 6.3)

- **Backup group keeps WebDAV `login` + `app_password`** instead of the
  OAuth-token shape from Q5. Rationale: env parity (`.env.example` already
  defines `YANDEX_DISK_LOGIN` + `YANDEX_DISK_APP_PASSWORD`); no Yandex.Disk
  client code consumes these yet, so swapping schemes later is cheap.
  Revisit when the backup uploader (task 9.x) lands or if Yandex deprecates
  app passwords. The `login` field is stored in plaintext JSONB (not a
  credential by itself); only `yandex_disk_app_password` is Fernet-encrypted.
- **Sources group shape** materialised as `{priority: list[Source],
  enabled: dict[Source, bool], average_mode: bool}`. The `enabled` map
  complements `priority` to let the FE distinguish "configured but paused"
  from "removed from priority list" without reordering.
- **Resolver is async with its own short-lived session** when no session is
  passed in — clients (`openweathermap`, `telegram_bot`, scheduler) refactor
  to `await resolver.get_secret(...)`. Sync-cache alternative rejected: it
  would require an explicit invalidation hook on every PUT and add a
  process-state surface that doesn't survive multi-worker deployment.
- **Env fallback reads `get_settings().<ATTR>`**, not `os.environ` directly
  — keeps a single source-of-truth for env coercion (Pydantic-settings)
  and makes test monkeypatching uniform with the rest of the codebase.

---

## ADR-001 — API URL prefix is `/api`, not `/api/v1`

**Status:** accepted — 2026-04-30
**Scope:** all FastAPI routes in `backend/app/api/*`

### Context

The MVP exposes a single internal client (the React frontend in this repo) and
the Telegram bot, both deployed as part of the same Docker Compose stack. There
are no external API consumers, no public SDK, and no contract obligations to
third parties. The product spec (`PRD.md` §12) describes endpoints under
`/api/...` without a version segment.

Adding a `/v1/` segment up front would impose a perpetual maintenance cost
(two paths during every breaking change, parallel routers, doubled tests)
without a corresponding benefit at this stage of the project.

### Decision

All HTTP routes are mounted under `/api/...`. We do **not** introduce a
`/v1/` (or any other version) prefix until a real need appears.

### Consequences

- Frontend and bot client code call `/api/<resource>` directly.
- Swagger / OpenAPI is served at `/api/docs`, schema at `/api/openapi.json`.
- When a breaking API change becomes necessary, the migration path is one of:
  1. **Nginx rewrite** — keep the application on `/api/...` and let the edge
     map legacy paths during a transition window. Concrete example in
     `nginx/nginx.conf`:
     ```nginx
     location /api/v1/ { rewrite ^/api/v1/(.*)$ /api/$1 break; proxy_pass http://backend:8000; }
     location /api/    {                                       proxy_pass http://backend:8000; }
     ```
  2. **New prefix** — mount the new router tree under `/api/v2/...` (or a
     name reflecting the breaking change) and run both prefixes in parallel
     until the old client is retired. Concrete example in
     `backend/app/main.py`:
     ```python
     app.include_router(legacy_alerts_router, prefix="/api")     # frozen, deprecated
     app.include_router(alerts_router_v2,    prefix="/api/v2")   # new shape
     ```
- The cost of either migration is bounded because the only consumers are
  in-tree.
- Developers must not introduce a `/v1/` segment retroactively to "future-
  proof" individual endpoints — that would create the inconsistency this ADR
  exists to prevent.

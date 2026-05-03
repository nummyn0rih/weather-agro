# Architecture Decision Records (ADR)

Lightweight log of non-obvious architectural choices. New entries go at the
top. Each ADR: context, decision, consequences.

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

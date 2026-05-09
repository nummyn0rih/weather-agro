# Endpoint role matrix

Snapshot generated for task **6.3.0.3** (защита существующих admin-эндпоинтов).
Authoritative classification of every backend route by required role.

Roles:

- **public** — no auth dependency.
- **user+admin** — `Depends(get_current_user)`. Any authenticated active user.
- **admin** — `Depends(require_admin)`. `is_admin=True` only; non-admin → 403,
  unauthenticated → 401.

## auth (`app/api/auth.py`)

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/api/auth/login` | public | rate-limited |
| POST | `/api/auth/refresh` | public | refresh JWT |
| POST | `/api/auth/logout` | public | stateless, frontend drops tokens |
| GET | `/api/auth/me` | user+admin | own profile |
| GET | `/api/auth/invites/{token}` | public | accept-invite landing |
| POST | `/api/auth/invites/{token}/accept` | public | rate-limited; auto-login |
| POST | `/api/auth/telegram/bind-code` | user+admin | per-user bind |
| GET | `/api/auth/telegram/status` | user+admin | per-user bind |
| DELETE | `/api/auth/telegram/bind` | user+admin | per-user unbind |

## health (`app/api/health.py`)

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/health` | public | liveness probe |

## locations (`app/api/locations.py`)

Locations are shared resources (no per-user ownership). Reads are open to any
authenticated user; mutations affect every dashboard, every alert rule, and
trigger a 10-year backfill — admin only.

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/locations` | user+admin | filter by region/type |
| GET | `/api/locations/{id}` | user+admin | |
| GET | `/api/locations/{id}/import-status` | user+admin | backfill progress |
| POST | `/api/locations` | **admin** | kicks off 10y backfill |
| PUT | `/api/locations/{id}` | **admin** | shared resource |
| DELETE | `/api/locations/{id}` | **admin** | shared resource |

## crops (`app/api/crops.py`)

Reference dictionary. Reads open to all authenticated users. Write endpoints
do not exist yet (added in task **6.3.2** as admin-only).

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/crops` | user+admin | sorted by name |

## weather (`app/api/weather.py`)

All read endpoints — open to any authenticated user.

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/weather/daily` | user+admin | universal query |
| GET | `/api/weather/heatmap` | user+admin | |
| GET | `/api/weather/cumulative` | user+admin | |
| GET | `/api/weather/stats` | user+admin | |
| GET | `/api/weather/export` | user+admin | CSV/XLSX |

## analytics (`app/api/analytics.py`)

Read endpoints — open to any authenticated user. `?refresh=true` on
`/normals` rebuilds the cached climate normals row; this is a per-(location,
parameter) cache refresh, not a system-wide cron operation, so it remains
user+admin. If admin-only refresh becomes a requirement, split into a separate
`POST /api/analytics/normals/refresh` admin-only route.

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/analytics/normals` | user+admin | `refresh=true` rewrites cache |
| GET | `/api/analytics/anomalies` | user+admin | |
| GET | `/api/analytics/correlations` | user+admin | |

## alerts — rules (`app/api/alerts.py`)

Alert rules are system-wide (a rule fires for any matching location). Reads
are open to all users; mutations are admin-only.

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/alerts/rules` | user+admin | |
| GET | `/api/alerts/rules/{id}` | user+admin | |
| POST | `/api/alerts/rules` | **admin** | system-wide rule |
| PUT | `/api/alerts/rules/{id}` | **admin** | system-wide rule |
| DELETE | `/api/alerts/rules/{id}` | **admin** | system-wide rule |

## alerts — history (`app/api/alert_history.py`)

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/alerts/history` | user+admin | filterable, paginated |

## events (`app/api/events.py`)

Field-events are shared journal entries (no per-user ownership in current
schema). All authenticated users may CRUD; row-level scoping is out of scope
for 6.3.0.3 (would land as 6.3.0.4 if business rules require it).

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/events` | user+admin | filters: location/type/crop/dates |
| POST | `/api/events` | user+admin | |
| GET | `/api/events/{id}` | user+admin | weather attached |
| PUT | `/api/events/{id}` | user+admin | |
| DELETE | `/api/events/{id}` | user+admin | also clears photo dir |
| POST | `/api/events/{id}/photos` | user+admin | multipart, MAX_PHOTOS_PER_EVENT |
| DELETE | `/api/events/{id}/photos/{filename}` | user+admin | |

## reports (`app/api/reports.py`)

Reports describe shared locations; all authenticated users can generate,
download, list, and delete them. Same row-level note as events.

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/api/reports/generate` | user+admin | async PDF job |
| GET | `/api/reports` | user+admin | |
| GET | `/api/reports/{file_id}` | user+admin | metadata |
| GET | `/api/reports/{file_id}/download` | user+admin | streams PDF |
| DELETE | `/api/reports/{file_id}` | user+admin | DB row + file |

## admin — invites (`app/api/admin_invites.py`)

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/api/admin/invites` | **admin** | create 7-day token |
| GET | `/api/admin/invites` | **admin** | with computed status |
| DELETE | `/api/admin/invites/{id}` | **admin** | revoke pending |

## admin — users (`app/api/admin_users.py`)

| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/admin/users` | **admin** | |
| GET | `/api/admin/users/{id}` | **admin** | |
| PATCH | `/api/admin/users/{id}` | **admin** | role/active flags, self-lockout guard |
| POST | `/api/admin/users/{id}/reset-password` | **admin** | bcrypt rehash |

## Future endpoints not yet implemented

These slots are reserved for upcoming tasks; classification recorded so the
implementation lands with the right dependency on day one:

| Group | Future path | Role |
|---|---|---|
| Settings (6.3) | `/api/settings/sources` GET/PUT | **admin** |
| Settings (6.3) | `/api/settings/api-keys` GET/PUT | **admin** |
| Settings (6.3) | `/api/settings/telegram` GET/PUT | **admin** |
| Settings (6.3) | `/api/settings/backup` GET/PUT | **admin** |
| Backups (6.2) | `/api/backup/run` POST | **admin** |
| Backups (6.2) | `/api/backup/list` GET | **admin** |
| Crops (6.3.2) | `/api/crops` POST/PUT/DELETE | **admin** |
| Auth (6.3.1) | `/api/auth/change-password` POST | user+admin (own password) |

## Notes

- Row-level access control ("user sees own records only") is **out of scope**
  for 6.3.0.3. Only role-level (admin vs user+admin) is enforced here.
- Static `/uploads/*` is served by FastAPI's `StaticFiles` mount (see
  `app/main.py`) and is not auth-gated. Uploaded files use UUID names so
  enumeration is impractical, but this is a known limitation for the MVP —
  if uploads contain sensitive data, gate behind nginx + signed URLs in
  prod.

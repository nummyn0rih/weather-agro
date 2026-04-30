# Architecture Decision Records (ADR)

Lightweight log of non-obvious architectural choices. New entries go at the
top. Each ADR: context, decision, consequences.

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

# Deploy notes

Per-task production deploy steps. Append entries chronologically; each one
documents what an operator must do beyond `git pull && alembic upgrade head`.

## 5.3 deploy note

Backend image must be rebuilt after this commit:
`docker compose build backend && docker compose up -d backend`
New apt deps: libpango/libcairo/libgdk-pixbuf for WeasyPrint.

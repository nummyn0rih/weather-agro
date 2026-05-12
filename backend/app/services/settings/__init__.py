"""Settings services package (task 6.3).

Public API:
  * :func:`store.load_group` / :func:`store.save_group` — JSONB read/write per group.
  * :func:`resolver.get_secret` — env→DB resolver for runtime secrets.
"""

from app.services.settings import resolver, store

__all__ = ["resolver", "store"]

from __future__ import annotations

from app.services.project_tracking.catalog import ProjectScope


def filter_scopes(scopes: list[ProjectScope], ignored_keys: set[str]) -> list[ProjectScope]:
    if not ignored_keys:
        return scopes
    return [item for item in scopes if item.key not in ignored_keys]

from __future__ import annotations

from urllib.parse import quote


def resolve_work_item_url(
    *,
    base_url: str | None,
    organization: str | None,
    team_project: str | None,
    task_id: str | int | None,
) -> str | None:
    base = (base_url or "").strip().rstrip("/")
    org = (organization or "").strip()
    project = (team_project or "").strip().replace("\\", "/")
    if not base or not org or not project or task_id is None:
        return None
    try:
        work_item_id = int(str(task_id).strip())
    except (TypeError, ValueError):
        return None
    if work_item_id <= 0:
        return None
    return f"{base}/{quote(org)}/{quote(project)}/_workitems/edit/{work_item_id}"

from __future__ import annotations

from app.models import Collaborator
from app.services.csv_parser import normalize_name


def find_collaborator_by_assignee(
    collaborators: list[Collaborator],
    assignee_name: str,
) -> Collaborator | None:
    key = normalize_name(assignee_name)
    if not key:
        return None
    for item in collaborators:
        if normalize_name(item.azure_name) == key:
            return item
    for item in collaborators:
        if normalize_name(item.name) == key:
            return item
    return None

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.services.project_tracking.dates import parse_azure_datetime
from app.services.project_tracking.states import is_completed_state, normalize_state


@dataclass
class WorkItemSnapshot:
    revision: int
    changed_at: datetime | None
    state: str | None
    iteration_path: str | None
    area_path: str | None
    assignee: str | None = None


def _field(fields: dict, name: str):
    return fields.get(name)


def _assignee_display(raw) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return str(raw.get("displayName") or raw.get("uniqueName") or "").strip() or None
    text = str(raw).strip()
    return text or None


def build_snapshots(revisions: list[dict]) -> list[WorkItemSnapshot]:
    ordered = sorted(revisions, key=lambda item: int(item.get("rev") or 0))
    snapshots: list[WorkItemSnapshot] = []
    for item in ordered:
        fields = item.get("fields") or {}
        snapshots.append(
            WorkItemSnapshot(
                revision=int(item.get("rev") or 0),
                changed_at=parse_azure_datetime(_field(fields, "System.ChangedDate")),
                state=str(_field(fields, "System.State") or "").strip() or None,
                iteration_path=str(_field(fields, "System.IterationPath") or "").strip() or None,
                area_path=str(_field(fields, "System.AreaPath") or "").strip() or None,
                assignee=_assignee_display(_field(fields, "System.AssignedTo")),
            )
        )
    return snapshots


def snapshot_at(snapshots: list[WorkItemSnapshot], moment: datetime) -> WorkItemSnapshot | None:
    chosen: WorkItemSnapshot | None = None
    for snap in snapshots:
        if snap.changed_at is None or snap.changed_at <= moment:
            chosen = snap
        else:
            break
    return chosen


def iteration_matches(iteration_path: str | None, sprint_path: str) -> bool:
    if not iteration_path:
        return False
    if iteration_path == sprint_path:
        return True
    prefix = f"{sprint_path}\\"
    return iteration_path.startswith(prefix)


def state_changes(snapshots: list[WorkItemSnapshot]) -> list[tuple[WorkItemSnapshot, WorkItemSnapshot]]:
    changes: list[tuple[WorkItemSnapshot, WorkItemSnapshot]] = []
    prev: WorkItemSnapshot | None = None
    for snap in snapshots:
        if prev is None:
            prev = snap
            continue
        if normalize_state(prev.state) != normalize_state(snap.state):
            changes.append((prev, snap))
        prev = snap
    return changes


def completed_transition_in_range(
    snapshots: list[WorkItemSnapshot],
    start: datetime,
    end: datetime,
) -> WorkItemSnapshot | None:
    for before, after in state_changes(snapshots):
        if after.changed_at is None:
            continue
        if after.changed_at < start or after.changed_at > end:
            continue
        if is_completed_state(after.state):
            return after
    return None

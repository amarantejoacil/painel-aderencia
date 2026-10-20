from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.services.azure_devops import AzureDevOpsService
from app.services.project_tracking.azure_wit import (
    DatedIteration,
    fetch_revisions,
    fetch_work_items,
    wiql_story_ids,
)
from app.services.project_tracking.dates import (
    end_of_day_cuiaba,
    now_utc,
    parse_azure_calendar_date,
    parse_azure_datetime,
    sprint_status,
    start_of_day_cuiaba,
)
from app.services.project_tracking.revisions import (
    build_snapshots,
    completed_transition_in_range,
    iteration_matches,
    snapshot_at,
)
from app.services.project_tracking.states import is_completed_state, is_removed_state, normalize_state
from app.services.project_tracking.story_consolidation import SPRINT_IN_PROGRESS_STATES


@dataclass
class SprintMetrics:
    stories_total: int
    stories_created_in_sprint: int
    stories_completed_in_sprint: int
    stories_in_progress: int
    stories_pending: int
    stories_added_after_start: int
    stories_removed: int
    completion_percent: float | None
    completion_denominator: int
    historical_limitations: list[str]


@dataclass
class StorySprintView:
    work_item_id: int
    title: str
    state_at_start: str | None
    state_at_cut: str | None
    state_current: str | None
    created_at: datetime | None
    completed_at: datetime | None
    area_path: str | None
    iteration_current: str | None
    assignee: str | None
    impediment: str | None
    in_sprint_at_cut: bool
    created_in_sprint: bool
    completed_in_sprint: bool
    added_after_start: bool
    azure_url: str


def _created_datetime(fields: dict) -> datetime | None:
    return parse_azure_datetime(fields.get("System.CreatedDate"))


def _assignee(fields: dict) -> str | None:
    raw = fields.get("System.AssignedTo")
    if isinstance(raw, dict):
        return str(raw.get("displayName") or "").strip() or None
    return str(raw).strip() if raw else None


def analyze_sprint_stories(
    service: AzureDevOpsService,
    sprint: DatedIteration,
    *,
    area_path: str | None = None,
    include_story_details: bool = False,
) -> tuple[SprintMetrics, list[StorySprintView]]:
    start_d = parse_azure_calendar_date(sprint.start)
    finish_d = parse_azure_calendar_date(sprint.finish)
    if start_d is None or finish_d is None:
        empty = SprintMetrics(
            stories_total=0,
            stories_created_in_sprint=0,
            stories_completed_in_sprint=0,
            stories_in_progress=0,
            stories_pending=0,
            stories_added_after_start=0,
            stories_removed=0,
            completion_percent=None,
            completion_denominator=0,
            historical_limitations=["Sprint sem datas de início e término no Azure."],
        )
        return empty, []

    sprint_start = start_of_day_cuiaba(start_d)
    sprint_end = end_of_day_cuiaba(finish_d)
    cut_moment = min(sprint_end, now_utc())

    story_ids = wiql_story_ids(service, sprint.team_project, iteration_path=sprint.path)
    if area_path:
        area_ids = set(wiql_story_ids(service, sprint.team_project, area_path=area_path))
        story_ids = [item for item in story_ids if item in area_ids]

    limitations: list[str] = []
    if len(story_ids) > 150:
        limitations.append(
            f"Métricas calculadas sobre {len(story_ids)} histórias; sprints muito grandes podem demorar."
        )

    items = fetch_work_items(service, story_ids) if story_ids else []
    item_by_id = {int(item["id"]): item for item in items if item.get("id") is not None}

    stories: list[StorySprintView] = []
    denominator = 0
    completed_count = 0
    created_in = 0
    completed_in = 0
    in_progress = 0
    pending = 0
    added_after = 0
    removed = 0

    for work_item_id in story_ids:
        item = item_by_id.get(work_item_id)
        if not item:
            limitations.append(f"História {work_item_id} não retornada pelo Azure.")
            continue
        fields = item.get("fields") or {}
        revisions_raw = fetch_revisions(service, work_item_id)
        snapshots = build_snapshots(revisions_raw)
        if not snapshots:
            limitations.append(f"História {work_item_id} sem revisões disponíveis.")

        at_start = snapshot_at(snapshots, sprint_start)
        at_cut = snapshot_at(snapshots, cut_moment)
        state_start = at_start.state if at_start else None
        state_cut = at_cut.state if at_cut else fields.get("System.State")
        iteration_cut = at_cut.iteration_path if at_cut else fields.get("System.IterationPath")

        in_sprint_at_cut = iteration_matches(
            str(iteration_cut) if iteration_cut else None,
            sprint.path,
        )
        created_dt = _created_datetime(fields)
        created_in_sprint = bool(
            created_dt and sprint_start <= created_dt <= sprint_end
        )
        completed_snap = completed_transition_in_range(snapshots, sprint_start, sprint_end)
        completed_in_sprint = completed_snap is not None

        in_sprint_at_start = iteration_matches(
            at_start.iteration_path if at_start else None,
            sprint.path,
        )
        added_after_start = bool(
            in_sprint_at_cut
            and not in_sprint_at_start
            and not created_in_sprint
        )

        if is_removed_state(str(state_cut)):
            removed += 1
            if include_story_details:
                stories.append(
                    _story_view(
                        service,
                        sprint,
                        work_item_id,
                        fields,
                        state_start,
                        state_cut,
                        in_sprint_at_cut,
                        created_in_sprint,
                        completed_in_sprint,
                        added_after_start,
                        created_dt,
                        completed_snap.changed_at if completed_snap else None,
                    )
                )
            continue

        counts_for_sprint = in_sprint_at_cut or completed_in_sprint or created_in_sprint
        if not counts_for_sprint:
            continue

        denominator += 1
        if created_in_sprint:
            created_in += 1
        if completed_in_sprint:
            completed_count += 1
        if added_after_start:
            added_after += 1

        if completed_in_sprint or is_completed_state(str(state_cut)):
            pass
        elif normalize_state(str(state_cut)) in SPRINT_IN_PROGRESS_STATES:
            in_progress += 1
        else:
            pending += 1

        if include_story_details:
            stories.append(
                _story_view(
                    service,
                    sprint,
                    work_item_id,
                    fields,
                    state_start,
                    state_cut,
                    in_sprint_at_cut,
                    created_in_sprint,
                    completed_in_sprint,
                    added_after_start,
                    created_dt,
                    completed_snap.changed_at if completed_snap else None,
                )
            )

    completion = (completed_count / denominator * 100) if denominator else None

    metrics = SprintMetrics(
        stories_total=denominator,
        stories_created_in_sprint=created_in,
        stories_completed_in_sprint=completed_count,
        stories_in_progress=in_progress,
        stories_pending=pending,
        stories_added_after_start=added_after,
        stories_removed=removed,
        completion_percent=round(completion, 1) if completion is not None else None,
        completion_denominator=denominator,
        historical_limitations=sorted(set(limitations)),
    )
    return metrics, stories


def _story_view(
    service: AzureDevOpsService,
    sprint: DatedIteration,
    work_item_id: int,
    fields: dict,
    state_start: str | None,
    state_cut: str | None,
    in_sprint_at_cut: bool,
    created_in_sprint: bool,
    completed_in_sprint: bool,
    added_after_start: bool,
    created_dt: datetime | None,
    completed_dt: datetime | None,
) -> StorySprintView:
    from app.services.project_tracking.azure_wit import work_item_web_url

    return StorySprintView(
        work_item_id=work_item_id,
        title=str(fields.get("System.Title") or "").strip(),
        state_at_start=state_start,
        state_at_cut=str(state_cut) if state_cut else None,
        state_current=str(fields.get("System.State") or "").strip() or None,
        created_at=created_dt,
        completed_at=completed_dt,
        area_path=str(fields.get("System.AreaPath") or "").strip() or None,
        iteration_current=str(fields.get("System.IterationPath") or "").strip() or None,
        assignee=_assignee(fields),
        impediment=str(fields.get("Custom.TemouTeveimpedimentoUS") or "").strip() or None,
        in_sprint_at_cut=in_sprint_at_cut,
        created_in_sprint=created_in_sprint,
        completed_in_sprint=completed_in_sprint,
        added_after_start=added_after_start,
        azure_url=work_item_web_url(service, sprint.team_project, work_item_id),
    )


def sprint_row_from_iteration(sprint: DatedIteration) -> dict:
    start_d = parse_azure_calendar_date(sprint.start)
    finish_d = parse_azure_calendar_date(sprint.finish)
    if start_d is None or finish_d is None:
        return {}
    return {
        "sprint_key": _sprint_key(sprint),
        "team_project": sprint.team_project,
        "name": sprint.name,
        "path": sprint.path,
        "start_date": start_d.isoformat(),
        "finish_date": finish_d.isoformat(),
        "status": sprint_status(start_d, finish_d),
    }


def _sprint_key(sprint: DatedIteration) -> str:
    import base64

    raw = f"{sprint.team_project}\n{sprint.path}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_sprint_key(key: str) -> tuple[str, str]:
    import base64

    padding = "=" * (-len(key) % 4)
    raw = base64.urlsafe_b64decode(key + padding).decode("utf-8")
    project, path = raw.split("\n", 1)
    return project, path

from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy.orm import Session

from app.services.azure_devops import AzureDevOpsService
from app.services.project_tracking.azure_wit import list_dated_iterations
from app.services.project_tracking.catalog import ProjectScope, list_project_scopes, resolve_scope
from app.services.project_tracking.dates import month_bounds, parse_azure_calendar_date, periods_intersect
from app.services.project_tracking.sprint_analytics import (
    analyze_sprint_stories,
    decode_sprint_key,
    sprint_row_from_iteration,
)
from app.services.project_tracking.sprint_scope import sprint_matches_area
from app.services.project_tracking.story_consolidation import (
    StoryAppearance,
    appearances_from_stories,
    explicit_impediment_label,
)


def _filter_sprints_for_scope(sprints: list, scope: ProjectScope | None) -> list:
    if scope is None or not scope.area_path:
        return sprints
    return [
        sprint
        for sprint in sprints
        if sprint_matches_area(
            sprint_path=sprint.path,
            team_project=sprint.team_project,
            area_path=scope.area_path,
        )
    ]


def _sprints_for_period(
    service: AzureDevOpsService,
    team_projects: list[str],
    period_start: date,
    period_end: date,
) -> list:
    from app.services.project_tracking.azure_wit import DatedIteration

    matched: list[DatedIteration] = []
    for project in team_projects:
        for sprint in list_dated_iterations(service, project):
            start_d = parse_azure_calendar_date(sprint.start)
            finish_d = parse_azure_calendar_date(sprint.finish)
            if start_d is None or finish_d is None:
                continue
            if periods_intersect(start_d, finish_d, period_start, period_end):
                matched.append(sprint)
    matched.sort(key=lambda item: (item.team_project, item.start or "", item.path))
    return matched


def build_overview(
    service: AzureDevOpsService,
    *,
    year: int,
    month: int,
    scope: ProjectScope | None,
    all_scopes: list[ProjectScope],
    include_appearances: bool = False,
) -> dict:
    period_start, period_end = month_bounds(year, month)
    team_projects = [scope.team_project] if scope else sorted({s.team_project for s in all_scopes})
    sprints = _filter_sprints_for_scope(
        _sprints_for_period(service, team_projects, period_start, period_end),
        scope,
    )

    totals = {
        "projects_tracked": len(all_scopes) if scope is None else 1,
        "sprints_in_period": 0,
        "stories_created": 0,
        "stories_completed": 0,
        "stories_in_progress": 0,
        "stories_pending": 0,
        "stories_added_after_start": 0,
        "impediments_identified": 0,
    }
    project_cards: list[dict] = []
    limitations: list[str] = []
    appearances: list[StoryAppearance] = []

    scopes_for_cards = [scope] if scope else [s for s in all_scopes if s.area_path is None]

    for card_scope in scopes_for_cards:
        card_sprints = [
            s
            for s in sprints
            if s.team_project == card_scope.team_project
        ]
        card_metrics = {
            "stories_created": 0,
            "stories_completed": 0,
            "stories_in_progress": 0,
            "stories_pending": 0,
            "sprints": 0,
        }
        scoped_sprints = _filter_sprints_for_scope(card_sprints, card_scope)
        card_metrics["sprints"] = len(scoped_sprints)
        for sprint in scoped_sprints:
            metrics, _ = analyze_sprint_stories(
                service,
                sprint,
                area_path=card_scope.area_path,
                include_story_details=False,
            )
            card_metrics["stories_created"] += metrics.stories_created_in_sprint
            card_metrics["stories_completed"] += metrics.stories_completed_in_sprint
            card_metrics["stories_in_progress"] += metrics.stories_in_progress
            card_metrics["stories_pending"] += metrics.stories_pending
            limitations.extend(metrics.historical_limitations)

        project_cards.append(
            {
                "scope_key": card_scope.key,
                "label": card_scope.label,
                "team_project": card_scope.team_project,
                "area_path": card_scope.area_path,
                **card_metrics,
            }
        )

    for sprint in sprints:
        metrics, stories = analyze_sprint_stories(
            service,
            sprint,
            area_path=scope.area_path if scope else None,
            include_story_details=include_appearances,
        )
        if include_appearances:
            appearances.extend(_sprint_appearances(sprint_row_from_iteration(sprint), stories))
        totals["sprints_in_period"] += 1
        totals["stories_created"] += metrics.stories_created_in_sprint
        totals["stories_completed"] += metrics.stories_completed_in_sprint
        totals["stories_in_progress"] += metrics.stories_in_progress
        totals["stories_pending"] += metrics.stories_pending
        totals["stories_added_after_start"] += metrics.stories_added_after_start
        limitations.extend(metrics.historical_limitations)

    if not include_appearances:
        if scope and scope.area_path:
            from app.services.project_tracking.azure_wit import fetch_work_items, wiql_story_ids

            ids = wiql_story_ids(service, scope.team_project, area_path=scope.area_path)
            items = fetch_work_items(service, ids[:500])
            impediments = 0
            for item in items:
                fields = item.get("fields") or {}
                raw = str(fields.get("Custom.TemouTeveimpedimentoUS") or "").strip().lower()
                if raw and raw not in {"não", "nao", "none", ""}:
                    if "impedimento" in raw or "imped" in raw:
                        impediments += 1
            totals["impediments_identified"] = impediments
        else:
            totals["impediments_identified"] = 0
            limitations.append(
                "Impedimentos consolidados exigem filtro por área/projeto de negócio; visão geral usa soma de Sprints."
            )

    return {
        "year": year,
        "month": month,
        "scope_key": scope.key if scope else None,
        "indicators": totals,
        "project_cards": project_cards,
        "limitations": sorted(set(limitations))[:20],
        "data_source": "azure_devops",
        "appearances": appearances if include_appearances else [],
    }


def build_sprints_list(
    service: AzureDevOpsService,
    *,
    year: int,
    month: int,
    scope: ProjectScope | None,
    include_appearances: bool = False,
) -> dict:
    period_start, period_end = month_bounds(year, month)
    team_projects = [scope.team_project] if scope else []
    if not team_projects:
        return {"year": year, "month": month, "rows": [], "limitations": []}

    sprints = _filter_sprints_for_scope(
        _sprints_for_period(service, team_projects, period_start, period_end),
        scope,
    )
    rows: list[dict] = []
    limitations: list[str] = []
    appearances: list[StoryAppearance] = []
    if scope and scope.area_path:
        limitations.append(
            f"Sprints filtradas pela área «{scope.label}» (pasta de iteração correspondente no Azure)."
        )

    for sprint in sprints:
        base = sprint_row_from_iteration(sprint)
        if not base:
            continue
        metrics, stories = analyze_sprint_stories(
            service,
            sprint,
            area_path=scope.area_path if scope else None,
            include_story_details=include_appearances,
        )
        limitations.extend(metrics.historical_limitations)
        if scope and scope.area_path and metrics.stories_total == 0:
            continue
        if include_appearances:
            appearances.extend(_sprint_appearances(base, stories))
        rows.append(
            {
                **base,
                "stories_total": metrics.stories_total,
                "stories_created_in_sprint": metrics.stories_created_in_sprint,
                "stories_completed_in_sprint": metrics.stories_completed_in_sprint,
                "stories_pending": metrics.stories_pending,
                "completion_percent": metrics.completion_percent,
                "completion_denominator": metrics.completion_denominator,
                "completion_numerator": metrics.stories_completed_in_sprint,
            }
        )

    return {
        "year": year,
        "month": month,
        "scope_key": scope.key if scope else None,
        "rows": rows,
        "limitations": sorted(set(limitations))[:20],
        "appearances": appearances if include_appearances else [],
    }


def build_sprint_detail(service: AzureDevOpsService, sprint_key: str, *, area_path: str | None) -> dict:
    team_project, path = decode_sprint_key(sprint_key)
    from app.services.project_tracking.azure_wit import DatedIteration

    sprint: DatedIteration | None = None
    for candidate in list_dated_iterations(service, team_project):
        if candidate.path == path:
            sprint = candidate
            break
    if sprint is None:
        raise ValueError("Sprint não encontrada no Azure DevOps.")

    metrics, stories = analyze_sprint_stories(
        service,
        sprint,
        area_path=area_path,
        include_story_details=True,
    )
    base = sprint_row_from_iteration(sprint)
    return {
        **base,
        "metrics": {
            "stories_total": metrics.stories_total,
            "stories_created_in_sprint": metrics.stories_created_in_sprint,
            "stories_completed_in_sprint": metrics.stories_completed_in_sprint,
            "stories_in_progress": metrics.stories_in_progress,
            "stories_pending": metrics.stories_pending,
            "stories_added_after_start": metrics.stories_added_after_start,
            "stories_removed": metrics.stories_removed,
            "completion_percent": metrics.completion_percent,
            "completion_denominator": metrics.completion_denominator,
            "completion_numerator": metrics.stories_completed_in_sprint,
        },
        "limitations": metrics.historical_limitations,
        "stories": [
            {
                "work_item_id": s.work_item_id,
                "title": s.title,
                "state_at_start": s.state_at_start,
                "state_at_cut": s.state_at_cut,
                "state_current": s.state_current,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "area_path": s.area_path,
                "iteration_current": s.iteration_current,
                "assignee": s.assignee,
                "impediment": s.impediment,
                "created_in_sprint": s.created_in_sprint,
                "completed_in_sprint": s.completed_in_sprint,
                "added_after_start": s.added_after_start,
                "azure_url": s.azure_url,
            }
            for s in stories
        ],
    }


def list_sprint_refs(
    service: AzureDevOpsService,
    *,
    year: int,
    month: int | None,
    scope: ProjectScope,
) -> list[dict]:
    """Sprints com data que cruzam o período, sem calcular indicadores."""
    normalized = None if month in (None, 0) else month
    period_start, period_end = _period_bounds(year, normalized)
    sprints = _filter_sprints_for_scope(
        _sprints_for_period(service, [scope.team_project], period_start, period_end),
        scope,
    )
    refs: list[dict] = []
    seen: set[str] = set()
    for sprint in sprints:
        base = sprint_row_from_iteration(sprint)
        if not base:
            continue
        key = str(base["sprint_key"])
        if key in seen:
            continue
        seen.add(key)
        refs.append(base)
    refs.sort(key=lambda item: (item.get("start_date") or "", item.get("name") or ""))
    return refs


def _period_bounds(year: int, month: int | None) -> tuple[date, date]:
    if month is None or month == 0:
        return date(year, 1, 1), date(year, 12, 31)
    return month_bounds(year, month)


def _impediment_label(raw: str | None) -> str | None:
    return explicit_impediment_label(raw)


def _sprint_appearances(base: dict, stories: list) -> list[StoryAppearance]:
    if not base:
        return []
    return appearances_from_stories(
        stories,
        sprint_start=str(base.get("start_date") or ""),
        sprint_name=str(base.get("name") or ""),
        team_project=str(base.get("team_project") or ""),
    )


def build_evolution(
    service: AzureDevOpsService,
    *,
    year: int,
    month: int | None,
    scope: ProjectScope,
    include_appearances: bool = False,
) -> dict:
    period_start, period_end = _period_bounds(year, month)
    sprints = _filter_sprints_for_scope(
        _sprints_for_period(service, [scope.team_project], period_start, period_end),
        scope,
    )
    limitations: list[str] = []
    appearances: list[StoryAppearance] = []
    if scope.area_path:
        limitations.append(
            f"Linha do tempo filtrada pela área «{scope.label}» (Sprints e histórias correspondentes)."
        )

    timeline: list[dict] = []
    for sprint in sprints:
        base = sprint_row_from_iteration(sprint)
        if not base:
            continue
        metrics, stories = analyze_sprint_stories(
            service,
            sprint,
            area_path=scope.area_path,
            include_story_details=True,
        )
        limitations.extend(metrics.historical_limitations)
        if scope.area_path and metrics.stories_total == 0:
            continue
        if include_appearances:
            appearances.extend(_sprint_appearances(base, stories))

        completed = [
            {
                "work_item_id": s.work_item_id,
                "title": s.title,
                "azure_url": s.azure_url,
            }
            for s in stories
            if s.completed_in_sprint
        ][:25]
        pending = [
            {
                "work_item_id": s.work_item_id,
                "title": s.title,
                "state_at_cut": s.state_at_cut,
                "azure_url": s.azure_url,
            }
            for s in stories
            if not s.completed_in_sprint and s.in_sprint_at_cut
        ][:25]
        impediments = [
            {
                "work_item_id": s.work_item_id,
                "title": s.title,
                "impediment": label,
                "azure_url": s.azure_url,
            }
            for s in stories
            if (label := _impediment_label(s.impediment))
        ][:15]

        timeline.append(
            {
                **base,
                "metrics": {
                    "stories_total": metrics.stories_total,
                    "stories_completed_in_sprint": metrics.stories_completed_in_sprint,
                    "stories_pending": metrics.stories_pending,
                    "stories_in_progress": metrics.stories_in_progress,
                    "completion_percent": metrics.completion_percent,
                },
                "completed_stories": completed,
                "pending_stories": pending,
                "impediments": impediments,
            }
        )

    timeline.sort(key=lambda item: (item.get("start_date") or "", item.get("name") or ""))

    return {
        "year": year,
        "month": month if month else None,
        "scope_key": scope.key,
        "scope_label": scope.label,
        "team_project": scope.team_project,
        "area_path": scope.area_path,
        "timeline": timeline,
        "limitations": sorted(set(limitations))[:20],
        "data_source": "azure_devops",
        "appearances": appearances if include_appearances else [],
    }


def load_scopes(
    db: Session,
    service: AzureDevOpsService,
    *,
    apply_ignore_filter: bool = True,
) -> list[ProjectScope]:
    from app.services.project_tracking.catalog import configured_team_projects
    from app.services.azure_devops_config import get_ignored_project_scope_keys
    from app.services.project_tracking.scope_settings import filter_scopes

    projects = configured_team_projects(db)
    scopes = list_project_scopes(service, projects)
    if apply_ignore_filter:
        ignored = set(get_ignored_project_scope_keys(db))
        scopes = filter_scopes(scopes, ignored)
    return scopes

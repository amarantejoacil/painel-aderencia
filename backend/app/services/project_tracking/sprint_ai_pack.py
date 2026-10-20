from __future__ import annotations

from datetime import datetime, timezone

from app.services.project_tracking.dates import (
    end_of_day_cuiaba,
    now_utc,
    parse_azure_calendar_date,
    parse_azure_datetime,
    start_of_day_cuiaba,
)
from app.services.project_tracking.revisions import (
    WorkItemSnapshot,
    completed_transition_in_range,
    iteration_matches,
    snapshot_at,
    state_changes,
)
from app.services.project_tracking.states import is_completed_state, is_removed_state, normalize_state

IN_PROGRESS_STATES = frozenset(
    {"active", "new", "in progress", "inprogress", "committed", "approved", "doing"}
)

CRITERIA = {
    "stories_total": "Histórias previstas na Sprint: pelas revisões, estavam na Sprint no corte, foram criadas nela ou foram concluídas nela. Itens Removed ficam de fora. Distinto de histórias apenas criadas no período.",
    "stories_created": "Data de criação da história dentro do intervalo da Sprint (fuso America/Cuiaba).",
    "stories_completed": "Transição de estado para Closed, Resolved ou Done dentro do intervalo, lida nas revisões. O estado atual isolado não prova conclusão no fim de uma Sprint anterior.",
    "stories_in_progress": "No corte, estado de andamento (ex.: Active, New) e sem conclusão registrada no intervalo.",
    "stories_pending": "No corte, nem concluída no intervalo nem em estado de andamento.",
    "stories_reopened": "Esteve em estado concluído e voltou a um estado não concluído dentro do intervalo.",
    "stories_without_movement": "Sem mudança de estado, iteração ou responsável e sem comentário no intervalo, e não criada na Sprint.",
    "completion_percent": "Histórias concluídas no intervalo divididas pelas histórias consideradas na Sprint.",
    "cut": "Sprint encerrada: fim do dia de término. Sprint em andamento ou planejada: momento da análise, limitado ao fim da Sprint.",
    "collaborators": "Contagem de itens não mede produtividade. O responsável da história é independente dos responsáveis das Tasks.",
}

NO_EXPLICIT_IMPEDIMENT = (
    "Não foram identificados registros explícitos de impedimentos nas informações analisadas."
)


def _snapshots(revisions: list[dict]) -> list[WorkItemSnapshot]:
    snaps: list[WorkItemSnapshot] = []
    ordered = sorted(revisions, key=lambda item: int(item.get("revision") or 0))
    for item in ordered:
        snaps.append(
            WorkItemSnapshot(
                revision=int(item.get("revision") or 0),
                changed_at=parse_azure_datetime(item.get("changed_at")),
                state=item.get("state"),
                iteration_path=item.get("iteration_path"),
                area_path=item.get("area_path"),
                assignee=item.get("assignee"),
            )
        )
    return snaps


def _cut_moment(sprint: dict, analysis_at: datetime) -> datetime:
    finish = parse_azure_calendar_date(sprint.get("finish_date"))
    if finish is None:
        return analysis_at
    sprint_end = end_of_day_cuiaba(finish)
    if sprint.get("status") == "closed":
        return sprint_end
    if analysis_at.tzinfo is None:
        analysis_at = analysis_at.replace(tzinfo=timezone.utc)
    return min(analysis_at.astimezone(timezone.utc), sprint_end)


def _bounds(sprint: dict) -> tuple[datetime, datetime] | None:
    start = parse_azure_calendar_date(sprint.get("start_date"))
    finish = parse_azure_calendar_date(sprint.get("finish_date"))
    if start is None or finish is None:
        return None
    return start_of_day_cuiaba(start), end_of_day_cuiaba(finish)


def _in_window(moment: datetime | None, start: datetime, end: datetime) -> bool:
    return bool(moment and start <= moment <= end)


def _comment_in_window(comments: list[dict], start: datetime, end: datetime) -> bool:
    for comment in comments:
        if _in_window(parse_azure_datetime(comment.get("created_at")), start, end):
            return True
    return False


def _changes_in_window(snapshots: list[WorkItemSnapshot], start: datetime, end: datetime) -> dict:
    state_changed = False
    iteration_changed = False
    assignee_changed = False
    reopened = False
    saw_completed = False
    reassignment: list[dict] = []
    prev: WorkItemSnapshot | None = None
    for snap in snapshots:
        if prev is None:
            prev = snap
            continue
        moment = snap.changed_at
        if not _in_window(moment, start, end):
            prev = snap
            continue
        if normalize_state(prev.state) != normalize_state(snap.state):
            state_changed = True
            if is_completed_state(snap.state):
                saw_completed = True
            elif saw_completed or is_completed_state(prev.state):
                reopened = True
                saw_completed = is_completed_state(snap.state)
        if (prev.iteration_path or "") != (snap.iteration_path or ""):
            iteration_changed = True
        if (prev.assignee or "") != (snap.assignee or ""):
            assignee_changed = True
            reassignment.append(
                {
                    "at": moment.isoformat() if moment else None,
                    "from": prev.assignee,
                    "to": snap.assignee,
                }
            )
        prev = snap
    return {
        "state_changed": state_changed,
        "iteration_changed": iteration_changed,
        "assignee_changed": assignee_changed,
        "reopened": reopened,
        "reassignment": reassignment,
    }


def _bucket(state: str | None, completed_in_sprint: bool) -> str:
    if completed_in_sprint:
        return "completed"
    if is_completed_state(state):
        return "already_done"
    if normalize_state(state) in IN_PROGRESS_STATES:
        return "in_progress"
    return "pending"


def _task_bucket(state: str | None) -> str:
    if is_completed_state(state) or is_removed_state(state):
        return "completed" if is_completed_state(state) else "pending"
    if normalize_state(state) in IN_PROGRESS_STATES:
        return "in_progress"
    return "pending"


def _explicit_impediment_text(story: dict) -> str | None:
    raw = str(story.get("impediment_field") or "").strip()
    lowered = raw.casefold()
    if raw and lowered not in {"não", "nao", "none"} and "imped" in lowered:
        return raw
    for tag in story.get("tags") or []:
        if "imped" in str(tag).casefold():
            return f"Tag: {tag}"
    for comment in story.get("comments") or []:
        text = str(comment.get("text") or "")
        if "imped" in text.casefold():
            author = comment.get("author") or "autor não identificado"
            return f"Comentário de {author}: {text[:240]}"
    for task in story.get("tasks") or []:
        for comment in task.get("comments") or []:
            text = str(comment.get("text") or "")
            if "imped" in text.casefold():
                return f"Task #{task.get('work_item_id')}: {text[:240]}"
    return None


def analyze_story(story: dict, sprint: dict, analysis_at: datetime) -> dict | None:
    bounds = _bounds(sprint)
    if bounds is None:
        return None
    start, end = bounds
    cut = _cut_moment(sprint, analysis_at)
    snapshots = _snapshots(story.get("revisions") or [])
    at_start = snapshot_at(snapshots, start)
    at_cut = snapshot_at(snapshots, cut)
    state_cut = (at_cut.state if at_cut else None) or story.get("state_current")
    iteration_cut = (at_cut.iteration_path if at_cut else None) or story.get("iteration_current")
    assignee_cut = (at_cut.assignee if at_cut else None) or story.get("assignee_current")
    path = sprint.get("path") or ""
    in_sprint_at_cut = iteration_matches(str(iteration_cut) if iteration_cut else None, path)
    in_sprint_at_start = iteration_matches(at_start.iteration_path if at_start else None, path)
    created_at = parse_azure_datetime(story.get("created_at"))
    created_in_sprint = _in_window(created_at, start, cut)
    completed_snap = completed_transition_in_range(snapshots, start, cut)
    completed_in_sprint = completed_snap is not None
    if is_removed_state(str(state_cut)):
        return {
            "work_item_id": story["work_item_id"],
            "counted": False,
            "removed": True,
            "title": story.get("title"),
            "azure_url": story.get("azure_url"),
        }
    counted = in_sprint_at_cut or completed_in_sprint or created_in_sprint or in_sprint_at_start
    if not counted:
        return None
    window = _changes_in_window(snapshots, start, cut)
    added_after_start = bool(in_sprint_at_cut and not in_sprint_at_start and not created_in_sprint)
    transferred_out = bool(in_sprint_at_start and not in_sprint_at_cut)
    comments = story.get("comments") or []
    no_movement = (
        not created_in_sprint
        and not window["state_changed"]
        and not window["iteration_changed"]
        and not window["assignee_changed"]
        and not _comment_in_window(comments, start, cut)
    )
    bucket = _bucket(str(state_cut) if state_cut else None, completed_in_sprint)
    impediment = _explicit_impediment_text(story)
    movements: list[str] = []
    if created_in_sprint:
        movements.append("criada na Sprint")
    if completed_in_sprint:
        movements.append("concluída na Sprint")
    if window["reopened"]:
        movements.append("reaberta")
    if added_after_start:
        movements.append("adicionada após o início")
    if transferred_out:
        movements.append("transferida para fora da Sprint")
    for change in window["reassignment"]:
        movements.append(
            f"responsável de {change.get('from') or 'sem responsável'} para {change.get('to') or 'sem responsável'}"
        )
    return {
        "work_item_id": story["work_item_id"],
        "title": story.get("title"),
        "azure_url": story.get("azure_url"),
        "counted": True,
        "removed": False,
        "created_in_sprint": created_in_sprint,
        "completed_in_sprint": completed_in_sprint,
        "reopened": window["reopened"],
        "no_movement": no_movement,
        "added_after_start": added_after_start,
        "transferred_out": transferred_out,
        "bucket": bucket,
        "state_at_cut": state_cut,
        "assignee_at_cut": assignee_cut,
        "feature": story.get("feature"),
        "movements": movements,
        "reassignment": window["reassignment"],
        "impediment": impediment,
        "description": story.get("description") or "",
        "acceptance": story.get("acceptance") or "",
        "tags": story.get("tags") or [],
        "comments": comments[:8],
        "tasks": story.get("tasks") or [],
    }


def _empty_indicators() -> dict:
    return {
        "stories_total": 0,
        "stories_created": 0,
        "stories_completed": 0,
        "stories_in_progress": 0,
        "stories_pending": 0,
        "stories_reopened": 0,
        "stories_without_movement": 0,
        "stories_added_after_start": 0,
        "stories_transferred_out": 0,
        "completion_percent": None,
        "completion_numerator": 0,
        "completion_denominator": 0,
        "tasks_total": 0,
    }


def _apply_flags(indicators: dict, flags: dict) -> None:
    indicators["stories_total"] += 1
    indicators["completion_denominator"] += 1
    if flags["created_in_sprint"]:
        indicators["stories_created"] += 1
    if flags["completed_in_sprint"]:
        indicators["stories_completed"] += 1
        indicators["completion_numerator"] += 1
    if flags["reopened"]:
        indicators["stories_reopened"] += 1
    if flags["no_movement"]:
        indicators["stories_without_movement"] += 1
    if flags["added_after_start"]:
        indicators["stories_added_after_start"] += 1
    if flags["transferred_out"]:
        indicators["stories_transferred_out"] += 1
    if flags["bucket"] == "in_progress":
        indicators["stories_in_progress"] += 1
    elif flags["bucket"] == "pending":
        indicators["stories_pending"] += 1
    indicators["tasks_total"] += len(flags.get("tasks") or [])


def _finalize(indicators: dict) -> dict:
    den = indicators["completion_denominator"]
    num = indicators["completion_numerator"]
    indicators["completion_percent"] = round(100.0 * num / den, 1) if den else None
    return indicators


def _collaborator_key(name: str | None) -> str:
    text = (name or "").strip()
    return text or "Sem responsável"


def build_analysis_pack(
    sprints: list[dict],
    *,
    scope_label: str,
    analysis_at: datetime | None = None,
    limitations: list[str] | None = None,
) -> dict:
    moment = analysis_at or now_utc()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    sprint_rows: list[dict] = []
    evidence: list[dict] = []
    seen_evidence: set[int] = set()
    explicit: list[dict] = []
    collaborator_map: dict[str, dict] = {}
    unique: dict[int, dict] = {}
    unique_tasks: set[int] = set()
    seen_story_ids: set[int] = set()
    seen_task_ids: set[int] = set()
    notes = list(limitations or [])

    for sprint in sprints:
        indicators = _empty_indicators()
        analyzed: list[dict] = []
        if _bounds(sprint) is None:
            notes.append(f"Sprint {sprint.get('name')} sem datas; indicadores não calculados.")
            continue
        for story in sprint.get("stories") or []:
            flags = analyze_story(story, sprint, moment)
            if not flags or not flags.get("counted"):
                continue
            _apply_flags(indicators, flags)
            analyzed.append(flags)
            work_id = int(flags["work_item_id"])
            if work_id not in seen_evidence:
                seen_evidence.add(work_id)
                evidence.append(
                    {
                        "work_item_id": work_id,
                        "title": flags.get("title"),
                        "azure_url": flags.get("azure_url"),
                        "kind": "story",
                    }
                )
            if flags.get("impediment"):
                explicit.append(
                    {
                        "work_item_id": work_id,
                        "title": flags.get("title"),
                        "azure_url": flags.get("azure_url"),
                        "description": flags["impediment"],
                        "assignee": flags.get("assignee_at_cut"),
                        "sprint_name": sprint.get("name"),
                    }
                )
            work_already = work_id in seen_story_ids
            seen_story_ids.add(work_id)
            owner = _collaborator_key(flags.get("assignee_at_cut"))
            bucket = collaborator_map.setdefault(
                owner,
                {
                    "name": owner,
                    "stories": 0,
                    "tasks": 0,
                    "completed": 0,
                    "in_progress": 0,
                    "pending": 0,
                    "items": [],
                    "reassignments": [],
                },
            )
            if not work_already:
                bucket["stories"] += 1
                if flags["bucket"] == "completed":
                    bucket["completed"] += 1
                elif flags["bucket"] == "in_progress":
                    bucket["in_progress"] += 1
                elif flags["bucket"] == "pending":
                    bucket["pending"] += 1
            bucket["items"].append(
                {
                    "kind": "story",
                    "work_item_id": work_id,
                    "title": flags.get("title"),
                    "azure_url": flags.get("azure_url"),
                    "bucket": flags["bucket"],
                    "sprint_name": sprint.get("name"),
                }
            )
            bucket["reassignments"].extend(
                {"work_item_id": work_id, **item} for item in flags.get("reassignment") or []
            )
            for task in flags.get("tasks") or []:
                task_id = int(task["work_item_id"])
                unique_tasks.add(task_id)
                task_already = task_id in seen_task_ids
                seen_task_ids.add(task_id)
                task_owner = _collaborator_key(task.get("assignee"))
                task_row = collaborator_map.setdefault(
                    task_owner,
                    {
                        "name": task_owner,
                        "stories": 0,
                        "tasks": 0,
                        "completed": 0,
                        "in_progress": 0,
                        "pending": 0,
                        "items": [],
                        "reassignments": [],
                    },
                )
                task_bucket = _task_bucket(task.get("state"))
                if not task_already:
                    task_row["tasks"] += 1
                    if task_bucket == "completed":
                        task_row["completed"] += 1
                    elif task_bucket == "in_progress":
                        task_row["in_progress"] += 1
                    else:
                        task_row["pending"] += 1
                task_row["items"].append(
                    {
                        "kind": "task",
                        "work_item_id": task_id,
                        "title": task.get("title"),
                        "azure_url": task.get("azure_url"),
                        "bucket": task_bucket,
                        "parent_id": work_id,
                        "sprint_name": sprint.get("name"),
                    }
                )
                if task_id not in seen_evidence:
                    seen_evidence.add(task_id)
                    evidence.append(
                        {
                            "work_item_id": task_id,
                            "title": task.get("title"),
                            "azure_url": task.get("azure_url"),
                            "kind": "task",
                        }
                    )
            previous = unique.get(work_id)
            if previous is None:
                unique[work_id] = flags
            else:
                merged = dict(previous)
                for key in (
                    "created_in_sprint",
                    "completed_in_sprint",
                    "reopened",
                    "added_after_start",
                    "transferred_out",
                ):
                    merged[key] = bool(previous.get(key) or flags.get(key))
                merged["no_movement"] = bool(previous.get("no_movement") and flags.get("no_movement"))
                if flags["completed_in_sprint"] or previous["completed_in_sprint"]:
                    merged["bucket"] = "completed"
                else:
                    merged["bucket"] = flags["bucket"]
                merged["tasks"] = list(previous.get("tasks") or [])
                known = {int(item["work_item_id"]) for item in merged["tasks"]}
                for task in flags.get("tasks") or []:
                    if int(task["work_item_id"]) not in known:
                        merged["tasks"].append(task)
                unique[work_id] = merged

        _finalize(indicators)
        sprint_rows.append(
            {
                "sprint_key": sprint.get("sprint_key"),
                "name": sprint.get("name"),
                "team_project": sprint.get("team_project"),
                "area_label": sprint.get("area_label"),
                "path": sprint.get("path"),
                "start_date": sprint.get("start_date"),
                "finish_date": sprint.get("finish_date"),
                "status": sprint.get("status"),
                "indicators": indicators,
                "stories": [
                    {
                        "work_item_id": item["work_item_id"],
                        "title": item.get("title"),
                        "azure_url": item.get("azure_url"),
                        "state_at_cut": item.get("state_at_cut"),
                        "assignee_at_cut": item.get("assignee_at_cut"),
                        "feature": item.get("feature"),
                        "bucket": item.get("bucket"),
                        "movements": item.get("movements"),
                        "description": (item.get("description") or "")[:500],
                        "acceptance": (item.get("acceptance") or "")[:400],
                        "tags": item.get("tags") or [],
                        "comments": item.get("comments") or [],
                        "tasks": [
                            {
                                "work_item_id": task.get("work_item_id"),
                                "title": task.get("title"),
                                "state": task.get("state"),
                                "assignee": task.get("assignee"),
                            }
                            for task in item.get("tasks") or []
                        ],
                        "impediment": item.get("impediment"),
                    }
                    for item in analyzed
                ],
            }
        )

    consolidated = _empty_indicators()
    for flags in unique.values():
        _apply_flags(consolidated, flags)
    consolidated["tasks_total"] = len(unique_tasks)
    _finalize(consolidated)

    collaborators = sorted(collaborator_map.values(), key=lambda item: item["name"].casefold())
    return {
        "analysis_at": moment.isoformat(),
        "scope_label": scope_label,
        "criteria": CRITERIA,
        "sprints": sprint_rows,
        "consolidated": consolidated,
        "collaborators": collaborators,
        "explicit_impediments": explicit,
        "impediments_note": None if explicit else NO_EXPLICIT_IMPEDIMENT,
        "limitations": list(dict.fromkeys(notes)),
        "evidence_index": evidence,
        "multiple_sprints": len(sprint_rows) >= 2,
    }

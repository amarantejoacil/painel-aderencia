from datetime import datetime, timezone

from app.services.project_tracking.sprint_ai_pack import build_analysis_pack
from app.services.project_tracking.sprint_ai_schema import SprintAiNarrative, sanitize_narrative

PATH = "Projeto\\Sprint 1"
PATH_2 = "Projeto\\Sprint 2"
WHEN = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)


def _sprint(name: str, path: str, start: str, finish: str, status: str, stories: list[dict]) -> dict:
    return {
        "sprint_key": name,
        "name": name,
        "team_project": "Projeto",
        "area_label": "Área",
        "path": path,
        "start_date": start,
        "finish_date": finish,
        "status": status,
        "stories": stories,
    }


def _story(
    work_item_id: int,
    revisions: list[dict],
    *,
    assignee: str | None = None,
    created_at: str = "2026-09-01T12:00:00Z",
    tasks: list[dict] | None = None,
    comments: list[dict] | None = None,
    impediment_field: str | None = None,
) -> dict:
    return {
        "work_item_id": work_item_id,
        "title": f"História {work_item_id}",
        "description": "",
        "acceptance": "",
        "state_current": revisions[-1]["state"] if revisions else None,
        "assignee_current": assignee,
        "created_at": created_at,
        "tags": [],
        "iteration_current": revisions[-1]["iteration_path"] if revisions else None,
        "azure_url": f"https://example.test/{work_item_id}",
        "comments": comments or [],
        "revisions": revisions,
        "tasks": tasks or [],
        "impediment_field": impediment_field,
        "feature": None,
    }


def _rev(revision: int, at: str, state: str, iteration: str, assignee: str | None = "Ana") -> dict:
    return {
        "revision": revision,
        "changed_at": at,
        "state": state,
        "iteration_path": iteration,
        "area_path": "Projeto\\Área",
        "assignee": assignee,
    }


def test_reopened_unassigned_and_transferred() -> None:
    reopened = _story(
        1,
        [
            _rev(1, "2026-09-20T12:00:00Z", "Closed", PATH),
            _rev(2, "2026-10-05T12:00:00Z", "Active", PATH),
        ],
    )
    unassigned = _story(
        2,
        [_rev(1, "2026-09-20T12:00:00Z", "New", PATH, assignee=None)],
        assignee=None,
    )
    transferred = _story(
        3,
        [
            _rev(1, "2026-09-20T12:00:00Z", "Active", PATH, assignee="Bruno"),
            _rev(2, "2026-10-06T12:00:00Z", "Active", PATH_2, assignee="Bruno"),
        ],
        assignee="Bruno",
    )
    pack = build_analysis_pack(
        [
            _sprint(
                "S1",
                PATH,
                "2026-10-01",
                "2026-10-14",
                "closed",
                [reopened, unassigned, transferred],
            )
        ],
        scope_label="Área",
        analysis_at=WHEN,
    )
    indicators = pack["sprints"][0]["indicators"]
    assert indicators["stories_reopened"] == 1
    assert indicators["stories_transferred_out"] == 1
    names = {row["name"] for row in pack["collaborators"]}
    assert "Sem responsável" in names


def test_closed_sprint_ignores_change_after_finish() -> None:
    story = _story(
        10,
        [
            _rev(1, "2026-10-02T12:00:00Z", "Active", PATH),
            _rev(2, "2026-10-20T12:00:00Z", "Closed", PATH),
        ],
    )
    pack = build_analysis_pack(
        [_sprint("S1", PATH, "2026-10-01", "2026-10-14", "closed", [story])],
        scope_label="Área",
        analysis_at=WHEN,
    )
    assert pack["consolidated"]["stories_completed"] == 0
    assert pack["sprints"][0]["stories"][0]["state_at_cut"] == "Active"


def test_active_sprint_uses_analysis_date() -> None:
    story = _story(
        11,
        [
            _rev(1, "2026-10-02T12:00:00Z", "Active", PATH),
            _rev(2, "2026-10-18T12:00:00Z", "Closed", PATH),
        ],
    )
    early = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)
    pack = build_analysis_pack(
        [_sprint("S1", PATH, "2026-10-01", "2026-10-31", "active", [story])],
        scope_label="Área",
        analysis_at=early,
    )
    assert pack["consolidated"]["stories_completed"] == 0
    assert pack["sprints"][0]["stories"][0]["state_at_cut"] == "Active"


def test_unique_story_across_sprints() -> None:
    first = _story(7, [_rev(1, "2026-10-02T12:00:00Z", "Active", PATH)])
    second = _story(
        7,
        [
            _rev(1, "2026-10-02T12:00:00Z", "Active", PATH),
            _rev(2, "2026-10-20T12:00:00Z", "Closed", PATH_2),
        ],
    )
    pack = build_analysis_pack(
        [
            _sprint("S1", PATH, "2026-10-01", "2026-10-14", "closed", [first]),
            _sprint("S2", PATH_2, "2026-10-15", "2026-10-31", "active", [second]),
        ],
        scope_label="Área",
        analysis_at=WHEN,
    )
    assert pack["sprints"][0]["indicators"]["stories_total"] == 1
    assert pack["sprints"][1]["indicators"]["stories_completed"] == 1
    assert pack["consolidated"]["stories_total"] == 1
    assert pack["consolidated"]["stories_completed"] == 1
    assert pack["multiple_sprints"] is True


def test_no_comments_and_explicit_impediment_note() -> None:
    quiet = _story(4, [_rev(1, "2026-09-01T12:00:00Z", "New", PATH)])
    pack = build_analysis_pack(
        [_sprint("S1", PATH, "2026-10-01", "2026-10-14", "closed", [quiet])],
        scope_label="Área",
        analysis_at=WHEN,
    )
    assert pack["sprints"][0]["indicators"]["stories_without_movement"] == 1
    assert pack["explicit_impediments"] == []
    assert "Não foram identificados" in pack["impediments_note"]


def test_sanitize_drops_invented_impediments() -> None:
    pack = {"evidence_index": [{"work_item_id": 1}], "explicit_impediments": [], "multiple_sprints": False}
    narrative = SprintAiNarrative(
        executive_summary="Resumo",
        risks={
            "confirmed_impediments": [
                {
                    "description": "Inventado",
                    "impact": "Alto",
                    "known_status": "Aberto",
                    "evidence_ids": [1],
                    "kind": "fact",
                }
            ],
            "registered_challenges": [],
            "alerts": [],
        },
        management_actions=[
            {
                "action": "Validar a entrega",
                "reason": "Confirmar estágio",
                "priority": "alta",
                "evidence_ids": [1],
            }
        ],
        comparison_narrative="não deveria",
    )
    cleaned = sanitize_narrative(narrative, pack)
    assert cleaned["schema_version"] == 2
    assert cleaned["impediments"] == []
    assert cleaned["risks"]["confirmed_impediments"] == []
    assert cleaned["impediments_note"]
    assert cleaned["next_steps"][0]["kind"] == "recommendation"
    assert cleaned["comparison_narrative"] is None


def test_sanitize_v2_work_fronts_require_story_ids() -> None:
    pack = {"evidence_index": [{"work_item_id": 10}, {"work_item_id": 11}], "explicit_impediments": [], "multiple_sprints": False}
    narrative = SprintAiNarrative(
        executive_summary="Parágrafo um.\n\nParágrafo dois.",
        work_fronts=[
            {
                "name": "Sem histórias",
                "summary": "X",
                "expected_benefit": "Y",
                "situation": "Z",
                "story_ids": [],
            },
            {
                "name": "Com histórias",
                "summary": "Resumo",
                "expected_benefit": "Benefício",
                "situation": "Em andamento",
                "story_ids": [10, 99],
            },
        ],
    )
    cleaned = sanitize_narrative(narrative, pack)
    assert len(cleaned["work_fronts"]) == 1
    assert cleaned["work_fronts"][0]["story_ids"] == [10]

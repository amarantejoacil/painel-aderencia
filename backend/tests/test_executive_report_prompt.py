import json

from app.services.project_tracking.catalog import ProjectScope
from app.services.project_tracking.executive_targets import (
    MAX_EXECUTIVE_SPRINTS,
    scope_label_for,
    target_scopes,
    trim_sprint_refs,
    validate_period,
)
from app.services.project_tracking.sprint_ai_schema import (
    SYSTEM_INSTRUCTION,
    executive_system_instruction,
    narrative_user_content,
)


def _scope(key: str, project: str, area: str | None) -> ProjectScope:
    return ProjectScope(key=key, label=area or project, team_project=project, area_path=area)


def test_sprint_analysis_prompt_stays_two_paragraphs() -> None:
    assert "até dois parágrafos" in SYSTEM_INSTRUCTION
    assert "até três parágrafos" not in SYSTEM_INSTRUCTION


def test_executive_prompts_cover_the_four_reports() -> None:
    monthly = executive_system_instruction("monthly")
    evolution = executive_system_instruction("evolution")
    consolidated = executive_system_instruction("consolidated")
    sprints = executive_system_instruction("sprints")
    assert "até três parágrafos" in monthly
    assert "não repita o mesmo conteúdo por Sprint" in monthly
    assert "planejado" in evolution and "concluído" in evolution
    assert "quantidade de histórias" in consolidated
    assert "não ranqueie" in consolidated
    assert "conjunto de Sprints" in sprints
    assert "até dois parágrafos" in SYSTEM_INSTRUCTION


def test_user_payload_marks_report_type_without_changing_sprint_analysis() -> None:
    pack = {"scope_label": "PAN", "collaborators": [], "sprints": []}
    plain = json.loads(narrative_user_content(pack))
    marked = json.loads(narrative_user_content(pack, report_type="consolidated"))
    assert "report_type" not in plain
    assert marked["report_type"] == "consolidated"
    assert "quantidade de histórias" in marked["report_focus"]


def test_targets_and_period_rules() -> None:
    team = _scope("p::*", "Projeto", None)
    area = _scope("p::a", "Projeto", "Projeto\\Área")
    assert target_scopes("monthly", area, [team, area]) == [area]
    assert target_scopes("consolidated", None, [team, area]) == [team]
    try:
        target_scopes("consolidated", area, [team, area])
        raise AssertionError("consolidado com área deveria falhar")
    except ValueError:
        pass
    try:
        validate_period("monthly", 0)
        raise AssertionError("mês obrigatório")
    except ValueError:
        pass
    validate_period("evolution", 0)


def test_trim_keeps_the_most_recent_sprints() -> None:
    refs = [
        {"sprint_key": f"s{index}", "name": f"Sprint {index}", "start_date": f"2026-01-{index:02d}"}
        for index in range(1, MAX_EXECUTIVE_SPRINTS + 4)
    ]
    kept, note = trim_sprint_refs(refs)
    assert len(kept) == MAX_EXECUTIVE_SPRINTS
    assert kept[0]["sprint_key"] == "s4"
    assert kept[-1]["sprint_key"] == f"s{MAX_EXECUTIVE_SPRINTS + 3}"
    assert note is not None and "mais recentes" in note
    label = scope_label_for([_scope("a", "A", None), _scope("b", "B", None)])
    assert label.startswith("Projetos acompanhados:")

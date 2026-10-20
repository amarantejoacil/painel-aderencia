"""Consolidação de histórias entre Sprints para os relatórios.

A tela de Sprints continua contando cada Sprint separadamente. Quando o
relatório soma o período, a mesma história pode ter aparecido em mais de uma
Sprint: aqui ela entra uma única vez.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.project_tracking.states import is_completed_state, is_removed_state, normalize_state

# Mesmo conjunto usado por analyze_sprint_stories. A análise com IA aceita
# estados adicionais (Committed, Approved, Doing) e não deve ser alterada aqui.
SPRINT_IN_PROGRESS_STATES = frozenset({"active", "new", "in progress", "inprogress"})


INDICATOR_CRITERIA: list[dict[str, str]] = [
    {
        "key": "stories_in_sprint",
        "label": "Histórias da Sprint",
        "description": (
            "Na tela de Sprints e em cada linha de Sprint do relatório, a história entra "
            "se, pelas revisões, estava na Sprint no corte, foi criada nela ou foi concluída "
            "nela. Itens Removed ficam de fora. O fuso é America/Cuiaba."
        ),
    },
    {
        "key": "stories_created",
        "label": "Histórias criadas",
        "description": (
            "Data de criação dentro do intervalo completo da Sprint, do início do primeiro "
            "dia ao fim do último. No total do período, conta uma vez se isso ocorreu em "
            "qualquer Sprint do recorte."
        ),
    },
    {
        "key": "stories_completed",
        "label": "Histórias concluídas",
        "description": (
            "Transição para Closed, Resolved ou Done dentro do intervalo da Sprint, lida "
            "nas revisões. O estado atual sozinho não conta como conclusão daquela Sprint. "
            "No total do período, conta uma vez se houve essa transição em qualquer Sprint."
        ),
    },
    {
        "key": "stories_in_progress",
        "label": "Histórias em andamento",
        "description": (
            "No corte da Sprint, estado Active, New ou In Progress, sem conclusão registrada "
            "no intervalo. No total do período, a história só fica em andamento se não tiver "
            "sido concluída em nenhuma Sprint do recorte e se o corte da Sprint mais recente "
            "em que ela aparece for de andamento."
        ),
    },
    {
        "key": "stories_pending",
        "label": "Histórias pendentes",
        "description": (
            "No corte, nem concluída no intervalo nem em estado de andamento. Um estado já "
            "concluído sem transição dentro da Sprint não entra em pendentes nem em andamento. "
            "No período, vale o corte da Sprint mais recente, salvo se houve conclusão em "
            "alguma Sprint."
        ),
    },
    {
        "key": "stories_added_after_start",
        "label": "Histórias adicionadas após o início",
        "description": (
            "Estava na Sprint no corte, não estava no início e não foi criada na Sprint. "
            "No período, conta uma vez se isso ocorreu em qualquer Sprint."
        ),
    },
    {
        "key": "impediments",
        "label": "Impedimentos",
        "description": (
            "No relatório, impedimento é o texto explícito do campo da história nas histórias "
            "efetivamente analisadas no período. Respostas vazias, «não» ou «none» não contam. "
            "A mesma história conta uma vez. Este número não varre a área inteira fora das Sprints."
        ),
    },
    {
        "key": "unique_period",
        "label": "Totais do período",
        "description": (
            "Os totais do relatório contam cada história uma vez, mesmo que ela apareça em "
            "mais de uma Sprint. As linhas de cada Sprint continuam podendo repetir essa história, "
            "porque descrevem o recorte daquela Sprint."
        ),
    },
]


@dataclass(frozen=True)
class StoryAppearance:
    work_item_id: int
    sprint_start: str
    sprint_name: str
    team_project: str
    created_in_sprint: bool
    completed_in_sprint: bool
    added_after_start: bool
    state_at_cut: str | None
    impediment: str | None


def explicit_impediment_label(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip()
    lowered = text.casefold()
    if lowered in {"não", "nao", "none"}:
        return None
    if "imped" in lowered:
        return text
    return None


def _bucket(state: str | None, *, completed_in_sprint: bool) -> str:
    if completed_in_sprint:
        return "completed"
    if is_completed_state(state):
        return "already_done"
    if normalize_state(state) in SPRINT_IN_PROGRESS_STATES:
        return "in_progress"
    return "pending"


def empty_unique_indicators() -> dict[str, int]:
    return {
        "stories_total": 0,
        "stories_created": 0,
        "stories_completed": 0,
        "stories_in_progress": 0,
        "stories_pending": 0,
        "stories_already_done": 0,
        "stories_added_after_start": 0,
        "impediments_identified": 0,
    }


def appearances_from_stories(
    stories: list,
    *,
    sprint_start: str,
    sprint_name: str,
    team_project: str,
) -> list[StoryAppearance]:
    found: list[StoryAppearance] = []
    for story in stories:
        state = getattr(story, "state_at_cut", None)
        if is_removed_state(str(state) if state is not None else None):
            continue
        found.append(
            StoryAppearance(
                work_item_id=int(story.work_item_id),
                sprint_start=sprint_start,
                sprint_name=sprint_name,
                team_project=team_project,
                created_in_sprint=bool(story.created_in_sprint),
                completed_in_sprint=bool(story.completed_in_sprint),
                added_after_start=bool(story.added_after_start),
                state_at_cut=str(state) if state else None,
                impediment=getattr(story, "impediment", None),
            )
        )
    return found


def consolidate_appearances(appearances: list[StoryAppearance]) -> dict[str, int]:
    grouped: dict[int, list[StoryAppearance]] = {}
    for item in appearances:
        grouped.setdefault(item.work_item_id, []).append(item)

    totals = empty_unique_indicators()
    for group in grouped.values():
        ordered = sorted(group, key=lambda item: (item.sprint_start, item.sprint_name, item.team_project))
        latest = ordered[-1]
        completed = any(item.completed_in_sprint for item in ordered)
        bucket = _bucket(latest.state_at_cut, completed_in_sprint=completed)
        totals["stories_total"] += 1
        if any(item.created_in_sprint for item in ordered):
            totals["stories_created"] += 1
        if completed:
            totals["stories_completed"] += 1
        if any(item.added_after_start for item in ordered):
            totals["stories_added_after_start"] += 1
        if bucket == "in_progress":
            totals["stories_in_progress"] += 1
        elif bucket == "pending":
            totals["stories_pending"] += 1
        elif bucket == "already_done":
            totals["stories_already_done"] += 1
        if any(explicit_impediment_label(item.impediment) for item in ordered):
            totals["impediments_identified"] += 1
    return totals


def consolidate_by_team(appearances: list[StoryAppearance]) -> dict[str, dict[str, int]]:
    grouped: dict[str, list[StoryAppearance]] = {}
    for item in appearances:
        grouped.setdefault(item.team_project, []).append(item)
    return {team: consolidate_appearances(items) for team, items in grouped.items()}

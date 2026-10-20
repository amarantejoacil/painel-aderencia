from __future__ import annotations

from app.services.project_tracking.catalog import ProjectScope

MAX_EXECUTIVE_SPRINTS = 16

ReportKind = str


def validate_period(report_type: str, month: int) -> None:
    if report_type == "evolution":
        if month < 0 or month > 12:
            raise ValueError("Informe o mês ou o ano inteiro para o relatório de evolução.")
        return
    if month < 1 or month > 12:
        raise ValueError("Informe o mês para este relatório.")


def target_scopes(
    report_type: str,
    scope: ProjectScope | None,
    all_scopes: list[ProjectScope],
) -> list[ProjectScope]:
    if report_type == "consolidated":
        if scope is not None:
            raise ValueError("Relatório consolidado não usa filtro de projeto/área.")
        teams = [item for item in all_scopes if item.area_path is None]
        if not teams:
            raise ValueError("Nenhum projeto acompanhado está configurado.")
        return teams
    if report_type not in {"monthly", "sprints", "evolution"}:
        raise ValueError("Tipo de relatório inválido.")
    if scope is None:
        raise ValueError("Selecione um projeto/área para este relatório.")
    return [scope]


def scope_label_for(scopes: list[ProjectScope]) -> str:
    if len(scopes) == 1:
        return scopes[0].label
    text = "Projetos acompanhados: " + ", ".join(item.label for item in scopes)
    return text[:500]


def trim_sprint_refs(refs: list[dict], *, limit: int = MAX_EXECUTIVE_SPRINTS) -> tuple[list[dict], str | None]:
    ordered = sorted(refs, key=lambda item: (str(item.get("start_date") or ""), str(item.get("name") or "")))
    seen: set[str] = set()
    unique: list[dict] = []
    for item in ordered:
        key = str(item.get("sprint_key") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    if len(unique) <= limit:
        return unique, None
    kept = unique[-limit:]
    note = (
        f"O período tem {len(unique)} Sprints; a análise com IA usa as {limit} mais recentes "
        "para caber no modelo."
    )
    return kept, note

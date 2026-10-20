from __future__ import annotations

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from app.services.azure_devops import AzureDevOpsService
from app.services.project_tracking.catalog import ProjectScope
from app.services.project_tracking.facade import (
    build_evolution,
    build_overview,
    build_sprints_list,
)
from app.services.project_tracking.story_consolidation import (
    INDICATOR_CRITERIA,
    consolidate_appearances,
    consolidate_by_team,
)

ReportType = Literal["monthly", "sprints", "evolution", "consolidated"]

_MONTHS_PT = (
    "",
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)

_STATUS_PT = {
    "planned": "planejada",
    "active": "em andamento",
    "closed": "encerrada",
}


def _period_label(year: int, month: int | None) -> str:
    if month is None or month == 0:
        return f"ano de {year}"
    if 1 <= month <= 12:
        return f"{_MONTHS_PT[month]} de {year}"
    return f"{year}"


def _pct(value: float | None) -> str:
    if value is None:
        return "n/d"
    return f"{value:.1f}%"


def _section(heading: str, body: str | None = None, bullets: list[str] | None = None) -> dict:
    return {"heading": heading, "body": body, "bullets": bullets or []}


def _render_sections(sections: list[dict], *, title: str, meta_lines: list[str]) -> str:
    lines = [title, *meta_lines, ""]
    for block in sections:
        lines.append(block["heading"])
        if block.get("body"):
            lines.append(block["body"])
            lines.append("")
        for bullet in block.get("bullets") or []:
            lines.append(f"• {bullet}")
        lines.append("")
    return "\n".join(line for line in lines).strip() + "\n"


def _criteria_section() -> dict:
    return _section(
        "Critérios de cálculo",
        body=(
            "Os totais do período contam cada história uma vez. "
            "As linhas de cada Sprint descrevem somente aquela Sprint e podem repetir a mesma história."
        ),
        bullets=[f"{item['label']}: {item['description']}" for item in INDICATOR_CRITERIA],
    )


def _unique_bullets(unique: dict[str, int]) -> list[str]:
    return [
        f"Histórias no período, sem repetir entre Sprints: {unique['stories_total']}",
        f"Histórias criadas: {unique['stories_created']}",
        f"Histórias concluídas: {unique['stories_completed']}",
        f"Em andamento: {unique['stories_in_progress']}",
        f"Pendentes: {unique['stories_pending']}",
        f"Estado concluído sem transição no intervalo das Sprints do recorte: {unique['stories_already_done']}",
        f"Após início da Sprint: {unique['stories_added_after_start']}",
        f"Impedimentos explícitos nas histórias do período: {unique['impediments_identified']}",
    ]


def _report_title(report_type: ReportType) -> str:
    return {
        "monthly": "Relatório executivo — visão do mês",
        "sprints": "Relatório executivo — Sprints do período",
        "evolution": "Relatório executivo — evolução do projeto",
        "consolidated": "Relatório executivo — visão consolidada",
    }[report_type]


def build_project_report(
    service: AzureDevOpsService,
    *,
    report_type: ReportType,
    year: int,
    month: int,
    scope: ProjectScope | None,
    all_scopes: list[ProjectScope],
) -> dict:
    generated_at = datetime.now(ZoneInfo("America/Cuiaba")).isoformat(timespec="seconds")
    period = _period_label(year, month if month else None)
    scope_label = scope.label if scope else "Todos os projetos acompanhados"
    limitations: list[str] = []
    sections: list[dict] = []

    if report_type == "consolidated":
        if scope is not None:
            raise ValueError("Relatório consolidado exige visão sem filtro de área.")
        if month < 1:
            raise ValueError("Informe o mês para o relatório consolidado.")
        overview = build_overview(
            service,
            year=year,
            month=month,
            scope=None,
            all_scopes=all_scopes,
            include_appearances=True,
        )
        limitations.extend(overview["limitations"])
        ind = overview["indicators"]
        unique = consolidate_appearances(overview.get("appearances") or [])
        by_team = consolidate_by_team(overview.get("appearances") or [])
        sections.append(
            _section(
                "Resumo",
                f"No período de {period}, foram acompanhados {ind['projects_tracked']} escopos "
                f"de projeto no Azure DevOps, com {ind['sprints_in_period']} Sprint(s) cruzando o mês. "
                f"Os indicadores reúnem as histórias uma única vez, ainda que a mesma história "
                f"tenha passado por mais de uma Sprint.",
            )
        )
        sections.append(_section("Indicadores consolidados", bullets=_unique_bullets(unique)))
        card_lines = []
        for card in overview["project_cards"]:
            stats = by_team.get(card["team_project"]) or consolidate_appearances([])
            card_lines.append(
                f"{card['label']}: {card['sprints']} Sprint(s); "
                f"{stats['stories_completed']} concluída(s) e {stats['stories_pending']} pendente(s), "
                f"sem repetir a mesma história."
            )
        if card_lines:
            sections.append(_section("Por projeto Azure (nível time)", bullets=card_lines))

    elif report_type == "monthly":
        if month < 1:
            raise ValueError("Informe o mês para o relatório mensal.")
        overview = build_overview(
            service,
            year=year,
            month=month,
            scope=scope,
            all_scopes=all_scopes,
            include_appearances=True,
        )
        limitations.extend(overview["limitations"])
        ind = overview["indicators"]
        unique = consolidate_appearances(overview.get("appearances") or [])
        sections.append(
            _section(
                "Resumo",
                f"Escopo: {scope_label}. Período: {period}. "
                f"{ind['sprints_in_period']} Sprint(s) no recorte; "
                f"{unique['stories_completed']} história(s) concluída(s) e "
                f"{unique['stories_pending']} pendente(s), contadas uma vez no período.",
            )
        )
        sections.append(_section("Indicadores", bullets=_unique_bullets(unique)))

    elif report_type == "sprints":
        if scope is None:
            raise ValueError("Selecione um projeto/área para o relatório de Sprints.")
        if month < 1:
            raise ValueError("Informe o mês para o relatório de Sprints.")
        payload = build_sprints_list(
            service,
            year=year,
            month=month,
            scope=scope,
            include_appearances=True,
        )
        limitations.extend(payload["limitations"])
        rows = payload["rows"]
        unique = consolidate_appearances(payload.get("appearances") or [])
        sections.append(
            _section(
                "Resumo",
                f"Escopo: {scope_label}. Período: {period}. "
                f"{len(rows)} Sprint(s) com histórias no filtro aplicado. "
                f"Cada linha abaixo é o recorte daquela Sprint. "
                f"O total do período conta {unique['stories_total']} história(s) distinta(s).",
            )
        )
        sprint_bullets = []
        for row in rows:
            status = _STATUS_PT.get(row["status"], row["status"])
            sprint_bullets.append(
                f"{row['name']} ({row['start_date']} a {row['finish_date']}, {status}): "
                f"{row['stories_completed_in_sprint']}/{row['stories_total']} concluídas "
                f"({_pct(row.get('completion_percent'))}); {row['stories_pending']} pendente(s)."
            )
        sections.append(
            _section(
                "Sprints",
                body="Métricas com base em revisões de histórias (User Stories) no Azure DevOps."
                if not sprint_bullets
                else None,
                bullets=sprint_bullets or ["Nenhuma Sprint com histórias neste mês para o escopo."],
            )
        )
        sections.append(_section("Totais do período", bullets=_unique_bullets(unique)))

    elif report_type == "evolution":
        if scope is None:
            raise ValueError("Selecione um projeto/área para o relatório de evolução.")
        normalized_month = None if month == 0 else month
        payload = build_evolution(
            service,
            year=year,
            month=normalized_month,
            scope=scope,
            include_appearances=True,
        )
        limitations.extend(payload["limitations"])
        timeline = payload["timeline"]
        unique = consolidate_appearances(payload.get("appearances") or [])
        sections.append(
            _section(
                "Resumo",
                f"Escopo: {scope_label}. Período: {period}. "
                f"Linha do tempo com {len(timeline)} Sprint(s). "
                f"No período, sem repetir a mesma história: "
                f"{unique['stories_completed']} concluída(s), "
                f"{unique['stories_pending']} pendente(s) e "
                f"{unique['impediments_identified']} com impedimento explícito. "
                f"Cada item da linha do tempo mantém o recorte da própria Sprint.",
            )
        )
        evo_bullets = []
        for entry in timeline:
            status = _STATUS_PT.get(entry["status"], entry["status"])
            m = entry["metrics"]
            evo_bullets.append(
                f"{entry['name']} ({status}): {m['stories_completed_in_sprint']} concluída(s), "
                f"{m['stories_pending']} pendente(s), conclusão {_pct(m.get('completion_percent'))}."
            )
            if entry["completed_stories"]:
                titles = ", ".join(f"#{s['work_item_id']}" for s in entry["completed_stories"][:5])
                extra = "…" if len(entry["completed_stories"]) > 5 else ""
                evo_bullets.append(f"  Entregas destacadas: {titles}{extra}")
        sections.append(
            _section(
                "Linha do tempo",
                bullets=evo_bullets or ["Nenhuma Sprint com histórias no período."],
            )
        )
    else:
        raise ValueError("Tipo de relatório inválido.")

    sections.append(_criteria_section())

    title = _report_title(report_type)
    meta = [
        f"Gerado em: {generated_at} (America/Cuiaba)",
        f"Fonte: Azure DevOps (dados reais, sem simulação)",
        f"Escopo: {scope_label}",
        f"Período: {period}",
    ]
    full_text = _render_sections(sections, title=title, meta_lines=meta)

    return {
        "report_type": report_type,
        "title": title,
        "year": year,
        "month": month if month else None,
        "scope_key": scope.key if scope else None,
        "scope_label": scope_label,
        "generated_at": generated_at,
        "sections": sections,
        "full_text": full_text,
        "limitations": sorted(set(limitations))[:20],
        "data_source": "azure_devops",
        "indicator_criteria": INDICATOR_CRITERIA,
    }

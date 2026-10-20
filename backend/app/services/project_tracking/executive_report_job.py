from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import ExecutiveReport
from app.services.ai.errors import AiError
from app.services.ai.service import AiService
from app.services.azure_devops_config import build_service
from app.services.azure_devops_errors import AzureDevOpsError
from app.services.project_tracking.catalog import resolve_scope
from app.services.project_tracking.facade import load_scopes
from app.services.project_tracking.sprint_ai_collect import collect_sprints
from app.services.project_tracking.sprint_ai_pack import build_analysis_pack
from app.services.project_tracking.sprint_ai_schema import (
    SprintAiNarrative,
    executive_system_instruction,
    narrative_user_content,
    sanitize_narrative,
)
from app.services.project_tracking.sprint_analytics import decode_sprint_key


def pick_saved_report(rows: list[ExecutiveReport]) -> ExecutiveReport | None:
    """Prefere uma geração em andamento; senão, o sucesso mais recente."""
    for row in rows:
        if row.status in {"pending", "running"}:
            return row
    for row in rows:
        if row.status == "success":
            return row
    return None


def same_sprint_selection(stored: list | None, requested: list[str]) -> bool:
    return sorted(str(item) for item in (stored or [])) == sorted(requested)


def latest_saved_report(
    db,
    *,
    report_type: str,
    year: int,
    month: int,
    scope_key: str | None,
    sprint_keys: list[str] | None = None,
) -> ExecutiveReport | None:
    query = db.query(ExecutiveReport).filter(
        ExecutiveReport.report_type == report_type,
        ExecutiveReport.year == year,
        ExecutiveReport.month == month,
    )
    if scope_key:
        query = query.filter(ExecutiveReport.scope_key == scope_key)
    else:
        query = query.filter(ExecutiveReport.scope_key.is_(None))
    rows = query.order_by(ExecutiveReport.id.desc()).limit(30).all()
    if sprint_keys is not None:
        rows = [row for row in rows if same_sprint_selection(row.sprint_keys, sprint_keys)]
    return pick_saved_report(rows)


def _sanitize_error(message: str) -> str:
    text = " ".join(message.split())
    lowered = text.lower()
    if "api key" in lowered or "api_key" in lowered:
        return "Falha na integração de IA."
    if len(text) > 480:
        return text[:477] + "..."
    return text or "Não foi possível gerar o relatório."


def run_executive_report(report_id: int) -> None:
    db = SessionLocal()
    try:
        report = db.get(ExecutiveReport, report_id)
        if report is None:
            return
        report.status = "running"
        db.commit()
        try:
            service = build_service(db)
            scopes = load_scopes(db, service)
            targets = []
            for key in list(report.scope_keys or []):
                scope = resolve_scope(scopes, team_project=None, area_path=None, scope_key=key)
                if scope is None:
                    raise ValueError("Escopo de projeto não encontrado.")
                targets.append(scope)
            if not targets:
                raise ValueError("Nenhum projeto selecionado para o relatório.")

            by_project = {item.team_project: item for item in targets}
            grouped: dict[str, list[str]] = defaultdict(list)
            for sprint_key in list(report.sprint_keys or []):
                project, _path = decode_sprint_key(str(sprint_key))
                grouped[project].append(str(sprint_key))

            rows: list[dict] = []
            limitations = [str(item) for item in (report.notes or [])]
            if len(targets) == 1:
                part, notes = collect_sprints(service, list(report.sprint_keys or []), targets[0])
                rows.extend(part)
                limitations.extend(notes)
            else:
                for project, keys in grouped.items():
                    scope = by_project.get(project)
                    if scope is None:
                        raise ValueError("Há Sprint fora dos projetos do relatório.")
                    part, notes = collect_sprints(service, keys, scope)
                    rows.extend(part)
                    limitations.extend(notes)

            pack = build_analysis_pack(rows, scope_label=report.scope_label, limitations=limitations)
            stories_total = int((pack.get("consolidated") or {}).get("stories_total") or 0)
            if stories_total <= 0:
                raise ValueError("Não há histórias para analisar nas Sprints do período.")

            ai = AiService(db)
            execution = ai.generate_structured(
                module="project_tracking_executive_report",
                user_content=narrative_user_content(pack, report_type=report.report_type),
                schema_model=SprintAiNarrative,
                system_instruction=executive_system_instruction(report.report_type),
                temperature=0.2,
                max_output_tokens=8192,
            )
            parsed = execution.parsed
            if not isinstance(parsed, SprintAiNarrative):
                raise ValueError("Resposta da IA fora do formato esperado.")
            result = sanitize_narrative(parsed, pack)
            report = db.get(ExecutiveReport, report_id)
            if report is None:
                return
            report.pack = pack
            report.result = result
            report.evidence = pack.get("evidence_index")
            report.stories_count = stories_total
            report.tasks_count = int((pack.get("consolidated") or {}).get("tasks_total") or 0)
            report.model = execution.model
            report.status = "success"
            report.generated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            report.error_message = None
            db.commit()
        except (AiError, AzureDevOpsError, ValueError) as exc:
            db.rollback()
            report = db.get(ExecutiveReport, report_id)
            if report is None:
                return
            report.status = "error"
            report.error_message = _sanitize_error(str(exc))
            db.commit()
        except Exception as exc:
            db.rollback()
            report = db.get(ExecutiveReport, report_id)
            if report is None:
                return
            report.status = "error"
            report.error_message = _sanitize_error(str(exc))
            db.commit()
    finally:
        db.close()

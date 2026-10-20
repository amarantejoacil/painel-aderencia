from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import SprintAiReport
from app.services.ai.errors import AiError
from app.services.ai.service import AiService
from app.services.azure_devops_config import build_service
from app.services.azure_devops_errors import AzureDevOpsError
from app.services.project_tracking.catalog import resolve_scope
from app.services.project_tracking.facade import load_scopes
from app.services.project_tracking.sprint_ai_collect import collect_sprints
from app.services.project_tracking.sprint_ai_pack import build_analysis_pack
from app.services.project_tracking.sprint_ai_schema import (
    SYSTEM_INSTRUCTION,
    SprintAiNarrative,
    narrative_user_content,
    sanitize_narrative,
)


def sprint_fingerprint(scope_key: str, sprint_keys: list[str]) -> str:
    raw = scope_key + "\n" + "\n".join(sorted(sprint_keys))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sanitize_error(message: str) -> str:
    text = " ".join(message.split())
    lowered = text.lower()
    if "api key" in lowered or "api_key" in lowered:
        return "Falha na integração de IA."
    if len(text) > 480:
        return text[:477] + "..."
    return text or "Não foi possível gerar a análise."


def run_sprint_analysis(report_id: int) -> None:
    db = SessionLocal()
    try:
        report = db.get(SprintAiReport, report_id)
        if report is None:
            return
        report.status = "running"
        db.commit()
        try:
            service = build_service(db)
            scopes = load_scopes(db, service)
            scope = resolve_scope(scopes, team_project=None, area_path=None, scope_key=report.scope_key)
            if scope is None:
                raise ValueError("Escopo de projeto não encontrado.")
            sprints, limitations = collect_sprints(service, list(report.sprint_keys), scope)
            pack = build_analysis_pack(sprints, scope_label=scope.label, limitations=limitations)
            ai = AiService(db)
            execution = ai.generate_structured(
                module="project_tracking_sprint_analysis",
                user_content=narrative_user_content(pack),
                schema_model=SprintAiNarrative,
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2,
                max_output_tokens=8192,
            )
            parsed = execution.parsed
            if not isinstance(parsed, SprintAiNarrative):
                raise ValueError("Resposta da IA fora do formato esperado.")
            result = sanitize_narrative(parsed, pack)
            report = db.get(SprintAiReport, report_id)
            if report is None:
                return
            report.pack = pack
            report.result = result
            report.evidence = pack.get("evidence_index")
            report.stories_count = int((pack.get("consolidated") or {}).get("stories_total") or 0)
            report.tasks_count = int((pack.get("consolidated") or {}).get("tasks_total") or 0)
            report.model = execution.model
            report.status = "success"
            report.generated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            report.error_message = None
            db.commit()
        except (AiError, AzureDevOpsError, ValueError) as exc:
            db.rollback()
            report = db.get(SprintAiReport, report_id)
            if report is None:
                return
            report.status = "error"
            report.error_message = _sanitize_error(str(exc))
            db.commit()
        except Exception as exc:
            db.rollback()
            report = db.get(SprintAiReport, report_id)
            if report is None:
                return
            report.status = "error"
            report.error_message = _sanitize_error(str(exc))
            db.commit()
    finally:
        db.close()


def latest_success(db: Session, scope_key: str, sprint_keys: list[str]) -> SprintAiReport | None:
    fingerprint = sprint_fingerprint(scope_key, sprint_keys)
    return (
        db.query(SprintAiReport)
        .filter(SprintAiReport.fingerprint == fingerprint, SprintAiReport.status == "success")
        .order_by(SprintAiReport.id.desc())
        .first()
    )


def latest_by_fingerprint(db: Session, scope_key: str, sprint_keys: list[str]) -> SprintAiReport | None:
    fingerprint = sprint_fingerprint(scope_key, sprint_keys)
    return (
        db.query(SprintAiReport)
        .filter(SprintAiReport.fingerprint == fingerprint)
        .order_by(SprintAiReport.id.desc())
        .first()
    )

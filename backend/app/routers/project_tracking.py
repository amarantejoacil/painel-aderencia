from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ExecutiveReport, SprintAiReport
from app.schemas import (
    ExecutiveReportCreate,
    ExecutiveReportLatestOut,
    ExecutiveReportOut,
    ProjectEvolutionOut,
    ProjectOverviewOut,
    ProjectReportOut,
    ProjectScopeOut,
    ProjectSprintDetailOut,
    ProjectSprintsOut,
    SprintRefOut,
    SprintAnalysisCreate,
    SprintAnalysisLatestOut,
    SprintAnalysisOut,
)
from app.services.azure_devops_config import build_service, is_configured
from app.services.azure_devops_errors import AzureDevOpsConfigError, AzureDevOpsError
from app.services.project_tracking.catalog import resolve_scope
from app.services.project_tracking.facade import (
    build_evolution,
    build_overview,
    build_sprint_detail,
    build_sprints_list,
    list_sprint_refs,
    load_scopes,
)
from app.services.project_tracking.executive_report_job import latest_saved_report, run_executive_report
from app.services.project_tracking.executive_targets import (
    scope_label_for,
    target_scopes,
    trim_sprint_refs,
    validate_period,
)
from app.services.project_tracking.reports import build_project_report
from app.services.project_tracking.sprint_ai_job import (
    latest_by_fingerprint,
    run_sprint_analysis,
    sprint_fingerprint,
)

router = APIRouter(prefix="/projects", tags=["projects"])

GENERIC_MESSAGE = "Não foi possível consultar o Azure DevOps."


def _service_or_error(db: Session):
    try:
        return build_service(db)
    except AzureDevOpsConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/scopes", response_model=list[ProjectScopeOut])
def list_scopes(db: Session = Depends(get_db)) -> list[ProjectScopeOut]:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        service = _service_or_error(db)
        scopes = load_scopes(db, service)
        return [
            ProjectScopeOut(
                key=item.key,
                label=item.label,
                team_project=item.team_project,
                area_path=item.area_path,
            )
            for item in scopes
        ]
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc


@router.get("/overview", response_model=ProjectOverviewOut)
def get_overview(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    scope_key: str | None = None,
    db: Session = Depends(get_db),
) -> ProjectOverviewOut:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        service = _service_or_error(db)
        scopes = load_scopes(db, service)
        scope = resolve_scope(scopes, team_project=None, area_path=None, scope_key=scope_key)
        payload = build_overview(service, year=year, month=month, scope=scope, all_scopes=scopes)
        return ProjectOverviewOut.model_validate(payload)
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc


@router.get("/sprints", response_model=ProjectSprintsOut)
def list_sprints(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    scope_key: str = Query(min_length=3),
    db: Session = Depends(get_db),
) -> ProjectSprintsOut:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        service = _service_or_error(db)
        scopes = load_scopes(db, service)
        scope = resolve_scope(scopes, team_project=None, area_path=None, scope_key=scope_key)
        if scope is None:
            raise HTTPException(status_code=404, detail="Escopo de projeto não encontrado.")
        payload = build_sprints_list(service, year=year, month=month, scope=scope)
        return ProjectSprintsOut.model_validate(payload)
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc


@router.get("/sprint-refs", response_model=list[SprintRefOut])
def list_sprint_refs_route(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    scope_key: str = Query(min_length=3),
    db: Session = Depends(get_db),
) -> list[SprintRefOut]:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        service = _service_or_error(db)
        scopes = load_scopes(db, service)
        scope = resolve_scope(scopes, team_project=None, area_path=None, scope_key=scope_key)
        if scope is None:
            raise HTTPException(status_code=404, detail="Escopo de projeto não encontrado.")
        refs = list_sprint_refs(service, year=year, month=month, scope=scope)
        return [
            SprintRefOut(
                sprint_key=str(item["sprint_key"]),
                name=str(item["name"]),
                start_date=str(item["start_date"]),
                finish_date=str(item["finish_date"]),
                status=str(item["status"]),
            )
            for item in refs
        ]
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc


ReportType = Literal["monthly", "sprints", "evolution", "consolidated"]


def _report_payload(
    db: Session,
    *,
    report_type: ReportType,
    year: int,
    month: int,
    scope_key: str | None,
) -> dict:
    service = _service_or_error(db)
    scopes = load_scopes(db, service)
    scope = resolve_scope(scopes, team_project=None, area_path=None, scope_key=scope_key or None)
    if report_type == "consolidated":
        if scope_key:
            raise HTTPException(
                status_code=400,
                detail="Relatório consolidado não usa filtro de projeto/área.",
            )
        scope = None
    elif report_type in {"sprints", "evolution"} and scope is None:
        raise HTTPException(status_code=400, detail="Selecione um projeto/área para este relatório.")
    try:
        return build_project_report(
            service,
            report_type=report_type,
            year=year,
            month=month,
            scope=scope,
            all_scopes=scopes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reports", response_model=ProjectReportOut)
def get_project_report(
    report_type: ReportType = Query(...),
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=0, le=12),
    scope_key: str | None = None,
    db: Session = Depends(get_db),
) -> ProjectReportOut:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        payload = _report_payload(
            db,
            report_type=report_type,
            year=year,
            month=month,
            scope_key=scope_key,
        )
        return ProjectReportOut.model_validate(payload)
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc


@router.get("/reports/export")
def export_project_report(
    report_type: ReportType = Query(...),
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=0, le=12),
    scope_key: str | None = None,
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        payload = _report_payload(
            db,
            report_type=report_type,
            year=year,
            month=month,
            scope_key=scope_key,
        )
        filename = f"relatorio-projetos-{report_type}-{year}-{month:02d}.txt"
        return PlainTextResponse(
            content=payload["full_text"],
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc


@router.get("/evolution", response_model=ProjectEvolutionOut)
def get_evolution(
    year: int = Query(ge=2000, le=2100),
    scope_key: str = Query(min_length=3),
    month: int | None = Query(default=None, ge=0, le=12),
    db: Session = Depends(get_db),
) -> ProjectEvolutionOut:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        service = _service_or_error(db)
        scopes = load_scopes(db, service)
        scope = resolve_scope(scopes, team_project=None, area_path=None, scope_key=scope_key)
        if scope is None:
            raise HTTPException(status_code=404, detail="Escopo de projeto não encontrado.")
        normalized_month = None if month in (None, 0) else month
        payload = build_evolution(service, year=year, month=normalized_month, scope=scope)
        return ProjectEvolutionOut.model_validate(payload)
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc


def _analysis_out(row: SprintAiReport) -> SprintAnalysisOut:
    generated = row.generated_at.isoformat() if row.generated_at else None
    return SprintAnalysisOut(
        id=row.id,
        status=row.status,
        scope_key=row.scope_key,
        scope_label=row.scope_label,
        team_project=row.team_project,
        area_path=row.area_path,
        year=row.year,
        month=row.month,
        sprint_keys=list(row.sprint_keys or []),
        model=row.model,
        stories_count=row.stories_count,
        tasks_count=row.tasks_count,
        generated_at=generated,
        error_message=row.error_message,
        pack=row.pack,
        result=row.result,
        evidence=row.evidence,
    )


@router.get("/sprint-analyses/latest", response_model=SprintAnalysisLatestOut)
def get_latest_sprint_analysis(
    scope_key: str = Query(min_length=3),
    sprint_keys: list[str] = Query(min_length=1),
    db: Session = Depends(get_db),
) -> SprintAnalysisLatestOut:
    row = latest_by_fingerprint(db, scope_key, sprint_keys)
    if row is None:
        return SprintAnalysisLatestOut()
    generated = row.generated_at.isoformat() if row.generated_at else None
    return SprintAnalysisLatestOut(report_id=row.id, status=row.status, generated_at=generated)


@router.post("/sprint-analyses", response_model=SprintAnalysisOut)
def create_sprint_analysis(
    payload: SprintAnalysisCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SprintAnalysisOut:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    from app.services.gemini_config import is_enabled_for_use

    if not is_enabled_for_use(db):
        raise HTTPException(status_code=503, detail="Integração de IA desabilitada ou não configurada.")
    try:
        service = _service_or_error(db)
        scopes = load_scopes(db, service)
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc
    scope = resolve_scope(scopes, team_project=None, area_path=None, scope_key=payload.scope_key)
    if scope is None:
        raise HTTPException(status_code=404, detail="Escopo de projeto não encontrado.")
    keys = list(dict.fromkeys(payload.sprint_keys))
    row = SprintAiReport(
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        fingerprint=sprint_fingerprint(scope.key, keys),
        scope_key=scope.key,
        scope_label=scope.label,
        team_project=scope.team_project,
        area_path=scope.area_path,
        year=payload.year,
        month=payload.month,
        sprint_keys=keys,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    background.add_task(run_sprint_analysis, row.id)
    return _analysis_out(row)


@router.get("/sprint-analyses/{report_id}", response_model=SprintAnalysisOut)
def get_sprint_analysis(report_id: int, db: Session = Depends(get_db)) -> SprintAnalysisOut:
    row = db.get(SprintAiReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada.")
    return _analysis_out(row)


@router.get("/sprints/{sprint_key}", response_model=ProjectSprintDetailOut)
def get_sprint_detail(
    sprint_key: str,
    area_path: str | None = None,
    db: Session = Depends(get_db),
) -> ProjectSprintDetailOut:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        service = _service_or_error(db)
        payload = build_sprint_detail(service, sprint_key, area_path=area_path)
        return ProjectSprintDetailOut.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc


def _executive_out(row: ExecutiveReport) -> ExecutiveReportOut:
    generated = row.generated_at.isoformat() if row.generated_at else None
    return ExecutiveReportOut(
        id=row.id,
        status=row.status,
        report_type=row.report_type,
        scope_key=row.scope_key,
        scope_keys=list(row.scope_keys or []),
        scope_label=row.scope_label,
        team_project=row.team_project,
        area_path=row.area_path,
        year=row.year,
        month=row.month,
        sprint_keys=list(row.sprint_keys or []),
        model=row.model,
        stories_count=row.stories_count,
        tasks_count=row.tasks_count,
        generated_at=generated,
        error_message=row.error_message,
        pack=row.pack,
        result=row.result,
        evidence=row.evidence,
    )


@router.post("/executive-reports", response_model=ExecutiveReportOut)
def create_executive_report(
    payload: ExecutiveReportCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ExecutiveReportOut:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    from app.services.gemini_config import is_enabled_for_use

    if not is_enabled_for_use(db):
        raise HTTPException(status_code=503, detail="Integração de IA desabilitada ou não configurada.")
    if payload.sprint_keys and payload.report_type != "sprints":
        raise HTTPException(
            status_code=400,
            detail="A seleção de Sprints vale apenas para o relatório de Sprint.",
        )
    if payload.report_type == "sprints" and not payload.sprint_keys:
        raise HTTPException(status_code=400, detail="Selecione ao menos uma Sprint.")
    try:
        validate_period(payload.report_type, payload.month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        service = _service_or_error(db)
        scopes = load_scopes(db, service)
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc

    scope = None
    if payload.report_type != "consolidated":
        if not payload.scope_key:
            raise HTTPException(status_code=400, detail="Selecione um projeto/área para este relatório.")
        scope = resolve_scope(scopes, team_project=None, area_path=None, scope_key=payload.scope_key)
        if scope is None:
            raise HTTPException(status_code=404, detail="Escopo de projeto não encontrado.")
    try:
        targets = target_scopes(payload.report_type, scope, scopes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    notes: list[str] = []
    if payload.sprint_keys:
        from app.services.project_tracking.sprint_analytics import decode_sprint_key

        sprint_keys = list(dict.fromkeys(payload.sprint_keys))
        project = targets[0].team_project
        for key in sprint_keys:
            try:
                decoded_project, _path = decode_sprint_key(key)
            except (ValueError, UnicodeError):
                raise HTTPException(status_code=400, detail="Sprint inválida.") from None
            if decoded_project != project:
                raise HTTPException(status_code=400, detail="A Sprint não pertence ao projeto selecionado.")
    else:
        try:
            refs: list[dict] = []
            for target in targets:
                refs.extend(list_sprint_refs(service, year=payload.year, month=payload.month, scope=target))
        except AzureDevOpsError as exc:
            raise HTTPException(status_code=502, detail=GENERIC_MESSAGE) from exc
        kept, note = trim_sprint_refs(refs)
        if note:
            notes.append(note)
        sprint_keys = [str(item["sprint_key"]) for item in kept]
    if not sprint_keys:
        raise HTTPException(status_code=400, detail="Nenhuma Sprint com datas no período selecionado.")

    row = ExecutiveReport(
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        report_type=payload.report_type,
        scope_key=scope.key if scope else None,
        scope_keys=[item.key for item in targets],
        scope_label=scope_label_for(targets),
        team_project=targets[0].team_project if len(targets) == 1 else "Vários projetos",
        area_path=targets[0].area_path if len(targets) == 1 else None,
        year=payload.year,
        month=payload.month,
        sprint_keys=sprint_keys,
        notes=notes,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    background.add_task(run_executive_report, row.id)
    return _executive_out(row)


@router.get("/executive-reports/latest", response_model=ExecutiveReportLatestOut)
def get_latest_executive_report(
    report_type: ReportType = Query(...),
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=0, le=12),
    scope_key: str | None = None,
    sprint_keys: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
) -> ExecutiveReportLatestOut:
    if report_type == "consolidated":
        scope_key = None
    elif not scope_key:
        raise HTTPException(status_code=400, detail="Selecione um projeto/área para este relatório.")
    selected = list(dict.fromkeys(sprint_keys)) if report_type == "sprints" and sprint_keys else None
    row = latest_saved_report(
        db,
        report_type=report_type,
        year=year,
        month=month,
        scope_key=scope_key,
        sprint_keys=selected,
    )
    return ExecutiveReportLatestOut(report=_executive_out(row) if row else None)


@router.get("/executive-reports/{report_id}", response_model=ExecutiveReportOut)
def get_executive_report(report_id: int, db: Session = Depends(get_db)) -> ExecutiveReportOut:
    row = db.get(ExecutiveReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    return _executive_out(row)

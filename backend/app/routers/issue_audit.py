from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IssueAuditQuery, IssueAuditValidation
from app.services.azure_devops_config import get_settings_row
from app.services.azure_devops_errors import (
    AzureDevOpsAuthError,
    AzureDevOpsConfigError,
    AzureDevOpsConnectionError,
    AzureDevOpsError,
)
from app.services.issue_audit.comment_storage import comment_storage_report, full_comments_exportable
from app.services.issue_audit.excel_export import build_audit_workbook
from app.services.issue_audit.jobs import (
    create_query,
    list_collection_projects,
    lookup_people,
    request_cancel,
    request_backfill_all_comments,
    retry_failed,
    select_identity,
)
from app.services.issue_audit.profiles import AUDIT_PROFILES, get_profile
from app.services.issue_audit.validation import (
    extraction_diagnosis,
    get_latest_validation,
    run_validation,
    save_manual_review,
)

router = APIRouter(prefix="/audit/issues", tags=["issue-audit"])


class IssueAuditCreate(BaseModel):
    organization: str = Field(min_length=1, max_length=200)
    project: str = Field(min_length=1, max_length=300)
    work_item_type: str = Field(default="Issue", min_length=1, max_length=100)
    period_criterion: str = Field(pattern="^(created|changed)$")
    year: int = Field(ge=2000, le=2100)
    comment_scope: str = Field(pattern="^(all|period)$")
    person_name: str = Field(min_length=1, max_length=300)
    person_identity_id: str | None = Field(default=None, max_length=100)
    person_unique_name: str | None = Field(default=None, max_length=300)
    requester: str | None = Field(default=None, max_length=200)
    profile_id: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=200)
    period_start: date | None = None
    period_end: date | None = None


class IssueAuditIdentity(BaseModel):
    identity_id: str | None = None
    unique_name: str | None = None
    display_name: str | None = None


class IssueAuditSummary(BaseModel):
    id: int
    created_at: datetime
    finished_at: datetime | None
    requester: str | None
    organization: str
    project: str
    work_item_type: str
    period_criterion: str
    year: int
    comment_scope: str
    person_name: str
    person_identity_id: str | None
    person_unique_name: str | None
    profile_id: str | None = None
    state_filter: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    status: str
    issues_found: int
    issues_processed: int
    comments_analyzed: int
    comments_matched: int
    failure_count: int
    progress_percent: int
    error_message: str | None
    limitations: list[str]


class IssueAuditDetail(IssueAuditSummary):
    failed_ids: list[int]
    result: dict | None


class IssueAuditValidationOut(BaseModel):
    id: int
    query_id: int
    created_at: datetime
    updated_at: datetime | None
    payload: dict


class IssueAuditManualReviewIn(BaseModel):
    issue_id: int
    status: str = Field(pattern="^(confere|divergencia|nao_verificado)$")
    real_comment_count: int | None = None
    real_person_comment_count: int | None = None
    divergence_type: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    reviewer: str | None = Field(default=None, max_length=200)


def _summary(row: IssueAuditQuery) -> IssueAuditSummary:
    return IssueAuditSummary(
        id=row.id,
        created_at=row.created_at,
        finished_at=row.finished_at,
        requester=row.requester,
        organization=row.organization,
        project=row.project,
        work_item_type=row.work_item_type,
        period_criterion=row.period_criterion,
        year=row.year,
        comment_scope=row.comment_scope,
        person_name=row.person_name,
        person_identity_id=row.person_identity_id,
        person_unique_name=row.person_unique_name,
        profile_id=row.profile_id,
        state_filter=row.state_filter,
        period_start=row.period_start,
        period_end=row.period_end,
        status=row.status,
        issues_found=row.issues_found,
        issues_processed=row.issues_processed,
        comments_analyzed=row.comments_analyzed,
        comments_matched=row.comments_matched,
        failure_count=row.failure_count,
        progress_percent=row.progress_percent,
        error_message=row.error_message,
        limitations=list(row.limitations or []),
    )


def _detail(row: IssueAuditQuery) -> IssueAuditDetail:
    return IssueAuditDetail(**_summary(row).model_dump(), failed_ids=list(row.failed_ids or []), result=row.result)


def _http(exc: AzureDevOpsError) -> HTTPException:
    if isinstance(exc, AzureDevOpsAuthError):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, AzureDevOpsConfigError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, AzureDevOpsConnectionError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=502, detail="Não foi possível consultar o Azure DevOps.")


@router.get("/profiles")
def get_audit_profiles() -> list[dict]:
    return [profile.as_dict() for profile in AUDIT_PROFILES]


@router.get("/states", response_model=list[str])
def get_states(
    organization: str = Query(min_length=1),
    project: str = Query(min_length=1),
    work_item_type: str = Query(default="Issue", min_length=1),
    db: Session = Depends(get_db),
) -> list[str]:
    from app.services.issue_audit.jobs import _client

    client = _client(db, organization)
    try:
        return client.list_work_item_states(project, work_item_type)
    except AzureDevOpsError as exc:
        raise _http(exc) from exc
    finally:
        client.close()


@router.get("/projects", response_model=list[str])
def get_projects(organization: str = Query(min_length=1), db: Session = Depends(get_db)) -> list[str]:
    try:
        return list_collection_projects(db, organization)
    except AzureDevOpsError as exc:
        raise _http(exc) from exc


@router.get("/people")
def get_people(
    organization: str = Query(min_length=1),
    name: str = Query(min_length=2),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return lookup_people(db, organization=organization, name=name)
    except AzureDevOpsError as exc:
        raise _http(exc) from exc


@router.get("/queries", response_model=list[IssueAuditSummary])
def list_queries(db: Session = Depends(get_db)) -> list[IssueAuditSummary]:
    rows = db.scalars(select(IssueAuditQuery).order_by(IssueAuditQuery.created_at.desc()).limit(100)).all()
    return [_summary(row) for row in rows]


@router.post("/queries", response_model=IssueAuditSummary)
def post_query(payload: IssueAuditCreate, db: Session = Depends(get_db)) -> IssueAuditSummary:
    try:
        organization = payload.organization.strip()
        project = payload.project.strip()
        work_item_type = payload.work_item_type.strip()
        profile = get_profile(payload.profile_id)
        if payload.profile_id and profile is None:
            raise AzureDevOpsConfigError("Perfil de auditoria desconhecido.")
        if profile is not None:
            organization = profile.organization
            project = profile.project
            work_item_type = profile.work_item_type
        state = (payload.state or "").strip() or None
        if profile is None or profile.comment_strategy != "comments_api":
            state = None
        if (payload.period_start is None) != (payload.period_end is None):
            raise AzureDevOpsConfigError("Informe a data inicial e a data final do período.")
        if payload.period_start and payload.period_end and payload.period_end < payload.period_start:
            raise AzureDevOpsConfigError("A data final do período é anterior à data inicial.")
        row = create_query(
            db,
            requester=payload.requester,
            organization=organization,
            project=project,
            work_item_type=work_item_type,
            period_criterion=payload.period_criterion,
            year=payload.year,
            comment_scope=payload.comment_scope,
            person_name=payload.person_name,
            person_identity_id=payload.person_identity_id,
            person_unique_name=payload.person_unique_name,
            profile_id=profile.id if profile else None,
            state_filter=state,
            period_start=payload.period_start,
            period_end=payload.period_end,
        )
    except AzureDevOpsError as exc:
        raise _http(exc) from exc
    return _summary(row)


@router.get("/queries/{query_id}", response_model=IssueAuditDetail)
def get_query(query_id: int, db: Session = Depends(get_db)) -> IssueAuditDetail:
    row = db.get(IssueAuditQuery, query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")
    return _detail(row)


@router.post("/queries/{query_id}/cancel", response_model=IssueAuditSummary)
def post_cancel(query_id: int, db: Session = Depends(get_db)) -> IssueAuditSummary:
    row = db.get(IssueAuditQuery, query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")
    request_cancel(query_id)
    return _summary(row)


@router.post("/queries/{query_id}/retry", response_model=IssueAuditSummary)
def post_retry(query_id: int, db: Session = Depends(get_db)) -> IssueAuditSummary:
    row = db.get(IssueAuditQuery, query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")
    try:
        row = retry_failed(db, row)
    except AzureDevOpsError as exc:
        raise _http(exc) from exc
    return _summary(row)


@router.post("/queries/{query_id}/identity", response_model=IssueAuditDetail)
def post_identity(query_id: int, payload: IssueAuditIdentity, db: Session = Depends(get_db)) -> IssueAuditDetail:
    row = db.get(IssueAuditQuery, query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")
    try:
        row = select_identity(
            db,
            row,
            identity_id=payload.identity_id,
            unique_name=payload.unique_name,
            display_name=payload.display_name,
        )
    except AzureDevOpsError as exc:
        raise _http(exc) from exc
    return _detail(row)


@router.get("/extraction/diagnosis")
def get_extraction_diagnosis() -> dict:
    return extraction_diagnosis()


@router.get("/queries/{query_id}/validation", response_model=IssueAuditValidationOut | None)
def get_query_validation(query_id: int, db: Session = Depends(get_db)) -> IssueAuditValidationOut | None:
    if db.get(IssueAuditQuery, query_id) is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")
    row = get_latest_validation(db, query_id)
    if row is None:
        return None
    return IssueAuditValidationOut(
        id=row.id,
        query_id=row.query_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        payload=row.payload or {},
    )


@router.post("/queries/{query_id}/validate", response_model=IssueAuditValidationOut)
def post_validate_query(query_id: int, db: Session = Depends(get_db)) -> IssueAuditValidationOut:
    row = db.get(IssueAuditQuery, query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")
    try:
        validation = run_validation(db, row)
    except AzureDevOpsError as exc:
        raise _http(exc) from exc
    return IssueAuditValidationOut(
        id=validation.id,
        query_id=validation.query_id,
        created_at=validation.created_at,
        updated_at=validation.updated_at,
        payload=validation.payload or {},
    )


@router.post("/queries/{query_id}/validation/manual", response_model=IssueAuditValidationOut)
def post_manual_review(
    query_id: int,
    payload: IssueAuditManualReviewIn,
    db: Session = Depends(get_db),
) -> IssueAuditValidationOut:
    if db.get(IssueAuditQuery, query_id) is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")
    validation = get_latest_validation(db, query_id)
    if validation is None:
        raise HTTPException(status_code=404, detail="Execute a validação antes de registrar conferência manual.")
    try:
        validation = save_manual_review(
            db,
            validation,
            issue_id=payload.issue_id,
            status=payload.status,
            real_comment_count=payload.real_comment_count,
            real_person_comment_count=payload.real_person_comment_count,
            divergence_type=payload.divergence_type,
            notes=payload.notes,
            reviewer=payload.reviewer,
        )
    except AzureDevOpsError as exc:
        raise _http(exc) from exc
    return IssueAuditValidationOut(
        id=validation.id,
        query_id=validation.query_id,
        created_at=validation.created_at,
        updated_at=validation.updated_at,
        payload=validation.payload or {},
    )


class BackfillAllCommentsBody(BaseModel):
    confirm: bool = False


@router.get("/queries/{query_id}/export-readiness")
def export_readiness(query_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(IssueAuditQuery, query_id)
    if row is None or not row.result:
        raise HTTPException(status_code=404, detail="A consulta ainda não tem resultado.")
    report = comment_storage_report(row.result)
    return {
        **report,
        "comments_matched": row.comments_matched,
        "query_status": row.status,
    }


@router.post("/queries/{query_id}/backfill-all-comments")
def backfill_all_comments(query_id: int, body: BackfillAllCommentsBody, db: Session = Depends(get_db)) -> IssueAuditSummary:
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Confirme o reprocessamento com confirm=true.")
    row = db.get(IssueAuditQuery, query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")
    if not row.result:
        raise HTTPException(status_code=404, detail="A consulta ainda não tem resultado.")
    try:
        row = request_backfill_all_comments(db, row)
    except AzureDevOpsConfigError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _summary(row)


@router.get("/queries/{query_id}/export")
def export_query(
    query_id: int,
    db: Session = Depends(get_db),
    include_all_discussions: bool = Query(default=False),
) -> Response:
    row = db.get(IssueAuditQuery, query_id)
    if row is None or not row.result:
        raise HTTPException(status_code=404, detail="A consulta ainda não tem resultado para exportar.")
    if row.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="A consulta ainda está em andamento.")
    if include_all_discussions:
        ok, message = full_comments_exportable(row.result)
        if not ok:
            raise HTTPException(
                status_code=409,
                detail={"message": message, "can_backfill": True},
            )
    settings_row = get_settings_row(db)
    base_url = settings_row.base_url if settings_row and settings_row.base_url else ""
    validation_row = get_latest_validation(db, query_id)
    workbook, _split = build_audit_workbook(
        {
            "organization": row.organization,
            "project": row.project,
            "work_item_type": row.work_item_type,
            "period_criterion": row.period_criterion,
            "year": row.year,
            "comment_scope": row.comment_scope,
            "person_name": row.person_name,
            "person_identity_id": row.person_identity_id,
            "profile_id": row.profile_id,
            "state": row.state_filter,
            "period_start": row.period_start.isoformat() if row.period_start else None,
            "period_end": row.period_end.isoformat() if row.period_end else None,
        },
        row.result,
        base_url=base_url,
        validation=validation_row.payload if validation_row else None,
        include_all_discussions=include_all_discussions,
    )
    filename = f"auditoria-issues-{row.year}-{row.id}.xlsx"
    return Response(
        content=workbook.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session



from app.database import get_db

from app.schemas import (

    AzureDevOpsFieldProbeOut,

    AzureDevOpsStatusOut,

    AzureDevOpsSyncIn,
    AzureDevOpsSyncPreviewOut,
    AzureSyncPreviewAssigneeOut,

    AzureDevOpsSyncIgnoredOut,
    AzureDevOpsSyncOut,
    AzureDevOpsTestOut,
)

from app.services.activity_persistence import azure_period_label, latest_azure_sync, persist_azure_merge

from app.services.azure_devops_config import (
    build_service,
    get_ignored_assignees,
    is_configured,
    persist_discovered_fields,
    save_ignored_assignees,
)

from app.services.azure_devops_errors import AzureDevOpsConfigError, AzureDevOpsError

from app.services.azure_sync_preview import (
    fetch_and_map_period,
    filter_by_ignored_assignees,
    summarize_assignees,
)



router = APIRouter(prefix="/azure-devops", tags=["azure-devops"])



GENERIC_CONNECTION_MESSAGE = "Não foi possível conectar ao Azure DevOps."

GENERIC_SYNC_MESSAGE = "Não foi possível sincronizar com o Azure DevOps."





def _service_or_error(db: Session):

    try:

        return build_service(db)

    except AzureDevOpsConfigError as exc:

        raise HTTPException(status_code=503, detail=str(exc)) from exc





@router.get("/projects", response_model=list[str])
def list_projects(db: Session = Depends(get_db)) -> list[str]:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        service = _service_or_error(db)
        return service.list_team_projects()
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_CONNECTION_MESSAGE) from exc


@router.get("/status", response_model=AzureDevOpsStatusOut)

def get_status(db: Session = Depends(get_db)) -> AzureDevOpsStatusOut:

    last_sync = latest_azure_sync(db)

    return AzureDevOpsStatusOut(

        configured=is_configured(db),

        last_sync_at=last_sync.imported_at if last_sync else None,

    )





@router.post("/test-connection", response_model=AzureDevOpsTestOut)

def test_connection(db: Session = Depends(get_db)) -> AzureDevOpsTestOut:

    if not is_configured(db):

        return AzureDevOpsTestOut(ok=False, message="Integração não configurada.")

    try:

        service = _service_or_error(db)

        service.test_connection()

        return AzureDevOpsTestOut(ok=True, message="Conexão realizada com sucesso")

    except AzureDevOpsError:

        return AzureDevOpsTestOut(ok=False, message=GENERIC_CONNECTION_MESSAGE)





@router.get("/sample-fields", response_model=AzureDevOpsFieldProbeOut)

def sample_fields(db: Session = Depends(get_db)) -> AzureDevOpsFieldProbeOut:

    if not is_configured(db):

        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")

    try:

        service = _service_or_error(db)

        service.test_connection()

        probe = service.probe_field_names()

        return AzureDevOpsFieldProbeOut(**probe)

    except AzureDevOpsError as exc:

        raise HTTPException(status_code=502, detail=GENERIC_CONNECTION_MESSAGE) from exc





@router.post("/sync-preview", response_model=AzureDevOpsSyncPreviewOut)
def preview_azure_sync(payload: AzureDevOpsSyncIn, db: Session = Depends(get_db)) -> AzureDevOpsSyncPreviewOut:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        service = _service_or_error(db)
        mapped, mapper_ignored, tasks_found, _mapping = fetch_and_map_period(
            service,
            year=payload.year,
            month=payload.month,
        )
        saved_ignored = get_ignored_assignees(db)
        assignees = summarize_assignees(db, mapped, saved_ignored)
        return AzureDevOpsSyncPreviewOut(
            period_label=azure_period_label(payload.year, payload.month),
            year=payload.year,
            month=payload.month,
            tasks_found=tasks_found,
            mappable_tasks=len(mapped),
            mapper_ignored_count=len(mapper_ignored),
            assignees=[AzureSyncPreviewAssigneeOut(**item) for item in assignees],
            saved_ignored_assignees=saved_ignored,
        )
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=GENERIC_SYNC_MESSAGE) from exc


@router.post("/sync", response_model=AzureDevOpsSyncOut)

def sync_azure_devops(payload: AzureDevOpsSyncIn, db: Session = Depends(get_db)) -> AzureDevOpsSyncOut:

    if not is_configured(db):

        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")

    try:

        service = _service_or_error(db)

        mapped, mapper_ignored, task_ids_count, mapping = fetch_and_map_period(
            service,
            year=payload.year,
            month=payload.month,
        )
        persist_discovered_fields(db, mapping)

        ignore_names = list(
            dict.fromkeys([*get_ignored_assignees(db), *payload.ignore_assignee_names])
        )
        save_ignored_assignees(db, ignore_names)
        mapped, assignee_ignored = filter_by_ignored_assignees(mapped, ignore_names)

        extra_warnings: list[dict] = []
        if mapper_ignored:
            extra_warnings.append(
                {
                    "kind": "skipped",
                    "message": f"{len(mapper_ignored)} Task(s) ignorada(s) por dados incompletos ou inválidos.",
                    "row": None,
                }
            )
        if assignee_ignored:
            extra_warnings.append(
                {
                    "kind": "ignored_assignee",
                    "message": f"{len(assignee_ignored)} Task(s) ignorada(s) por regra de responsável.",
                    "row": None,
                }
            )

        batch, stats = persist_azure_merge(
            db,
            year=payload.year,
            month=payload.month,
            incoming=mapped,
            extra_warnings=extra_warnings,
        )

        stats.tasks_found = task_ids_count
        ignored_items = [
            AzureDevOpsSyncIgnoredOut(task_id=item.task_id, title=item.title, reason=item.reason)
            for item in [*mapper_ignored, *assignee_ignored, *stats.ignored_items]
        ]

        return AzureDevOpsSyncOut(
            period_label=azure_period_label(payload.year, payload.month),
            tasks_found=stats.tasks_found,
            created=stats.created,
            updated=stats.updated,
            ignored=len(ignored_items),
            ignored_items=ignored_items,
            last_sync_at=batch.imported_at,
            import_id=batch.id,
        )

    except AzureDevOpsError as exc:

        db.rollback()

        raise HTTPException(status_code=502, detail=GENERIC_SYNC_MESSAGE) from exc

    except Exception:

        db.rollback()

        raise HTTPException(status_code=502, detail=GENERIC_SYNC_MESSAGE)



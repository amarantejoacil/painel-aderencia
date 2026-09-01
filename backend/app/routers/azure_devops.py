from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session



from app.database import get_db

from app.schemas import (

    AzureDevOpsFieldProbeOut,

    AzureDevOpsStatusOut,

    AzureDevOpsSyncIn,

    AzureDevOpsSyncOut,

    AzureDevOpsTestOut,

)

from app.services.activity_persistence import azure_period_label, latest_azure_sync, persist_azure_merge

from app.services.azure_devops_config import build_service, is_configured

from app.services.azure_devops_errors import AzureDevOpsConfigError, AzureDevOpsError

from app.services.azure_mapper import map_work_items



router = APIRouter(prefix="/azure-devops", tags=["azure-devops"])



GENERIC_CONNECTION_MESSAGE = "Não foi possível conectar ao Azure DevOps."

GENERIC_SYNC_MESSAGE = "Não foi possível sincronizar com o Azure DevOps."





def _service_or_error(db: Session):

    try:

        return build_service(db)

    except AzureDevOpsConfigError as exc:

        raise HTTPException(status_code=503, detail=str(exc)) from exc





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





@router.post("/sync", response_model=AzureDevOpsSyncOut)

def sync_azure_devops(payload: AzureDevOpsSyncIn, db: Session = Depends(get_db)) -> AzureDevOpsSyncOut:

    if not is_configured(db):

        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")

    try:

        service = _service_or_error(db)

        mapping = service.discover_field_mapping()

        task_ids = service.query_task_ids(payload.year, payload.month)

        raw_items = service.fetch_work_items(task_ids)

        mapped, skipped = map_work_items(

            raw_items,

            work_date_field=mapping["work_date_field"] or "",

            activity_field=mapping.get("activity_field"),

        )

        extra_warnings: list[dict] = []

        if skipped:

            extra_warnings.append(

                {

                    "kind": "skipped",

                    "message": f"{skipped} Task(s) ignorada(s) por dados incompletos ou inválidos.",

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

        stats.tasks_found = len(task_ids)

        return AzureDevOpsSyncOut(

            period_label=azure_period_label(payload.year, payload.month),

            tasks_found=stats.tasks_found,

            created=stats.created,

            updated=stats.updated,

            ignored=stats.ignored + skipped,

            last_sync_at=batch.imported_at,

            import_id=batch.id,

        )

    except AzureDevOpsError as exc:

        db.rollback()

        raise HTTPException(status_code=502, detail=GENERIC_SYNC_MESSAGE) from exc

    except Exception:

        db.rollback()

        raise HTTPException(status_code=502, detail=GENERIC_SYNC_MESSAGE)



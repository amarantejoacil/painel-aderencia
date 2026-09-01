from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Activity, Collaborator, ImportBatch
from app.schemas import ImportOut
from app.services.csv_parser import CsvValidationError, normalize_name, parse_csv

router = APIRouter(prefix="/imports", tags=["imports"])


def _latest_import(db: Session) -> ImportBatch | None:
    return db.scalars(select(ImportBatch).order_by(ImportBatch.imported_at.desc())).first()


@router.get("/latest", response_model=ImportOut | None)
def get_latest_import(db: Session = Depends(get_db)) -> ImportBatch | None:
    return _latest_import(db)


@router.delete("/{import_id}", status_code=204)
def delete_import(import_id: int, db: Session = Depends(get_db)) -> None:
    batch = db.get(ImportBatch, import_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Importação não encontrada.")
    db.delete(batch)
    db.commit()


@router.post("", response_model=ImportOut)
async def upload_import(file: UploadFile = File(...), db: Session = Depends(get_db)) -> ImportBatch:
    filename = file.filename or "arquivo.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .csv exportado do Azure Boards.")
    raw = await file.read()
    try:
        parsed = parse_csv(raw)
    except CsvValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": exc.message, "details": exc.details},
        ) from exc

    collaborators = list(db.scalars(select(Collaborator)).all())
    by_azure = {normalize_name(item.azure_name): item for item in collaborators}

    unmapped: set[str] = set()
    mapped_count = 0
    rows: list[Activity] = []
    warnings = list(parsed.warnings)

    for activity in parsed.activities:
        match = by_azure.get(normalize_name(activity.assignee_name))
        if match is None:
            unmapped.add(activity.assignee_name)
        else:
            mapped_count += 1
        rows.append(
            Activity(
                task_id=activity.task_id,
                title=activity.title,
                work_item_type=activity.work_item_type,
                azure_assignee=activity.azure_assignee,
                collaborator_id=match.id if match else None,
                work_date=activity.work_date,
                estimated_hours=activity.estimated_hours,
                completed_hours=activity.completed_hours,
                state=activity.state,
                project=activity.project,
            )
        )

    if unmapped:
        names = ", ".join(sorted(unmapped))
        warnings.append(
            {
                "kind": "unmapped",
                "message": (
                    f"{len(unmapped)} responsável(is) do CSV não possuem cadastro: {names}. "
                    "Cadastre o colaborador com o mesmo nome usado no Azure e importe novamente."
                ),
                "row": None,
            }
        )

    db.execute(delete(Activity))
    db.execute(delete(ImportBatch))
    batch = ImportBatch(
        filename=filename,
        imported_at=datetime.now(timezone.utc).replace(tzinfo=None),
        row_count=len(rows),
        mapped_count=mapped_count,
        unmapped_count=len(rows) - mapped_count,
        warning_count=len(warnings),
        status="success",
        warnings=warnings,
    )
    db.add(batch)
    db.flush()
    for row in rows:
        row.import_id = batch.id
        db.add(row)
    db.commit()
    db.refresh(batch)
    return batch

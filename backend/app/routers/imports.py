from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Activity, Collaborator, ImportBatch
from app.schemas import ImportOut, ImportPeriodSummary, ImportPreviewOut
from app.services.csv_parser import CsvValidationError, normalize_name, parse_csv
from app.services.import_period import count_outside_period, summarize_import_period

router = APIRouter(prefix="/imports", tags=["imports"])

MONTH_NAMES = [
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
]


def _latest_import(db: Session) -> ImportBatch | None:
    return db.scalars(select(ImportBatch).order_by(ImportBatch.imported_at.desc())).first()


async def _parse_upload(file: UploadFile):
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
    return filename, parsed


def _validate_reference_period(parsed, year: int, month: int) -> None:
    outside = count_outside_period(parsed.activities, year, month)
    if outside:
        period_label = f"{MONTH_NAMES[month]}/{year}"
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    f"{outside} atividade(s) do arquivo estão fora de {period_label}. "
                    "Confirme o mês e o ano corretos ou ajuste o CSV."
                ),
                "details": [
                    f"Atividades fora do período confirmado: {outside}.",
                    f"Total de linhas válidas no arquivo: {len(parsed.activities)}.",
                ],
            },
        )


@router.get("", response_model=list[ImportOut])
def list_imports(db: Session = Depends(get_db)) -> list[ImportBatch]:
    return list(db.scalars(select(ImportBatch).order_by(ImportBatch.imported_at.desc())).all())


@router.get("/latest", response_model=ImportOut | None)
def get_latest_import(db: Session = Depends(get_db)) -> ImportBatch | None:
    return _latest_import(db)


@router.post("/preview", response_model=ImportPreviewOut)
async def preview_import(file: UploadFile = File(...)) -> ImportPreviewOut:
    filename, parsed = await _parse_upload(file)
    summary = summarize_import_period(parsed.activities)
    return ImportPreviewOut(
        filename=filename,
        row_count=summary["row_count"],
        year=summary["year"],
        month=summary["month"],
        min_date=summary["min_date"],
        max_date=summary["max_date"],
        primary_count=summary["primary_count"],
        outside_primary_count=summary["outside_primary_count"],
        periods=[ImportPeriodSummary(**item) for item in summary["periods"]],
    )


@router.delete("/{import_id}", status_code=204)
def delete_import(import_id: int, db: Session = Depends(get_db)) -> None:
    batch = db.get(ImportBatch, import_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Importação não encontrada.")
    db.delete(batch)
    db.commit()


@router.post("", response_model=ImportOut)
async def upload_import(
    file: UploadFile = File(...),
    year: int = Form(..., ge=2000, le=2100),
    month: int = Form(..., ge=1, le=12),
    db: Session = Depends(get_db),
) -> ImportBatch:
    filename, parsed = await _parse_upload(file)
    _validate_reference_period(parsed, year, month)

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
                activity_category=activity.activity_category,
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

    batch = ImportBatch(
        filename=filename,
        imported_at=datetime.now(timezone.utc).replace(tzinfo=None),
        row_count=len(rows),
        mapped_count=mapped_count,
        unmapped_count=len(rows) - mapped_count,
        warning_count=len(warnings),
        status="success",
        reference_year=year,
        reference_month=month,
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

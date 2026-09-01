from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Activity, Collaborator, ImportBatch
from app.services.activity_normalization import NormalizedActivity
from app.services.csv_parser import normalize_name

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


@dataclass
class SyncStats:
    tasks_found: int = 0
    created: int = 0
    updated: int = 0
    ignored: int = 0


def latest_import_batch(db: Session) -> ImportBatch | None:
    return db.scalars(select(ImportBatch).order_by(ImportBatch.imported_at.desc())).first()


def latest_azure_sync(db: Session) -> ImportBatch | None:
    return db.scalars(
        select(ImportBatch)
        .where(ImportBatch.source == "azure_api")
        .order_by(ImportBatch.imported_at.desc())
    ).first()


def from_activity_model(row: Activity) -> NormalizedActivity:
    assignee_name = row.azure_assignee
    if "<" in assignee_name:
        from app.services.csv_parser import extract_assignee_name

        assignee_name = extract_assignee_name(row.azure_assignee)
    return NormalizedActivity(
        task_id=row.task_id,
        title=row.title,
        azure_assignee=row.azure_assignee,
        assignee_name=assignee_name,
        work_date=row.work_date,
        work_item_type=row.work_item_type,
        completed_hours=row.completed_hours,
        estimated_hours=row.estimated_hours,
        state=row.state,
        project=row.project,
        activity_category=row.activity_category,
        source=row.source if row.source in {"csv", "azure_api"} else "csv",
    )


def match_collaborators(
    db: Session,
    items: list[NormalizedActivity],
    extra_warnings: list[dict] | None = None,
) -> tuple[list[Activity], list[dict], int, int]:
    collaborators = list(db.scalars(select(Collaborator)).all())
    by_azure = {normalize_name(item.azure_name): item for item in collaborators}

    unmapped: set[str] = set()
    mapped_count = 0
    rows: list[Activity] = []
    warnings = list(extra_warnings or [])

    for item in items:
        match = by_azure.get(normalize_name(item.assignee_name))
        if match is None:
            unmapped.add(item.assignee_name)
        else:
            mapped_count += 1
        rows.append(
            Activity(
                task_id=item.task_id,
                title=item.title,
                work_item_type=item.work_item_type,
                azure_assignee=item.azure_assignee,
                collaborator_id=match.id if match else None,
                work_date=item.work_date,
                estimated_hours=item.estimated_hours,
                completed_hours=item.completed_hours,
                state=item.state,
                project=item.project,
                activity_category=item.activity_category,
                source=item.source,
            )
        )

    if unmapped:
        names = ", ".join(sorted(unmapped))
        warnings.append(
            {
                "kind": "unmapped",
                "message": (
                    f"{len(unmapped)} responsável(is) não possuem cadastro: {names}. "
                    "Cadastre o colaborador com o mesmo nome usado no Azure."
                ),
                "row": None,
            }
        )

    return rows, warnings, mapped_count, len(rows) - mapped_count


def persist_csv_snapshot(
    db: Session,
    *,
    filename: str,
    year: int,
    month: int,
    items: list[NormalizedActivity],
    extra_warnings: list[dict] | None = None,
) -> ImportBatch:
    for item in items:
        item.source = "csv"

    rows, warnings, mapped_count, unmapped_count = match_collaborators(db, items, extra_warnings)
    batch = ImportBatch(
        filename=filename,
        imported_at=datetime.now(timezone.utc).replace(tzinfo=None),
        row_count=len(rows),
        mapped_count=mapped_count,
        unmapped_count=unmapped_count,
        warning_count=len(warnings),
        status="success",
        reference_year=year,
        reference_month=month,
        source="csv",
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


def persist_azure_merge(
    db: Session,
    *,
    year: int,
    month: int,
    incoming: list[NormalizedActivity],
    extra_warnings: list[dict] | None = None,
) -> tuple[ImportBatch, SyncStats]:
    stats = SyncStats(tasks_found=len(incoming))

    by_task_id: dict[str, NormalizedActivity] = {}
    latest = db.scalars(
        select(ImportBatch)
        .options(joinedload(ImportBatch.activities))
        .order_by(ImportBatch.imported_at.desc())
    ).unique().first()
    if latest:
        for activity in latest.activities:
            by_task_id[activity.task_id] = from_activity_model(activity)

    for item in incoming:
        if item.work_date.year != year or item.work_date.month != month:
            stats.ignored += 1
            continue
        item.source = "azure_api"
        if item.task_id in by_task_id:
            stats.updated += 1
        else:
            stats.created += 1
        by_task_id[item.task_id] = item

    merged_items = list(by_task_id.values())
    period_label = f"{MONTH_NAMES[month]}/{year}"
    filename = f"Azure DevOps — {period_label}"

    rows, warnings, mapped_count, unmapped_count = match_collaborators(db, merged_items, extra_warnings)
    batch = ImportBatch(
        filename=filename,
        imported_at=datetime.now(timezone.utc).replace(tzinfo=None),
        row_count=len(rows),
        mapped_count=mapped_count,
        unmapped_count=unmapped_count,
        warning_count=len(warnings),
        status="success",
        reference_year=year,
        reference_month=month,
        source="azure_api",
        warnings=warnings,
    )
    db.add(batch)
    db.flush()
    for row in rows:
        row.import_id = batch.id
        db.add(row)
    db.commit()
    db.refresh(batch)
    return batch, stats


def azure_period_label(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month]}/{year}"

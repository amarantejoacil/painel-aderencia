from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from app.models import Activity, ImportBatch
from app.services.activity_normalization import NormalizedActivity, from_parsed_csv
from app.services.activity_persistence import persist_azure_merge, persist_csv_snapshot
from app.services.csv_parser import parse_csv
from tests.conftest import TestingSession

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "relatorio-contrato-exemplo.csv"


def _item(task_id: str, work_date: date, title: str = "Task") -> NormalizedActivity:
    return NormalizedActivity(
        task_id=task_id,
        title=title,
        azure_assignee="Ana Souza <PJMT\\1001>",
        assignee_name="Ana Souza",
        work_date=work_date,
        source="azure_api",
    )


def test_persist_csv_snapshot_creates_batch(client) -> None:
    db = TestingSession()
    try:
        parsed = parse_csv(SAMPLE.read_bytes())
        items = [from_parsed_csv(item) for item in parsed.activities]
        batch = persist_csv_snapshot(
            db,
            filename="exemplo.csv",
            year=2026,
            month=8,
            items=items,
            extra_warnings=list(parsed.warnings),
        )
        assert batch.source == "csv"
        assert batch.row_count == 13
        assert db.scalar(select(func.count()).select_from(Activity)) == 13
    finally:
        db.close()


def test_persist_azure_merge_is_idempotent(client) -> None:
    db = TestingSession()
    try:
        incoming = [_item("1001", date(2026, 8, 3)), _item("1002", date(2026, 8, 4))]
        first, stats_first = persist_azure_merge(db, year=2026, month=8, incoming=incoming)
        second, stats_second = persist_azure_merge(db, year=2026, month=8, incoming=incoming)

        assert stats_first.created == 2
        assert stats_first.updated == 0
        assert stats_second.created == 0
        assert stats_second.updated == 2
        assert db.scalar(select(func.count()).select_from(Activity)) == 4
        assert first.source == "azure_api"
        assert second.source == "azure_api"
    finally:
        db.close()


def test_persist_azure_merge_updates_existing_task_from_csv(client) -> None:
    db = TestingSession()
    try:
        parsed = parse_csv(SAMPLE.read_bytes())
        csv_items = [from_parsed_csv(item) for item in parsed.activities[:1]]
        persist_csv_snapshot(
            db,
            filename="csv.csv",
            year=2026,
            month=8,
            items=csv_items,
        )
        updated = NormalizedActivity(
            task_id=csv_items[0].task_id,
            title="Título atualizado via Azure",
            azure_assignee=csv_items[0].azure_assignee,
            assignee_name=csv_items[0].assignee_name,
            work_date=csv_items[0].work_date,
            completed_hours=Decimal("4.00"),
            source="azure_api",
        )
        _, stats = persist_azure_merge(db, year=2026, month=8, incoming=[updated])
        assert stats.updated == 1
        assert stats.created == 0
        latest = db.scalars(select(Activity).order_by(Activity.id.desc())).first()
        assert latest is not None
        assert latest.title == "Título atualizado via Azure"
        assert latest.completed_hours == Decimal("4.00")
        assert latest.source == "azure_api"
    finally:
        db.close()

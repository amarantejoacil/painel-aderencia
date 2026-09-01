from pathlib import Path

from sqlalchemy import func, select

from app.models import Activity, ImportBatch
from tests.conftest import TestingSession

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "relatorio-contrato-exemplo.csv"
IMPORT_FORM = {"year": 2026, "month": 8}


def test_import_sample_csv_reports_unmapped_people(client) -> None:
    with SAMPLE.open("rb") as handle:
        response = client.post(
            "/api/imports",
            files={"file": ("exemplo.csv", handle, "text/csv")},
            data=IMPORT_FORM,
        )
    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 13
    assert body["unmapped_count"] == 13
    assert any(item["kind"] == "hours_absent" for item in body["warnings"])
    assert any(item["kind"] == "unmapped" for item in body["warnings"])


def test_import_keeps_previous_batches(client) -> None:
    with SAMPLE.open("rb") as handle:
        first = client.post(
            "/api/imports",
            files={"file": ("primeiro.csv", handle, "text/csv")},
            data=IMPORT_FORM,
        )
    with SAMPLE.open("rb") as handle:
        second = client.post(
            "/api/imports",
            files={"file": ("segundo.csv", handle, "text/csv")},
            data=IMPORT_FORM,
        )

    assert first.status_code == 200
    assert second.status_code == 200

    listed = client.get("/api/imports")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 2
    assert body[0]["filename"] == "segundo.csv"
    assert body[1]["filename"] == "primeiro.csv"
    assert client.get("/api/imports/latest").json()["filename"] == "segundo.csv"

    db = TestingSession()
    try:
        assert db.scalar(select(func.count()).select_from(ImportBatch)) == 2
        assert db.scalar(select(func.count()).select_from(Activity)) == 26
    finally:
        db.close()


def test_delete_import_removes_linked_activities(client) -> None:
    with SAMPLE.open("rb") as handle:
        created = client.post(
            "/api/imports",
            files={"file": ("exemplo.csv", handle, "text/csv")},
            data=IMPORT_FORM,
        )
    import_id = created.json()["id"]

    response = client.delete(f"/api/imports/{import_id}")
    assert response.status_code == 204
    assert client.get("/api/imports/latest").json() is None

    db = TestingSession()
    try:
        assert db.get(ImportBatch, import_id) is None
        assert db.scalar(select(func.count()).select_from(Activity)) == 0
    finally:
        db.close()


def test_delete_import_returns_404_for_unknown_id(client) -> None:
    response = client.delete("/api/imports/99999")
    assert response.status_code == 404


def test_preview_import_detects_period(client) -> None:
    with SAMPLE.open("rb") as handle:
        response = client.post("/api/imports/preview", files={"file": ("exemplo.csv", handle, "text/csv")})
    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 13
    assert body["year"] == 2026
    assert body["month"] == 8


def test_import_rejects_mismatched_period(client) -> None:
    with SAMPLE.open("rb") as handle:
        response = client.post(
            "/api/imports",
            files={"file": ("exemplo.csv", handle, "text/csv")},
            data={"year": 2026, "month": 9},
        )
    assert response.status_code == 422
    assert "fora de setembro/2026" in response.json()["detail"]["message"]

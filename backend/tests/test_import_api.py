from pathlib import Path

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.seed import seed_if_empty
from app.database import SessionLocal

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "relatorio-contrato-exemplo.csv"


def test_import_sample_csv_reports_unmapped_people() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()

    client = TestClient(app)
    with SAMPLE.open("rb") as handle:
        response = client.post("/api/imports", files={"file": ("exemplo.csv", handle, "text/csv")})
    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 13
    assert body["unmapped_count"] == 13
    assert any(item["kind"] == "hours_absent" for item in body["warnings"])
    assert any(item["kind"] == "unmapped" for item in body["warnings"])

from datetime import date
from decimal import Decimal

from app.analysis.engine import (
    STATUS_JUSTIFIED_ABSENCE,
    STATUS_MISSING,
    STATUS_NOT_REQUIRED,
    CollaboratorInput,
    analyze_collaborator,
)


def test_team_work_release_marks_day_not_required(client) -> None:
    response = client.post(
        "/api/work-releases",
        json={
            "scope": "team",
            "collaborator_ids": [],
            "start_date": "2026-09-12",
            "end_date": "2026-09-12",
            "description": "Liberados pela chefia",
        },
    )
    assert response.status_code == 201
    assert response.json()["calendar_days"] == 1

    collaborator = CollaboratorInput(
        id=1,
        name="João",
        azure_name="João",
        start_date=date(2026, 8, 1),
        end_date=None,
        daily_hours=Decimal("8"),
        active=True,
    )
    summary = analyze_collaborator(
        collaborator,
        [],
        {date(2026, 9, 12)},
        2026,
        9,
        date(2026, 9, 30),
    )
    day = next(item for item in summary.days if item.date == date(2026, 9, 12))
    assert day.status == STATUS_NOT_REQUIRED
    assert day.expected == Decimal("0.00")


def test_individual_work_release(client) -> None:
    created = client.post(
        "/api/collaborators",
        json={
            "name": "Maria Liberação",
            "azure_name": "Maria Liberação Teste",
            "start_date": "2026-08-01",
            "end_date": None,
            "daily_hours": "8",
            "active": True,
        },
    )
    assert created.status_code == 201
    person_id = created.json()["id"]

    response = client.post(
        "/api/work-releases",
        json={
            "scope": "collaborators",
            "collaborator_ids": [person_id],
            "start_date": "2026-09-10",
            "end_date": "2026-09-10",
            "description": "Liberação individual",
        },
    )
    assert response.status_code == 201
    assert response.json()["collaborator_count"] == 1

    analysis = client.get(f"/api/collaborators/{person_id}/analysis", params={"year": 2026, "month": 9})
    assert analysis.status_code == 200
    day = next(item for item in analysis.json()["days"] if item["date"] == "2026-09-10")
    assert day["status"] == STATUS_JUSTIFIED_ABSENCE
    assert day["absence_type"] == "work_release"
    assert Decimal(day["expected"]) == Decimal("0")

    dashboard = client.get("/api/dashboard", params={"year": 2026, "month": 9})
    assert dashboard.status_code == 200
    other = next(row for row in dashboard.json()["rows"] if row["collaborator"]["id"] != person_id)
    other_day = next(item for item in other["days"] if item["date"] == "2026-09-10")
    assert other_day["status"] == STATUS_MISSING

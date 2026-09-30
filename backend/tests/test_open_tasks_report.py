from datetime import date
from decimal import Decimal

from app.analysis.engine import ActivityInput
from app.services.azure_state_labels import is_azure_state_completed
from app.services.monthly_report import analyze_monthly_team
from app.services.open_tasks_report import collect_non_completed_tasks


def test_is_azure_state_completed() -> None:
    assert is_azure_state_completed("Closed") is True
    assert is_azure_state_completed("done") is True
    assert is_azure_state_completed("Active") is False
    assert is_azure_state_completed(None) is False


def test_collect_non_completed_tasks_filters_month_and_state() -> None:
    activities = [
        ActivityInput(
            task_id="1",
            title="Fechada",
            collaborator_id=1,
            work_date=date(2026, 9, 10),
            completed_hours=Decimal("8"),
            state="Closed",
        ),
        ActivityInput(
            task_id="2",
            title="Aberta",
            collaborator_id=1,
            work_date=date(2026, 9, 11),
            completed_hours=Decimal("4"),
            state="Active",
        ),
        ActivityInput(
            task_id="3",
            title="Outro mês",
            collaborator_id=1,
            work_date=date(2026, 8, 30),
            completed_hours=Decimal("8"),
            state="Active",
        ),
    ]
    rows = collect_non_completed_tasks(activities, 1, 2026, 9)
    assert len(rows) == 1
    assert rows[0]["task_id"] == "2"
    assert rows[0]["state_label"] == "Ativo"


def test_monthly_report_includes_open_tasks_indicator() -> None:
    from app.analysis.engine import CollaboratorInput

    collaborator = CollaboratorInput(
        id=1,
        name="Ana",
        azure_name="Ana",
        start_date=date(2026, 9, 1),
        end_date=None,
        daily_hours=Decimal("8"),
        active=True,
    )
    activities = [
        ActivityInput(
            task_id="10",
            title="Em andamento",
            collaborator_id=1,
            work_date=date(2026, 9, 5),
            completed_hours=Decimal("8"),
            state="In Progress",
        ),
    ]
    report = analyze_monthly_team(
        [collaborator],
        activities,
        set(),
        2026,
        9,
        date(2026, 9, 30),
    )
    assert report["indicators"]["open_tasks"] == 1
    assert len(report["rows"][0]["open_tasks"]) == 1

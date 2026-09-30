from datetime import date

from app.models import CalendarException, Collaborator, CollaboratorAbsence
from app.services.period_observations import build_period_observations_text


def _collaborator(name: str, cid: int = 1) -> Collaborator:
    return Collaborator(
        id=cid,
        name=name,
        azure_name=name,
        start_date=date(2026, 1, 1),
        end_date=None,
        daily_hours=8,
        active=True,
    )


def test_build_period_observations_includes_all_sections() -> None:
    calendar = [
        CalendarException(id=1, date=date(2026, 9, 7), type="holiday", description="Independência"),
        CalendarException(
            id=2,
            date=date(2026, 9, 15),
            type="work_release",
            description="Reunião geral",
        ),
    ]
    absences = [
        (
            CollaboratorAbsence(
                id=1,
                collaborator_id=1,
                type="vacation",
                start_date=date(2026, 9, 8),
                end_date=date(2026, 9, 10),
                note="Férias programadas",
            ),
            _collaborator("Davi Monteiro Alves"),
        ),
        (
            CollaboratorAbsence(
                id=2,
                collaborator_id=2,
                type="medical_certificate",
                start_date=date(2026, 9, 20),
                end_date=date(2026, 9, 20),
                note="Consulta",
            ),
            _collaborator("Alisson de Souza Louly", 2),
        ),
        (
            CollaboratorAbsence(
                id=3,
                collaborator_id=1,
                type="work_release",
                start_date=date(2026, 9, 12),
                end_date=date(2026, 9, 12),
                note="Prova",
            ),
            _collaborator("Davi Monteiro Alves"),
        ),
    ]
    text = build_period_observations_text(
        year=2026,
        month=9,
        calendar_rows=calendar,
        absence_rows=absences,
    )
    assert "Observações do período — Setembro/2026" in text
    assert "07/09/2026 — Feriado — Independência" in text
    assert "15/09/2026 — Liberação de expediente — Reunião geral" in text
    assert "Davi Monteiro Alves — 12/09/2026 — Prova" in text
    assert "Davi Monteiro Alves — 08/09/2026 a 10/09/2026 — Férias — Férias programadas" in text
    assert "Alisson de Souza Louly — 20/09/2026 — Atestado médico — Consulta" in text


def test_build_period_observations_empty_month() -> None:
    text = build_period_observations_text(year=2026, month=9, calendar_rows=[], absence_rows=[])
    assert text.count("Nenhuma registrada no período.") == 4

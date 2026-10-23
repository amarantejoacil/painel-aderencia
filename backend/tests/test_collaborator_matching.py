from datetime import date
from decimal import Decimal

from app.models import Collaborator
from app.services.collaborator_matching import find_collaborator_by_assignee


def _collaborator(**kwargs) -> Collaborator:
    defaults = {
        "id": 1,
        "name": "Tayllisy Kristiny Cruz Silva de Oliveira",
        "azure_name": "TAYLLISY KRISTINY CRUZ SILVA DE OLIVEIRA",
        "start_date": date(2026, 10, 1),
        "end_date": None,
        "daily_hours": Decimal("8"),
        "active": True,
    }
    defaults.update(kwargs)
    return Collaborator(**defaults)


def test_find_by_azure_name() -> None:
    person = _collaborator()
    found = find_collaborator_by_assignee([person], "Tayllisy Kristiny Cruz Silva de Oliveira")
    assert found is person


def test_find_by_display_name_when_azure_differs() -> None:
    person = _collaborator(azure_name="PJMT\\12345")
    found = find_collaborator_by_assignee([person], "Tayllisy Kristiny Cruz Silva de Oliveira")
    assert found is person


def test_find_returns_none_when_missing() -> None:
    assert find_collaborator_by_assignee([], "Desconhecido") is None

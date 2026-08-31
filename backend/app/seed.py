from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarException, Collaborator

COLLABORATORS = [
    ("Alisson de Souza Louly", "Alisson de Souza Louly", date(2026, 8, 3)),
    ("Davi Monteiro Alves", "Davi Monteiro Alves", date(2026, 8, 19)),
    ("Gabriel Araújo Dos Santos", "Gabriel Araújo Dos Santos", date(2026, 8, 3)),
    ("Gleice Ferreira Marques", "Gleice Ferreira Marques", date(2026, 8, 3)),
    ("Joacil Amarante de Paula Junior", "JOACIL AMARANTE DE PAULA JUNIOR", date(2026, 8, 3)),
    ("Jonas Francisco Lima das Chagas", "Jonas Francisco Lima das Chagas", date(2026, 8, 12)),
    ("Matheus Cruz Andrade", "Matheus Cruz Andrade", date(2026, 8, 3)),
    ("Moisés Abinader Fiala", "Moisés Abinader Fiala", date(2026, 8, 12)),
    ("Nayan Pereira Couto Alves", "Nayan Pereira Couto Alves", date(2026, 8, 12)),
    ("Roni Andrei Wartha", "RONI ANDREI WARTHA", date(2026, 8, 3)),
]

EXCEPTIONS = [
    (date(2026, 8, 10), "optional_day", "Ponto facultativo — TJMT"),
    (date(2026, 8, 11), "optional_day", "Ponto facultativo — TJMT"),
]


def seed_if_empty(db: Session) -> None:
    has_people = db.scalars(select(Collaborator.id)).first()
    if has_people is None:
        for name, azure_name, start in COLLABORATORS:
            db.add(
                Collaborator(
                    name=name,
                    azure_name=azure_name,
                    start_date=start,
                    end_date=None,
                    daily_hours=Decimal("8.00"),
                    active=True,
                )
            )

    has_exceptions = db.scalars(select(CalendarException.id)).first()
    if has_exceptions is None:
        for day, kind, description in EXCEPTIONS:
            db.add(CalendarException(date=day, type=kind, description=description))

    db.commit()

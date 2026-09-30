from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarException, Collaborator, CollaboratorAbsence

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

CALENDAR_TYPE_LABEL = {
    "holiday": "Feriado",
    "optional_day": "Ponto facultativo",
    "work_release": "Liberação de expediente",
}

ABSENCE_TYPE_LABEL = {
    "medical_certificate": "Atestado médico",
    "vacation": "Férias",
    "day_off": "Folga",
    "leave": "Licença",
    "work_release": "Liberação de expediente",
    "other": "Outro",
}


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first, last


def _overlaps_month(start: date, end: date, first: date, last: date) -> bool:
    return start <= last and end >= first


def _clip_range(start: date, end: date, first: date, last: date) -> tuple[date, date]:
    return max(start, first), min(end, last)


def _format_date_br(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _format_period(start: date, end: date) -> str:
    if start == end:
        return _format_date_br(start)
    return f"{_format_date_br(start)} a {_format_date_br(end)}"


def _period_label(year: int, month: int) -> str:
    name = MONTH_NAMES[month]
    return f"{name.capitalize()}/{year}"


def _bullet_line(*parts: str) -> str:
    content = " — ".join(part.strip() for part in parts if part and part.strip())
    return f"• {content}" if content else ""


def build_period_observations_text(
    *,
    year: int,
    month: int,
    calendar_rows: list[CalendarException],
    absence_rows: list[tuple[CollaboratorAbsence, Collaborator]],
) -> str:
    first, last = _month_bounds(year, month)
    label = _period_label(year, month)

    calendar_lines: list[str] = []
    team_release_lines: list[str] = []
    individual_release_lines: list[str] = []
    absence_lines: list[str] = []

    for item in sorted(calendar_rows, key=lambda row: row.date):
        if not (first <= item.date <= last):
            continue
        type_label = CALENDAR_TYPE_LABEL.get(item.type, item.type)
        line = _bullet_line(_format_date_br(item.date), type_label, item.description)
        if item.type == "work_release":
            team_release_lines.append(line)
        else:
            calendar_lines.append(line)

    for absence, collaborator in sorted(
        absence_rows,
        key=lambda pair: (pair[0].start_date, pair[1].name.lower()),
    ):
        if not _overlaps_month(absence.start_date, absence.end_date, first, last):
            continue
        clipped_start, clipped_end = _clip_range(absence.start_date, absence.end_date, first, last)
        type_label = ABSENCE_TYPE_LABEL.get(absence.type, absence.type)
        period = _format_period(clipped_start, clipped_end)
        note = (absence.note or "").strip()
        if absence.type == "work_release":
            individual_release_lines.append(
                _bullet_line(collaborator.name, period, note or type_label)
            )
        else:
            absence_lines.append(
                _bullet_line(collaborator.name, period, type_label, note)
            )

    sections: list[str] = [
        f"Observações do período — {label}",
        "",
        "Exceções de calendário (equipe — feriados e pontos facultativos)",
    ]
    sections.extend(calendar_lines or ["• Nenhuma registrada no período."])
    sections.extend(
        [
            "",
            "Liberação de expediente (equipe)",
        ]
    )
    sections.extend(team_release_lines or ["• Nenhuma registrada no período."])
    sections.extend(
        [
            "",
            "Liberação de expediente (colaboradores específicos)",
        ]
    )
    sections.extend(individual_release_lines or ["• Nenhuma registrada no período."])
    sections.extend(
        [
            "",
            "Ausências dos colaboradores (férias, atestados e demais)",
        ]
    )
    sections.extend(absence_lines or ["• Nenhuma registrada no período."])

    return "\n".join(sections).strip() + "\n"


def fetch_period_observations(
    db: Session,
    year: int,
    month: int,
    collaborator_id: int | None = None,
) -> str:
    calendar_rows = list(db.scalars(select(CalendarException).order_by(CalendarException.date)).all())

    stmt = (
        select(CollaboratorAbsence, Collaborator)
        .join(Collaborator, Collaborator.id == CollaboratorAbsence.collaborator_id)
        .order_by(CollaboratorAbsence.start_date, Collaborator.name)
    )
    if collaborator_id is not None:
        stmt = stmt.where(CollaboratorAbsence.collaborator_id == collaborator_id)
    absence_rows = list(db.execute(stmt).all())

    return build_period_observations_text(
        year=year,
        month=month,
        calendar_rows=calendar_rows,
        absence_rows=[(row[0], row[1]) for row in absence_rows],
    )

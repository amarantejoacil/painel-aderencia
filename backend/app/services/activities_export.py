from __future__ import annotations

import re
from dataclasses import dataclass
import unicodedata
from calendar import monthrange
from datetime import date
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.analysis.engine import AbsenceInput
from app.models import Activity, CalendarException, Collaborator, ImportBatch
from app.services.azure_state_labels import translate_azure_state

HEADERS = [
    "ID",
    "Data da Atividade",
    "Título",
    "Atividade",
    "Atribuído para",
    "Status da Atividade",
    "Horas Executadas",
    "Liberação de expediente",
    "Exceção de calendário",
    "Férias",
]

CALENDAR_EXCEPTION_LABELS = {
    "holiday": "Feriado",
    "optional_day": "Ponto facultativo",
    "work_release": "Liberação de expediente",
}

HEADER_FILL = PatternFill("solid", fgColor="1F6B59")
HEADER_FONT = Font(bold=True, color="FFFFFF")
COLUMN_WIDTHS = {
    "A": 12,
    "B": 16,
    "C": 48,
    "D": 28,
    "E": 28,
    "F": 22,
    "G": 16,
    "H": 28,
    "I": 28,
    "J": 18,
}


@dataclass(frozen=True)
class ExportContext:
    calendar_by_date: dict[date, CalendarException]
    absences_by_collaborator: dict[int, dict[date, AbsenceInput]]


def format_work_release_cell(
    work_date: date,
    collaborator_id: int | None,
    calendar_by_date: dict[date, CalendarException],
    absences_by_collaborator: dict[int, dict[date, AbsenceInput]],
) -> str:
    parts: list[str] = []
    calendar = calendar_by_date.get(work_date)
    if calendar is not None and calendar.type == "work_release":
        parts.append(calendar.description.strip() if calendar.description else "Equipe")
    if collaborator_id is not None:
        absence = absences_by_collaborator.get(collaborator_id, {}).get(work_date)
        if absence is not None and absence.type == "work_release":
            parts.append(absence.note.strip() if absence.note else "Individual")
    return " — ".join(parts)


def format_calendar_exception_cell(
    work_date: date,
    calendar_by_date: dict[date, CalendarException],
) -> str:
    calendar = calendar_by_date.get(work_date)
    if calendar is None or calendar.type == "work_release":
        return ""
    label = CALENDAR_EXCEPTION_LABELS.get(calendar.type, calendar.type)
    description = (calendar.description or "").strip()
    if description:
        return f"{label} — {description}"
    return label


def format_vacation_cell(
    work_date: date,
    collaborator_id: int | None,
    absences_by_collaborator: dict[int, dict[date, AbsenceInput]],
) -> str:
    if collaborator_id is None:
        return ""
    absence = absences_by_collaborator.get(collaborator_id, {}).get(work_date)
    if absence is None or absence.type != "vacation":
        return ""
    return absence.note.strip() if absence.note else "Férias"


def _slug_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")
    return slug or "colaborador"


def _month_name_pt(month: int) -> str:
    names = [
        "",
        "janeiro",
        "fevereiro",
        "marco",
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
    return names[month]


def fetch_activities(
    db: Session,
    year: int,
    month: int,
    collaborator_id: int | None = None,
) -> list[Activity]:
    latest = db.scalars(select(ImportBatch).order_by(ImportBatch.imported_at.desc())).first()
    if not latest:
        return []

    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    stmt = (
        select(Activity)
        .options(joinedload(Activity.collaborator))
        .where(
            Activity.import_id == latest.id,
            Activity.work_date >= first,
            Activity.work_date <= last,
        )
        .order_by(Activity.work_date, Activity.task_id)
    )
    if collaborator_id is not None:
        stmt = stmt.where(Activity.collaborator_id == collaborator_id)
    return list(db.scalars(stmt).unique().all())


def assignee_label(activity: Activity) -> str:
    if activity.collaborator is not None:
        return activity.collaborator.name
    return activity.azure_assignee


def build_export_filename(
    year: int,
    month: int,
    collaborator: Collaborator | None = None,
) -> str:
    month_label = _month_name_pt(month)
    if collaborator is not None:
        return f"atividades_{_slug_name(collaborator.name)}_{month_label}_{year}.xlsx"
    return f"atividades_{month_label}_{year}.xlsx"


def _hours_value(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def build_activities_workbook(
    activities: list[Activity],
    context: ExportContext | None = None,
) -> BytesIO:
    calendar_by_date = context.calendar_by_date if context else {}
    absences_by_collaborator = context.absences_by_collaborator if context else {}
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Atividades"

    for col_index, header in enumerate(HEADERS, start=1):
        cell = worksheet.cell(row=1, column=col_index, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_index, activity in enumerate(activities, start=2):
        worksheet.cell(row=row_index, column=1, value=activity.task_id)

        date_cell = worksheet.cell(row=row_index, column=2, value=activity.work_date)
        date_cell.number_format = "DD/MM/YYYY"
        date_cell.alignment = Alignment(horizontal="center")

        title_cell = worksheet.cell(row=row_index, column=3, value=activity.title)
        title_cell.alignment = Alignment(wrap_text=True, vertical="top")

        category_cell = worksheet.cell(row=row_index, column=4, value=activity.activity_category)
        category_cell.alignment = Alignment(wrap_text=True, vertical="top")

        worksheet.cell(row=row_index, column=5, value=assignee_label(activity))
        worksheet.cell(row=row_index, column=6, value=translate_azure_state(activity.state))

        hours_cell = worksheet.cell(row=row_index, column=7, value=_hours_value(activity.completed_hours))
        if hours_cell.value is not None:
            hours_cell.number_format = "0.00"
            hours_cell.alignment = Alignment(horizontal="right")
        else:
            hours_cell.alignment = Alignment(horizontal="center")

        release_cell = worksheet.cell(
            row=row_index,
            column=8,
            value=format_work_release_cell(
                activity.work_date,
                activity.collaborator_id,
                calendar_by_date,
                absences_by_collaborator,
            ),
        )
        release_cell.alignment = Alignment(wrap_text=True, vertical="top")

        exception_cell = worksheet.cell(
            row=row_index,
            column=9,
            value=format_calendar_exception_cell(activity.work_date, calendar_by_date),
        )
        exception_cell.alignment = Alignment(wrap_text=True, vertical="top")

        vacation_cell = worksheet.cell(
            row=row_index,
            column=10,
            value=format_vacation_cell(
                activity.work_date,
                activity.collaborator_id,
                absences_by_collaborator,
            ),
        )
        vacation_cell.alignment = Alignment(wrap_text=True, vertical="top")

    for column, width in COLUMN_WIDTHS.items():
        worksheet.column_dimensions[column].width = width

    last_col = get_column_letter(len(HEADERS))
    worksheet.auto_filter.ref = f"A1:{last_col}{max(1, len(activities) + 1)}"
    worksheet.freeze_panes = "A2"

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer

from __future__ import annotations

import html
import re
from datetime import date
from decimal import Decimal

from app.analysis.engine import q
from app.services.time_entries.dates import reference_datetime_utc, today_cuiaba
from app.services.time_entries.errors import TimeEntryError

FIELD_TIPO_TAREFA = "Custom.TipoTarefa"
FIELD_ATIVIDADE = "Custom.Atividade"
FIELD_HORAS_ESTIMADA = "Custom.Horasestimada"
FIELD_HORAS_EXECUTADAS = "Custom.Horasexecutadas"
FIELD_IMPEDIMENTO = "Custom.TemouTeveimpedimento"

DEFAULT_TIPO_TAREFA = "Projeto"
DEFAULT_ATIVIDADE = "Gerência"
DEFAULT_IMPEDIMENTO = "Não"
DEFAULT_STATE = "New"
CLOSED_TASK_STATE = "Closed"
DEFAULT_HOURS = Decimal("8.00")
CLOSED_STORY_STATES = frozenset({"closed", "removed", "done"})
USER_STORY_TYPE = "user story"

ADHERENCE_NOTE = (
    "Horas estimadas e horas executadas são gravadas com o mesmo valor informado no formulário. "
    "A aderência usa as horas executadas confirmadas no Azure DevOps."
)

_TITLE_SPACE = re.compile(r"\s+")


def normalize_title(value: str) -> str:
    return _TITLE_SPACE.sub(" ", value).strip().casefold()


def story_blocked_reason(state: str | None, *, accessible: bool) -> str | None:
    if not accessible:
        return (
            "A User Story vinculada não está acessível no Azure DevOps. "
            "Valide o vínculo antes de criar novas Tasks."
        )
    if (state or "").strip().casefold() in CLOSED_STORY_STATES:
        return (
            "A User Story vinculada está encerrada ou removida. "
            "Valide o vínculo antes de criar novas Tasks."
        )
    return None


def ensure_user_story(work_item_type: str, work_item_id: int) -> None:
    if work_item_type.strip().casefold() != USER_STORY_TYPE:
        raise TimeEntryError(
            f"O work item {work_item_id} é do tipo {work_item_type}. "
            "Selecione uma User Story já existente. O sistema não cria histórias."
        )


def parse_hours(value: Decimal | int | float | str) -> Decimal:
    try:
        amount = q(value)
    except Exception as exc:
        raise TimeEntryError("Informe horas estimadas válidas.") from exc
    if amount <= 0 or amount > Decimal("24"):
        raise TimeEntryError("Informe horas estimadas entre 0,01 e 24.")
    return amount


def clean_title(value: str) -> str:
    title = _TITLE_SPACE.sub(" ", value).strip()
    if not title:
        raise TimeEntryError("Informe o título da atividade.")
    if len(title) > 256:
        raise TimeEntryError("O título deve ter no máximo 256 caracteres.")
    return title


def clean_description(value: str | None) -> str:
    text = (value or "").strip()
    if len(text) > 4000:
        raise TimeEntryError("A descrição deve ter no máximo 4000 caracteres.")
    return text


def ensure_reference_date(day: date, *, today: date | None = None) -> date:
    current = today or today_cuiaba()
    if day > current:
        raise TimeEntryError("A data de referência não pode ser posterior a hoje em Cuiabá.")
    return day


def description_html(value: str) -> str:
    return html.escape(value).replace("\n", "<br>")


def build_task_document(
    *,
    title: str,
    description: str,
    reference_date: date,
    estimated_hours: Decimal,
    assignee: str,
    area_path: str,
    iteration_path: str,
    work_date_field: str,
    parent_url: str,
) -> list[dict]:
    document: list[dict] = [
        {"op": "add", "path": "/fields/System.Title", "value": title},
        {"op": "add", "path": "/fields/System.State", "value": DEFAULT_STATE},
        {"op": "add", "path": "/fields/System.AssignedTo", "value": assignee},
        {"op": "add", "path": "/fields/System.AreaPath", "value": area_path},
        {"op": "add", "path": "/fields/System.IterationPath", "value": iteration_path},
        {
            "op": "add",
            "path": f"/fields/{work_date_field}",
            "value": reference_datetime_utc(reference_date),
        },
        {"op": "add", "path": f"/fields/{FIELD_TIPO_TAREFA}", "value": DEFAULT_TIPO_TAREFA},
        {"op": "add", "path": f"/fields/{FIELD_ATIVIDADE}", "value": DEFAULT_ATIVIDADE},
        {"op": "add", "path": f"/fields/{FIELD_HORAS_ESTIMADA}", "value": float(estimated_hours)},
        {"op": "add", "path": f"/fields/{FIELD_HORAS_EXECUTADAS}", "value": float(estimated_hours)},
        {"op": "add", "path": f"/fields/{FIELD_IMPEDIMENTO}", "value": DEFAULT_IMPEDIMENTO},
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": parent_url,
            },
        },
    ]
    if description:
        document.insert(1, {"op": "add", "path": "/fields/System.Description", "value": description_html(description)})
    return document

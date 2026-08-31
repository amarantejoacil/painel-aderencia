from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from app.analysis.engine import q

REQUIRED_ALIASES = {
    "task_id": ["id", "work item id", "work item", "task id"],
    "title": ["title", "título", "titulo"],
    "assignee": ["assigned to", "assignedto", "responsável", "responsavel"],
    "work_date": [
        "data referência",
        "data referencia",
        "data de referência",
        "data de referencia",
        "closed date",
        "finish date",
        "changed date",
        "completed date",
        "data",
    ],
}

OPTIONAL_ALIASES = {
    "work_item_type": ["work item type", "tipo", "type"],
    "state": ["state", "estado", "status"],
    "completed_hours": [
        "completed work",
        "completedwork",
        "horas executadas",
        "horas executada",
        "completed hours",
    ],
    "estimated_hours": [
        "original estimate",
        "horas estimadas",
        "estimated hours",
        "estimate",
    ],
    "project": ["area path", "team project", "project", "projeto"],
}

ASSIGNEE_RE = re.compile(r"^(?P<name>.*?)\s*<[^>]+>\s*$")
HOURS_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*h?\s*$", re.IGNORECASE)


@dataclass
class ParsedActivity:
    task_id: str
    title: str
    azure_assignee: str
    assignee_name: str
    work_date: date
    work_item_type: str | None = None
    completed_hours: Decimal | None = None
    estimated_hours: Decimal | None = None
    state: str | None = None
    project: str | None = None
    row_number: int = 0


@dataclass
class ParseResult:
    activities: list[ParsedActivity] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    columns: dict[str, str] = field(default_factory=dict)
    skipped_rows: int = 0


class CsvValidationError(ValueError):
    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\ufeff", "").strip().lower())


def _resolve_column(headers: list[str], aliases: list[str]) -> str | None:
    normalized = {_normalize_header(header): header for header in headers}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def _detect_frame(raw: bytes) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        for sep in (",", ";", "\t"):
            try:
                frame = pd.read_csv(io.BytesIO(raw), encoding=encoding, sep=sep, dtype=str, keep_default_na=False)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
            if frame.shape[1] >= 4:
                frame.columns = [str(col).replace("\ufeff", "").strip() for col in frame.columns]
                return frame
    raise CsvValidationError(
        "Não foi possível ler o arquivo CSV.",
        [str(last_error)] if last_error else ["Verifique o encoding e o separador."],
    )


def _parse_date(value: str) -> date | None:
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(text, dayfirst=True).date()
    except Exception:  # noqa: BLE001
        return None


def _parse_hours(value: str) -> Decimal | None:
    text = str(value).strip()
    if not text:
        return None
    match = HOURS_RE.match(text)
    if not match:
        return None
    try:
        return q(match.group(1).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def extract_assignee_name(raw: str) -> str:
    text = str(raw).strip()
    match = ASSIGNEE_RE.match(text)
    if match:
        return re.sub(r"\s+", " ", match.group("name").strip())
    return re.sub(r"\s+", " ", text)


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def parse_csv(raw: bytes) -> ParseResult:
    if not raw.strip():
        raise CsvValidationError("O arquivo está vazio.")

    frame = _detect_frame(raw)
    if frame.empty:
        raise CsvValidationError("O arquivo não contém linhas de atividade.")

    headers = list(frame.columns)
    mapping: dict[str, str] = {}
    missing: list[str] = []
    labels = {
        "task_id": "ID da Task",
        "title": "Título",
        "assignee": "Responsável (Assigned To)",
        "work_date": "Data da atividade (Data referência)",
    }
    for key, aliases in REQUIRED_ALIASES.items():
        column = _resolve_column(headers, aliases)
        if column is None:
            missing.append(labels[key])
        else:
            mapping[key] = column

    if missing:
        raise CsvValidationError(
            "O CSV não possui todas as colunas obrigatórias.",
            [
                f"Colunas não encontradas: {', '.join(missing)}.",
                f"Colunas presentes: {', '.join(headers)}.",
                "Este painel espera o export 'Relatório Contrato' do Azure Boards "
                "(Work Item Type, ID, Data referência, Title, Assigned To, State).",
            ],
        )

    for key, aliases in OPTIONAL_ALIASES.items():
        column = _resolve_column(headers, aliases)
        if column:
            mapping[key] = column

    result = ParseResult(columns=mapping)
    for index, row in frame.iterrows():
        row_number = int(index) + 2
        task_id = str(row[mapping["task_id"]]).strip()
        title = str(row[mapping["title"]]).strip()
        assignee_raw = str(row[mapping["assignee"]]).strip()
        date_raw = str(row[mapping["work_date"]]).strip()

        if not any([task_id, title, assignee_raw, date_raw]):
            result.skipped_rows += 1
            continue

        problems: list[str] = []
        if not task_id:
            problems.append("ID da Task vazio")
        if not title:
            problems.append("Título vazio")
        if not assignee_raw:
            problems.append("Responsável vazio")
        work_date = _parse_date(date_raw)
        if work_date is None:
            problems.append(f"Data inválida: '{date_raw}'")
        if problems:
            result.warnings.append(
                {
                    "kind": "invalid_row",
                    "message": f"Linha {row_number} ignorada: {'; '.join(problems)}.",
                    "row": row_number,
                }
            )
            result.skipped_rows += 1
            continue

        completed = None
        if "completed_hours" in mapping:
            raw_hours = str(row[mapping["completed_hours"]]).strip()
            if raw_hours:
                completed = _parse_hours(raw_hours)
                if completed is None:
                    result.warnings.append(
                        {
                            "kind": "invalid_hours",
                            "message": f"Linha {row_number}: horas executadas inválidas ('{raw_hours}').",
                            "row": row_number,
                        }
                    )

        estimated = None
        if "estimated_hours" in mapping:
            raw_est = str(row[mapping["estimated_hours"]]).strip()
            if raw_est:
                estimated = _parse_hours(raw_est)

        result.activities.append(
            ParsedActivity(
                task_id=task_id,
                title=title,
                azure_assignee=assignee_raw,
                assignee_name=extract_assignee_name(assignee_raw),
                work_date=work_date,
                work_item_type=str(row[mapping["work_item_type"]]).strip() or None
                if "work_item_type" in mapping
                else None,
                completed_hours=completed,
                estimated_hours=estimated,
                state=str(row[mapping["state"]]).strip() or None if "state" in mapping else None,
                project=str(row[mapping["project"]]).strip() or None if "project" in mapping else None,
                row_number=row_number,
            )
        )

    if not result.activities:
        raise CsvValidationError(
            "Nenhuma atividade válida foi encontrada no arquivo.",
            [warning["message"] for warning in result.warnings[:8]],
        )

    if "completed_hours" not in mapping:
        result.warnings.append(
            {
                "kind": "hours_absent",
                "message": (
                    "O arquivo não possui coluna de horas executadas. "
                    "Cada dia com ao menos uma Task será considerado Regular "
                    "com a carga diária do colaborador (modo presença)."
                ),
                "row": None,
            }
        )

    return result

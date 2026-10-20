from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class TimeEntryError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class TimeEntryTransportError(TimeEntryError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class TimeEntryRejected(TimeEntryError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


@dataclass(frozen=True)
class DuplicateHit:
    task_id: int | None
    title: str
    reference_date: date
    estimated_hours: Decimal | None
    origin: str


class TimeEntryDuplicate(TimeEntryError):
    def __init__(self, message: str, duplicates: list[DuplicateHit]) -> None:
        super().__init__(message, status_code=409)
        self.duplicates = duplicates

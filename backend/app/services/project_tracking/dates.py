from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

CUIABA = ZoneInfo("America/Cuiaba")


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def periods_intersect(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def parse_azure_calendar_date(raw: str | None) -> date | None:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def parse_azure_datetime(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def end_of_day_cuiaba(d: date) -> datetime:
    local_end = datetime.combine(d, time(23, 59, 59, 999999), tzinfo=CUIABA)
    return local_end.astimezone(timezone.utc)


def start_of_day_cuiaba(d: date) -> datetime:
    local_start = datetime.combine(d, time(0, 0, 0), tzinfo=CUIABA)
    return local_start.astimezone(timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def sprint_status(start: date, finish: date, *, today: date | None = None) -> str:
    ref = today or now_utc().astimezone(CUIABA).date()
    if ref < start:
        return "planned"
    if ref > finish:
        return "closed"
    return "active"

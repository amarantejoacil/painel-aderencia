from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

CUIABA = ZoneInfo("America/Cuiaba")


def today_cuiaba(now: datetime | None = None) -> date:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(CUIABA).date()


def reference_datetime_utc(day: date) -> str:
    """Meia-noite em Cuiabá, no mesmo formato já gravado nas Tasks do TJMT."""
    return f"{day.isoformat()}T04:00:00Z"


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

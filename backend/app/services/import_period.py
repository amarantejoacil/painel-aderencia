from __future__ import annotations

from collections import Counter
from datetime import date

from app.services.csv_parser import ParsedActivity


def summarize_import_period(activities: list[ParsedActivity]) -> dict:
    dates = [item.work_date for item in activities]
    periods = Counter((item.year, item.month) for item in dates)
    (year, month), primary_count = periods.most_common(1)[0]
    return {
        "year": year,
        "month": month,
        "row_count": len(activities),
        "min_date": min(dates),
        "max_date": max(dates),
        "primary_count": primary_count,
        "outside_primary_count": len(activities) - primary_count,
        "periods": [
            {"year": period_year, "month": period_month, "count": count}
            for (period_year, period_month), count in periods.most_common()
        ],
    }


def count_outside_period(activities: list[ParsedActivity], year: int, month: int) -> int:
    return sum(1 for item in activities if item.work_date.year != year or item.work_date.month != month)

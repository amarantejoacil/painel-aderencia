from datetime import date

from app.services.project_tracking.dates import month_bounds, periods_intersect, sprint_status


def test_month_bounds() -> None:
    start, end = month_bounds(2026, 2)
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_periods_intersect() -> None:
    assert periods_intersect(date(2026, 10, 1), date(2026, 10, 15), date(2026, 10, 10), date(2026, 10, 31))
    assert not periods_intersect(date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 31))


def test_sprint_status() -> None:
    assert sprint_status(date(2026, 10, 20), date(2026, 10, 31), today=date(2026, 10, 20)) == "active"
    assert sprint_status(date(2026, 10, 1), date(2026, 10, 15), today=date(2026, 10, 20)) == "closed"
    assert sprint_status(date(2026, 11, 1), date(2026, 11, 15), today=date(2026, 10, 20)) == "planned"

from __future__ import annotations

from datetime import date

from app.analysis.engine import (
    STATUS_EXCESS,
    STATUS_INCOMPLETE,
    STATUS_MISSING,
    CollaboratorSummary,
    DayResult,
    analyze_team,
)

PENDING_STATUSES = {STATUS_MISSING, STATUS_INCOMPLETE, STATUS_EXCESS}
SITUATION_OK = "ok"
SITUATION_PENDING = "pending"


def is_collaborator_ok(summary: CollaboratorSummary) -> bool:
    return summary.missing == 0 and summary.incomplete == 0 and summary.excess == 0


def pending_days(summary: CollaboratorSummary) -> list[DayResult]:
    return [day for day in summary.days if day.status in PENDING_STATUSES]


def _format_date_list(days: list[date]) -> str:
    labels = [f"{day.day:02d}/{day.month:02d}" for day in sorted(days)]
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} e {labels[1]}"
    return f"{', '.join(labels[:-1])} e {labels[-1]}"


def build_summary_text(summary: CollaboratorSummary) -> str:
    if is_collaborator_ok(summary):
        return "Nenhuma inconsistência identificada no período."

    issues: list[str] = []
    missing = [day.date for day in summary.days if day.status == STATUS_MISSING]
    incomplete = [day.date for day in summary.days if day.status == STATUS_INCOMPLETE]
    excess = [day.date for day in summary.days if day.status == STATUS_EXCESS]

    if missing:
        count = len(missing)
        label = "dia sem lançamento na importação" if count == 1 else "dias sem lançamento na importação"
        issues.append(f"{count} {label}: {_format_date_list(missing)}")
    if incomplete:
        count = len(incomplete)
        label = "dia incompleto" if count == 1 else "dias incompletos"
        issues.append(f"{count} {label}: {_format_date_list(incomplete)}")
    if excess:
        count = len(excess)
        label = "dia excedente" if count == 1 else "dias excedentes"
        issues.append(f"{count} {label}: {_format_date_list(excess)}")

    return ". ".join(issues) + "."


def build_monthly_report(
    summaries: list[CollaboratorSummary],
    year: int,
    month: int,
    situation: str | None = None,
    issue_type: str | None = None,
) -> dict:
    rows: list[dict] = []
    ok_count = 0
    pending_count = 0
    total_missing = 0
    total_incomplete = 0
    total_excess = 0

    for summary in summaries:
        ok = is_collaborator_ok(summary)
        row_situation = SITUATION_OK if ok else SITUATION_PENDING
        if ok:
            ok_count += 1
        else:
            pending_count += 1
        total_missing += summary.missing
        total_incomplete += summary.incomplete
        total_excess += summary.excess

        issues = pending_days(summary)
        if issue_type:
            issues = [day for day in issues if day.status == issue_type]

        if issue_type and not issues:
            continue
        if situation == SITUATION_OK and not ok:
            continue
        if situation == SITUATION_PENDING and ok:
            continue

        rows.append(
            {
                "summary": summary,
                "situation": row_situation,
                "summary_text": build_summary_text(summary),
                "pending_days": issues,
            }
        )

    rows.sort(
        key=lambda item: (
            0 if item["situation"] == SITUATION_PENDING else 1,
            item["summary"].collaborator.name.casefold(),
        )
    )

    return {
        "year": year,
        "month": month,
        "indicators": {
            "collaborators": len(summaries),
            "ok": ok_count,
            "with_issues": pending_count,
            "missing": total_missing,
            "incomplete": total_incomplete,
            "excess": total_excess,
        },
        "rows": rows,
    }


def analyze_monthly_team(
    collaborators,
    activities,
    exception_dates: set[date],
    year: int,
    month: int,
    today: date,
    situation: str | None = None,
    issue_type: str | None = None,
    all_absences=None,
) -> dict:
    summaries = analyze_team(collaborators, activities, exception_dates, year, month, today, all_absences)
    return build_monthly_report(summaries, year, month, situation, issue_type)

from __future__ import annotations

from decimal import Decimal

from app.analysis.engine import (
    STATUS_INCOMPLETE,
    STATUS_MISSING,
    STATUS_REGULAR,
    ActivityInput,
    DayResult,
    effective_task_hours,
    q,
)
from app.services.azure_state_labels import is_azure_state_completed, translate_azure_state


def verify_day_launch(day: DayResult, daily_hours: Decimal) -> dict | None:
    if day.status not in {STATUS_MISSING, STATUS_INCOMPLETE}:
        return None

    if day.task_count == 0:
        return {
            "kind": "no_imported_tasks",
            "message": (
                "Não há Tasks deste colaborador na importação para esta data. "
                "Confira a sincronização do Azure ou o cadastro do responsável."
            ),
        }

    if day.status == STATUS_REGULAR:
        return None

    tasks_detail: list[dict] = []
    for task in day.tasks:
        view = ActivityInput(
            task_id=task.task_id,
            title=task.title,
            collaborator_id=None,
            work_date=day.date,
            completed_hours=task.completed_hours,
            estimated_hours=task.estimated_hours,
            state=task.state,
            project=task.project,
            activity_category=task.activity_category,
        )
        effective = effective_task_hours(view, q(daily_hours))
        tasks_detail.append(
            {
                "task_id": task.task_id,
                "title": task.title,
                "state_label": translate_azure_state(task.state),
                "completed_hours": task.completed_hours,
                "estimated_hours": task.estimated_hours,
                "effective_hours": effective,
            }
        )

    all_closed_without_executed = bool(day.tasks) and all(
        is_azure_state_completed(task.state)
        and (task.completed_hours is None or task.completed_hours == 0)
        for task in day.tasks
    )
    if all_closed_without_executed:
        return {
            "kind": "closed_tasks_without_executed_hours",
            "message": (
                f"{day.task_count} Task(s) importada(s) neste dia (Concluído no Azure), "
                "porém com horas executadas zeradas. Revise o preenchimento no Azure DevOps."
            ),
            "tasks": tasks_detail,
        }

    return {
        "kind": "tasks_with_hour_gap",
        "message": (
            f"{day.task_count} Task(s) importada(s), porém a soma de horas "
            f"({day.executed}) ficou abaixo do esperado ({day.expected})."
        ),
        "tasks": tasks_detail,
    }

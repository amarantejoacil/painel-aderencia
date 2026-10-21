from __future__ import annotations

from typing import Any


def count_stored_all_comments(result: dict) -> int:
    total = 0
    for issue in result.get("issues") or []:
        if issue.get("error"):
            continue
        if issue.get("all_comments") is not None:
            total += len(issue.get("all_comments") or [])
        else:
            total += len(issue.get("comments") or [])
    return total


def count_person_comments(result: dict) -> int:
    total = 0
    for issue in result.get("issues") or []:
        if issue.get("error"):
            continue
        total += len(issue.get("comments") or [])
    return total


def comment_storage_report(result: dict | None) -> dict[str, Any]:
    if not result:
        return {
            "comments_analyzed": 0,
            "comments_stored_full": 0,
            "comments_stored_person": 0,
            "comments_storage_version": 0,
            "issues_incomplete": 0,
            "exportable_full": False,
            "message": "A consulta não tem resultado.",
        }
    expected = int(result.get("comments_analyzed") or 0)
    stored_full = count_stored_all_comments(result)
    stored_person = count_person_comments(result)
    incomplete_ids: list[int] = []
    for issue in result.get("issues") or []:
        if issue.get("error"):
            continue
        expected_issue = issue.get("comment_count")
        if expected_issue is None:
            continue
        need = int(expected_issue)
        have_list = issue.get("all_comments")
        if have_list is None:
            have = len(issue.get("comments") or [])
        else:
            have = len(have_list)
        if have < need:
            incomplete_ids.append(int(issue["id"]))
    exportable = expected > 0 and stored_full >= expected and not incomplete_ids
    if expected == 0:
        exportable = True
        message = None
    elif exportable:
        message = None
    elif stored_full <= stored_person and stored_person < expected:
        message = (
            f"Esta consulta só tem {stored_full} comentário(s) gravados para exportação completa, "
            f"mas foram analisados {expected} no total ({stored_person} da pessoa pesquisada). "
            "Reprocesse os comentários completos antes de exportar todas as discussões."
        )
    elif incomplete_ids:
        sample = ", ".join(str(item) for item in incomplete_ids[:5])
        extra = f" (e mais {len(incomplete_ids) - 5})" if len(incomplete_ids) > 5 else ""
        message = (
            f"Faltam comentários completos em {len(incomplete_ids)} Issue(s), por exemplo: {sample}{extra}. "
            "Reprocesse os comentários completos antes de exportar."
        )
    else:
        message = (
            f"Comentários gravados para exportação completa: {stored_full}; "
            f"analisados na consulta: {expected}. Reprocesse os comentários completos."
        )
    return {
        "comments_analyzed": expected,
        "comments_stored_full": stored_full,
        "comments_stored_person": stored_person,
        "comments_storage_version": int(result.get("comments_storage_version") or 0),
        "issues_incomplete": len(incomplete_ids),
        "exportable_full": exportable,
        "message": message,
        "can_backfill": not exportable and expected > 0,
    }


def full_comments_exportable(result: dict | None) -> tuple[bool, str | None]:
    report = comment_storage_report(result)
    if report["exportable_full"]:
        return True, None
    return False, report.get("message") or "Exportação completa indisponível."

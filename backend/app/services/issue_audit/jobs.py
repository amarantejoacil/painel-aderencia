from __future__ import annotations

import threading
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import IssueAuditQuery
from app.services.azure_devops_config import get_settings_row, resolve_pat
from app.services.azure_devops_errors import AzureDevOpsAuthError, AzureDevOpsConfigError, AzureDevOpsError
from app.services.issue_audit.client import AzureCollectionClient
from app.services.issue_audit.matching import PersonTarget, normalize_name
from app.services.issue_audit.profiles import resolve_audit_profile
from app.services.issue_audit.runner import apply_comment_scope, apply_identity, collect_comments, execute_audit

_cancel_events: dict[int, threading.Event] = {}
_guard = threading.Lock()


def fail_interrupted_audits(db: Session) -> None:
    rows = db.scalars(select(IssueAuditQuery).where(IssueAuditQuery.status.in_(("queued", "running")))).all()
    now = _now()
    for row in rows:
        row.status = "failed"
        row.finished_at = now
        row.error_message = "A consulta foi interrompida porque a API reiniciou."
        row.limitations = list(row.limitations or []) + [row.error_message]
    if rows:
        db.commit()


def create_query(
    db: Session,
    *,
    requester: str | None,
    organization: str,
    project: str,
    work_item_type: str,
    period_criterion: str,
    year: int,
    comment_scope: str,
    person_name: str,
    person_identity_id: str | None,
    person_unique_name: str | None,
    profile_id: str | None = None,
    state_filter: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> IssueAuditQuery:
    row = IssueAuditQuery(
        created_at=_now(),
        requester=(requester or "").strip() or None,
        organization=organization.strip(),
        project=project.strip(),
        work_item_type=work_item_type.strip(),
        period_criterion=period_criterion,
        year=year,
        comment_scope=comment_scope,
        person_name=person_name.strip(),
        person_identity_id=(person_identity_id or "").strip() or None,
        person_unique_name=(person_unique_name or "").strip() or None,
        profile_id=(profile_id or "").strip() or None,
        state_filter=(state_filter or "").strip() or None,
        period_start=period_start,
        period_end=period_end,
        status="queued",
        issues_found=0,
        issues_processed=0,
        comments_analyzed=0,
        comments_matched=0,
        failure_count=0,
        progress_percent=0,
        limitations=[],
        failed_ids=[],
        result=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _start_thread(row.id)
    return row


def request_cancel(query_id: int) -> None:
    with _guard:
        event = _cancel_events.get(query_id)
    if event is not None:
        event.set()


def request_backfill_all_comments(db: Session, row: IssueAuditQuery) -> IssueAuditQuery:
    if row.status in {"queued", "running"}:
        raise AzureDevOpsConfigError("A consulta ainda está em andamento.")
    if not row.result:
        raise AzureDevOpsConfigError("A consulta ainda não tem resultado.")
    from app.services.issue_audit.comment_storage import full_comments_exportable

    exportable, _message = full_comments_exportable(row.result)
    if exportable and int(row.result.get("comments_storage_version") or 0) >= 1:
        raise AzureDevOpsConfigError("Os comentários completos já estão gravados nesta consulta.")
    row.status = "running"
    row.progress_percent = 0
    row.error_message = None
    db.commit()
    _start_thread(row.id, backfill_all_comments=True)
    db.refresh(row)
    return row


def retry_failed(db: Session, row: IssueAuditQuery) -> IssueAuditQuery:
    if row.status == "running":
        raise AzureDevOpsConfigError("A consulta ainda está em andamento.")
    failed = list(row.failed_ids or [])
    if not failed:
        raise AzureDevOpsConfigError("Não há Issues com falha para tentar novamente.")
    row.status = "queued"
    row.finished_at = None
    row.error_message = None
    db.commit()
    _start_thread(row.id, retry_ids=failed)
    db.refresh(row)
    return row


def select_identity(
    db: Session,
    row: IssueAuditQuery,
    *,
    identity_id: str | None,
    unique_name: str | None,
    display_name: str | None,
) -> IssueAuditQuery:
    if not row.result:
        raise AzureDevOpsConfigError("A consulta ainda não tem resultado para filtrar.")
    person = PersonTarget(
        display_name=(display_name or row.person_name).strip(),
        identity_id=(identity_id or "").strip() or None,
        unique_name=(unique_name or "").strip() or None,
    )
    if not person.locked and normalize_name(person.display_name) != normalize_name(row.person_name):
        raise AzureDevOpsConfigError("Selecione uma identidade retornada pela consulta.")
    updated = apply_identity(row.result, person)
    row.person_identity_id = person.identity_id
    row.person_unique_name = person.unique_name
    if display_name and display_name.strip():
        row.person_name = display_name.strip()
    row.result = updated
    row.status = updated["status"]
    row.comments_matched = updated["comments_matched"]
    row.limitations = list(row.limitations or [])
    db.commit()
    db.refresh(row)
    return row


def lookup_people(db: Session, *, organization: str, name: str) -> dict[str, Any]:
    client = _client(db, organization)
    try:
        client.ensure_collection()
        return _lookup(client, name)
    finally:
        client.close()


def list_collection_projects(db: Session, organization: str) -> list[str]:
    client = _client(db, organization)
    try:
        return client.list_projects()
    finally:
        client.close()


def _lookup(client: AzureCollectionClient, name: str) -> dict[str, Any]:
    found = client.search_identities(name)
    if found["status"] == "unavailable":
        return {
            "status": "unavailable",
            "people": [],
            "message": "A pesquisa de usuários não está autorizada para este PAT. A consulta usará o nome de exibição e o identificador encontrado nos comentários.",
        }
    expected = normalize_name(name)
    exact = [person for person in found["people"] if normalize_name(person.get("display_name")) == expected]
    people = exact or found["people"]
    if not people:
        return {"status": "not_found", "people": [], "message": "Nenhuma identidade encontrada com esse nome."}
    if len(exact) == 1:
        return {"status": "matched", "people": exact, "message": None}
    return {
        "status": "ambiguous",
        "people": people,
        "message": "Há mais de uma identidade parecida. Selecione a pessoa correta.",
    }


def _start_thread(
    query_id: int,
    retry_ids: list[int] | None = None,
    *,
    backfill_all_comments: bool = False,
) -> None:
    event = threading.Event()
    with _guard:
        _cancel_events[query_id] = event
    thread = threading.Thread(
        target=_run,
        args=(query_id, event, retry_ids, backfill_all_comments),
        daemon=True,
        name=f"issue-audit-{query_id}",
    )
    thread.start()


def _run(
    query_id: int,
    cancel_event: threading.Event,
    retry_ids: list[int] | None,
    backfill_all_comments: bool = False,
) -> None:
    db = SessionLocal()
    client: AzureCollectionClient | None = None
    try:
        row = db.get(IssueAuditQuery, query_id)
        if row is None:
            return
        row.status = "running"
        db.commit()
        client = _client(db, row.organization)
        person = PersonTarget(row.person_name, row.person_identity_id, row.person_unique_name)

        def on_progress(found: int, processed: int, comments: int, failures: int) -> None:
            current = db.get(IssueAuditQuery, query_id)
            if current is None:
                return
            current.issues_found = found
            current.issues_processed = processed
            current.comments_analyzed = comments
            current.failure_count = failures
            current.progress_percent = 100 if found == 0 else min(99, int(processed * 100 / found))
            db.commit()

        if backfill_all_comments:
            restore_status = str((row.result or {}).get("status") or row.status or "complete")
            updated = _backfill_all_comments(
                client,
                row,
                should_cancel=cancel_event.is_set,
                on_progress=on_progress,
            )
            if person.locked:
                updated = apply_identity(updated, person)
            current = db.get(IssueAuditQuery, query_id)
            if current is None:
                return
            current.result = updated
            current.status = restore_status if not cancel_event.is_set() else "cancelled"
            current.finished_at = _now()
            current.progress_percent = 100
            current.limitations = updated.get("limitations") or []
            if cancel_event.is_set():
                current.error_message = "Reprocessamento de comentários cancelado."
            db.commit()
            return
        if retry_ids:
            result = _retry(client, row, person, retry_ids, on_progress, cancel_event.is_set)
        else:
            profile = resolve_audit_profile(row.profile_id, row.organization, row.project)
            client.ensure_project(row.project)
            result = execute_audit(
                client,
                project=row.project,
                work_item_type=row.work_item_type,
                period_criterion=row.period_criterion,
                year=row.year,
                comment_scope=row.comment_scope,
                person=person,
                on_progress=on_progress,
                should_cancel=cancel_event.is_set,
                comment_strategy=profile.comment_strategy,
                planning_fields=profile.planning_fields,
                profile_id=profile.id or None,
                period_start=row.period_start,
                period_end=row.period_end,
                state=row.state_filter,
            )
        _store_result(db, query_id, result)
    except AzureDevOpsAuthError as exc:
        _store_failure(db, query_id, str(exc))
    except AzureDevOpsError as exc:
        _store_failure(db, query_id, str(exc))
    except Exception:
        _store_failure(db, query_id, "Não foi possível concluir a auditoria.")
    finally:
        if client is not None:
            client.close()
        with _guard:
            _cancel_events.pop(query_id, None)
        db.close()


def _backfill_all_comments(
    client: AzureCollectionClient,
    row: IssueAuditQuery,
    *,
    should_cancel,
    on_progress,
) -> dict[str, Any]:
    previous = dict(row.result or {})
    strategy = _comment_strategy(row)
    issues = [dict(issue) for issue in previous.get("issues") or []]
    limitations = list(previous.get("limitations") or [])
    total_built = 0
    processable = [issue for issue in issues if not issue.get("error")]
    found = len(processable)
    processed = 0
    ui_counts: dict[int, int | None] = {}
    if strategy == "history":
        ui_counts = client.fetch_ui_comment_counts([int(issue["id"]) for issue in processable])
    ui_mismatches: list[tuple[int, int, int]] = []
    for issue in issues:
        if should_cancel():
            limitations.append("Reprocessamento de comentários cancelado antes de terminar.")
            break
        if issue.get("error"):
            continue
        issue_id = int(issue["id"])
        try:
            comments = collect_comments(
                client,
                project=row.project,
                work_item_id=issue_id,
                strategy=strategy,
            )
        except AzureDevOpsAuthError:
            raise
        except AzureDevOpsError as exc:
            limitations.append(f"Issue {issue_id}: comentários completos indisponíveis ({exc}).")
            issue["all_comments"] = list(issue.get("all_comments") or [])
        else:
            comments = apply_comment_scope(
                comments,
                comment_scope=row.comment_scope,
                year=row.year,
                period_start=row.period_start,
                period_end=row.period_end,
            )
            issue["all_comments"] = comments
            total_built += len(comments)
            ui_count = ui_counts.get(issue_id)
            if ui_count is not None and ui_count > len(comments):
                ui_mismatches.append((issue_id, ui_count, len(comments)))
        processed += 1
        if on_progress:
            on_progress(found, processed, int(previous.get("comments_analyzed") or 0), int(previous.get("failure_count") or 0))
    expected = int(previous.get("comments_analyzed") or 0)
    if total_built != expected:
        limitations.append(
            f"Reprocessamento de comentários: {total_built} reconstruídos vs {expected} analisados na consulta original."
        )
    if ui_mismatches:
        sample = ", ".join(f"#{wid} (UI {ui}, histórico {hist})" for wid, ui, hist in ui_mismatches[:5])
        extra = f" e mais {len(ui_mismatches) - 5}" if len(ui_mismatches) > 5 else ""
        limitations.append(
            f"Em {len(ui_mismatches)} Issue(s), System.CommentCount da UI do Azure excede os comentários "
            f"recuperados pelo histórico — {sample}{extra}. A exportação completa reflete apenas o histórico disponível."
        )
    previous["issues"] = issues
    previous["comments_storage_version"] = 1
    previous["limitations"] = limitations
    return previous


def _comment_strategy(row: IssueAuditQuery) -> str:
    stored = str((row.result or {}).get("comment_source") or "")
    if stored in {"history", "comments_api"}:
        return stored
    return resolve_audit_profile(row.profile_id, row.organization, row.project).comment_strategy


def _retry(client, row: IssueAuditQuery, person: PersonTarget, retry_ids: list[int], on_progress, should_cancel) -> dict[str, Any]:
    from app.services.issue_audit.runner import _issue_from_work_item, _payload

    retry_set = {int(item_id) for item_id in retry_ids}
    previous = dict(row.result or {})
    strategy = _comment_strategy(row)
    kept = [issue for issue in previous.get("issues") or [] if int(issue.get("id") or 0) not in retry_set]
    field_refs = previous.get("work_item_field_refs")
    field_mapping = previous.get("work_item_field_mapping") or {}
    items, failures = client.fetch_work_items(list(retry_set), field_refs=field_refs)
    by_id = {}
    for item in items:
        try:
            by_id[int(item["id"])] = item
        except (KeyError, TypeError, ValueError):
            continue
    fresh: list[dict[str, Any]] = []
    analyzed = 0
    processed = len(kept)
    total = processed + len(retry_set)
    if on_progress:
        on_progress(total, processed, sum(int(issue.get("comment_count") or 0) for issue in kept), 0)
    for item_id in retry_set:
        if should_cancel():
            break
        item = by_id.get(item_id)
        if item is None:
            message = next((text for failed_id, text in failures if failed_id == item_id), "Work Item inacessível.")
            fresh.append(
                {
                    "id": item_id,
                    "title": "",
                    "description": "",
                    "tags": "",
                    "bucket": "",
                    "areas_internas": "",
                    "areas_externa": "",
                    "work_item_type": "",
                    "state": "",
                    "assigned_to": "",
                    "created_at": None,
                    "changed_at": None,
                    "url": "",
                    "comments": [],
                    "comment_count": None,
                    "error": message,
                }
            )
        else:
            try:
                comments = collect_comments(
                    client,
                    project=row.project,
                    work_item_id=item_id,
                    strategy=strategy,
                )
            except AzureDevOpsAuthError:
                raise
            except AzureDevOpsError as exc:
                fresh.append(
                    _issue_from_work_item(
                        client, row.project, item, [], error=str(exc), field_mapping=field_mapping
                    )
                )
            else:
                comments = apply_comment_scope(
                    comments,
                    comment_scope=row.comment_scope,
                    year=row.year,
                    period_start=row.period_start,
                    period_end=row.period_end,
                )
                analyzed += len(comments)
                fresh.append(
                    _issue_from_work_item(client, row.project, item, comments, field_mapping=field_mapping)
                )
        processed += 1
        if on_progress:
            on_progress(total, processed, analyzed, 0)
    old_analyzed = sum(int(issue.get("comment_count") or 0) for issue in kept)
    done = {int(issue["id"]) for issue in fresh}
    untouched = [
        issue
        for issue in previous.get("issues") or []
        if int(issue.get("id") or 0) in retry_set and int(issue.get("id") or 0) not in done
    ]
    combined = kept + untouched + fresh
    from app.services.issue_audit.runner import _ambiguity

    ambiguous, candidates = (False, []) if person.locked else _ambiguity(combined, person)
    failed_ids = [int(issue["id"]) for issue in combined if issue.get("error")]
    if untouched:
        status = "cancelled"
        limitations = list(previous.get("limitations") or []) + ["A nova tentativa foi cancelada antes de terminar."]
    elif ambiguous:
        status = "ambiguous"
        limitations = list(previous.get("limitations") or [])
    elif failed_ids:
        status = "partial"
        limitations = list(previous.get("limitations") or [])
    else:
        status = "complete"
        limitations = list(previous.get("limitations") or [])
    return _payload(
        issues=combined,
        person=person,
        limitations=limitations,
        failed_ids=failed_ids,
        failure_count=len(failed_ids),
        comments_analyzed=old_analyzed + analyzed,
        issues_found=int(previous.get("issues_found") or len(combined)),
        status=status,
        ambiguous=ambiguous,
        candidates=candidates if ambiguous else [],
        work_item_field_refs=previous.get("work_item_field_refs"),
        work_item_field_mapping=previous.get("work_item_field_mapping"),
        profile_id=previous.get("profile_id") or row.profile_id,
        comment_source=strategy,
    )


def _store_result(db: Session, query_id: int, result: dict[str, Any]) -> None:
    row = db.get(IssueAuditQuery, query_id)
    if row is None:
        return
    row.status = result.get("status") or "failed"
    row.finished_at = _now()
    row.issues_found = int(result.get("issues_found") or 0)
    row.issues_processed = int(result.get("issues_processed") or 0)
    row.comments_analyzed = int(result.get("comments_analyzed") or 0)
    row.comments_matched = int(result.get("comments_matched") or 0)
    row.failure_count = int(result.get("failure_count") or 0)
    row.progress_percent = 100 if row.status != "cancelled" else row.progress_percent
    row.failed_ids = result.get("failed_ids") or []
    row.limitations = result.get("limitations") or []
    row.error_message = result.get("error_message")
    row.result = result
    if result.get("person", {}).get("identity_id") and not row.person_identity_id:
        row.person_identity_id = result["person"]["identity_id"]
    db.commit()


def _store_failure(db: Session, query_id: int, message: str) -> None:
    row = db.get(IssueAuditQuery, query_id)
    if row is None:
        return
    row.status = "failed"
    row.finished_at = _now()
    row.error_message = message
    row.limitations = list(row.limitations or []) + [message]
    row.progress_percent = row.progress_percent or 0
    db.commit()


def _client(db: Session, organization: str) -> AzureCollectionClient:
    row = get_settings_row(db)
    pat = resolve_pat(row) if row else None
    if row is None or not row.base_url or not pat:
        raise AzureDevOpsConfigError("Azure DevOps não configurado. Informe o PAT em Configurações.")
    return AzureCollectionClient(base_url=row.base_url, organization=organization, pat=pat)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

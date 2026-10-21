from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IssueAuditQuery, IssueAuditValidation
from app.services.azure_devops_errors import AzureDevOpsAuthError, AzureDevOpsConfigError, AzureDevOpsError
from app.services.issue_audit.client import COMMENT_SOURCE_LIMITATION, AzureCollectionClient
from app.services.issue_audit.jobs import _client
from app.services.issue_audit.matching import (
    PersonTarget,
    comment_from_update,
    in_selected_year,
    person_matches,
)

logger = logging.getLogger(__name__)

DATE_FIELDS = {"created": "System.CreatedDate", "changed": "System.ChangedDate"}
MAX_SAMPLE = 40
PROBE_COMMENTS_LIMIT = 5


def extraction_diagnosis() -> dict[str, Any]:
    doc_path = Path(__file__).with_name("EXTRACTION.md")
    return {
        "source": "system_history",
        "limitation": COMMENT_SOURCE_LIMITATION,
        "documentation": doc_path.read_text(encoding="utf-8") if doc_path.exists() else "",
        "risks": [
            "Histórico System.History pode divergir do contador de comentários da UI.",
            "Edições contam como nova revisão; exclusões não são detectadas.",
            "Autoria depende de revisedBy; homônimos exigem identity_id.",
            "WIQL sem continuationToken pode truncar períodos muito grandes.",
        ],
    }


def get_latest_validation(db: Session, query_id: int) -> IssueAuditValidation | None:
    return db.scalars(
        select(IssueAuditValidation)
        .where(IssueAuditValidation.query_id == query_id)
        .order_by(IssueAuditValidation.created_at.desc())
        .limit(1)
    ).first()


def run_validation(db: Session, row: IssueAuditQuery) -> IssueAuditValidation:
    if not row.result or not row.result.get("issues"):
        raise AzureDevOpsConfigError("A consulta não tem resultado armazenado para validar.")
    if row.status in {"queued", "running"}:
        raise AzureDevOpsConfigError("Aguarde o fim da consulta antes de validar.")

    client = _client(db, row.organization)
    try:
        person = PersonTarget(row.person_name, row.person_identity_id, row.person_unique_name)
        coverage = validate_coverage(client, row)
        sample_ids = build_stratified_sample(row.result.get("issues") or [], row)
        sample_items = []
        probes: list[dict[str, Any]] = []
        for index, issue_id in enumerate(sample_ids):
            item = validate_issue_sample(client, row, person, issue_id)
            sample_items.append(item)
            if index < PROBE_COMMENTS_LIMIT:
                try:
                    probe = client.probe_comments_api(issue_id)
                    probe["work_item_id"] = issue_id
                    probes.append(probe)
                except AzureDevOpsAuthError:
                    raise
                except AzureDevOpsError as exc:
                    probes.append({"work_item_id": issue_id, "available": False, "error": str(exc)})
        metrics = compute_metrics(coverage, sample_items, row)
        payload = {
            "validated_at": _now_iso(),
            "methodology": extraction_diagnosis(),
            "coverage": coverage,
            "comment_api_probes": probes,
            "sample": {"issue_ids": sample_ids, "items": sample_items},
            "manual_reviews": [],
            "metrics": metrics,
            "query_snapshot": {
                "issues_found": row.issues_found,
                "comments_analyzed": row.comments_analyzed,
                "comments_matched": row.comments_matched,
                "issues_with_person": row.result.get("issues_with_person"),
            },
        }
        record = IssueAuditValidation(
            query_id=row.id,
            created_at=_now(),
            updated_at=_now(),
            payload=payload,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info(
            "issue_audit validation query_id=%s sample=%s coverage_ok=%s",
            row.id,
            len(sample_ids),
            coverage.get("consistent"),
        )
        return record
    finally:
        client.close()


def validate_coverage(client: AzureCollectionClient, row: IssueAuditQuery) -> dict[str, Any]:
    start = date(row.year, 1, 1)
    end = date(row.year + 1, 1, 1)
    date_field = DATE_FIELDS[row.period_criterion]
    wiql_ids, wiql_notes = client.query_work_item_ids(
        project=row.project,
        work_item_type=row.work_item_type,
        date_field=date_field,
        start=start,
        end=end,
    )
    stored_issues = row.result.get("issues") or [] if row.result else []
    stored_ids_raw = [int(item["id"]) for item in stored_issues if item.get("id") is not None]
    stored_set = set(stored_ids_raw)
    wiql_set = set(wiql_ids)
    duplicates = [item for item, count in Counter(stored_ids_raw).items() if count > 1]
    missing = sorted(wiql_set - stored_set)
    extra = sorted(stored_set - wiql_set)
    type_mismatches: list[dict[str, Any]] = []
    project_mismatches: list[dict[str, Any]] = []
    check_ids = list(stored_set)[: min(25, len(stored_set))]
    if check_ids:
        field_refs = (row.result or {}).get("work_item_field_refs")
        items, _failures = client.fetch_work_items(check_ids, field_refs=field_refs)
        for item in items:
            fields = item.get("fields") or {}
            wid = int(item["id"])
            wit = str(fields.get("System.WorkItemType") or "")
            team = str(fields.get("System.TeamProject") or "")
            if wit and wit.casefold() != row.work_item_type.strip().casefold():
                type_mismatches.append({"id": wid, "work_item_type": wit})
            if team and team.casefold() != row.project.strip().casefold():
                project_mismatches.append({"id": wid, "team_project": team})
    consistent = (
        not missing
        and not extra
        and not duplicates
        and len(wiql_ids) == row.issues_found == len(stored_ids_raw)
        and not type_mismatches
        and not project_mismatches
    )
    return {
        "consistent": consistent,
        "wiql_count": len(wiql_ids),
        "stored_count": len(stored_ids_raw),
        "issues_found_field": row.issues_found,
        "unique_stored": len(stored_set),
        "missing_in_stored": missing[:500],
        "missing_count": len(missing),
        "extra_in_stored": extra[:500],
        "extra_count": len(extra),
        "duplicate_stored_ids": duplicates,
        "wiql_limitation_notes": wiql_notes,
        "type_mismatches": type_mismatches,
        "project_mismatches": project_mismatches,
        "filters": {
            "organization": row.organization,
            "project": row.project,
            "work_item_type": row.work_item_type,
            "period_criterion": row.period_criterion,
            "year": row.year,
            "date_field": date_field,
        },
    }


def build_stratified_sample(issues: list[dict[str, Any]], row: IssueAuditQuery) -> list[int]:
    if not issues:
        return []
    by_id = {int(item["id"]): item for item in issues if item.get("id") is not None}
    with_person = [issue_id for issue_id, item in by_id.items() if item.get("person_commented")]
    without_person = [
        issue_id for issue_id, item in by_id.items() if not item.get("person_commented") and not item.get("error")
    ]
    zero_comments = [
        issue_id
        for issue_id, item in by_id.items()
        if (item.get("comment_count") or 0) == 0 and not item.get("error")
    ]
    with_comments = [issue_id for issue_id, item in by_id.items() if (item.get("comment_count") or 0) > 0]
    with_comments.sort(key=lambda issue_id: by_id[issue_id].get("comment_count") or 0, reverse=True)
    high = with_comments[: max(3, len(with_comments) // 10)] if with_comments else []
    low = [issue_id for issue_id in with_comments if (by_id[issue_id].get("comment_count") or 0) <= 2][:5]
    quarters: dict[int, int] = {}
    date_key = "created_at" if row.period_criterion == "created" else "changed_at"
    for issue_id, issue in by_id.items():
        raw = str(issue.get(date_key) or "")
        month = 0
        if len(raw) >= 7:
            try:
                month = int(raw[5:7])
            except ValueError:
                month = 0
        quarter = (month - 1) // 3 + 1 if month else 0
        if quarter and quarter not in quarters:
            quarters[quarter] = issue_id
    strata = [
        ("with_person", with_person),
        ("without_person", without_person),
        ("zero_comments", zero_comments),
        ("high_comments", high),
        ("low_comments", low),
        ("by_quarter", list(quarters.values())),
    ]
    chosen: list[int] = []
    seen: set[int] = set()
    for _name, bucket in strata:
        for issue_id in bucket:
            if issue_id in seen:
                continue
            chosen.append(issue_id)
            seen.add(issue_id)
            if len(chosen) >= MAX_SAMPLE:
                return chosen
    for issue_id in sorted(by_id):
        if issue_id not in seen:
            chosen.append(issue_id)
            seen.add(issue_id)
        if len(chosen) >= MAX_SAMPLE:
            break
    return chosen


def validate_issue_sample(
    client: AzureCollectionClient,
    row: IssueAuditQuery,
    person: PersonTarget,
    issue_id: int,
) -> dict[str, Any]:
    stored = next((item for item in (row.result or {}).get("issues") or [] if int(item.get("id") or 0) == issue_id), None)
    original_count = stored.get("comment_count") if stored else None
    original_person = stored.get("person_comment_count") if stored else None
    original_comments = stored.get("comments") or [] if stored else []
    try:
        updates = client.fetch_comment_updates(issue_id)
        comments = [c for u in updates if (c := comment_from_update(u))]
        if row.comment_scope == "period":
            comments = [c for c in comments if in_selected_year(c, row.year)]
        comments.sort(key=lambda c: c.get("created_at") or "")
        person_comments = [c for c in comments if person_matches(c, person)]
        reextracted_count = len(comments)
        reextracted_person = len(person_comments)
        count_match = original_count == reextracted_count if original_count is not None else None
        person_match = original_person == reextracted_person if original_person is not None else None
        auto_status = "confere" if count_match and person_match else "divergencia" if count_match is False or person_match is False else "nao_verificado"
        return {
            "issue_id": issue_id,
            "url": stored.get("url") if stored else None,
            "title": stored.get("title") if stored else "",
            "stratum_hint": _stratum_hint(stored),
            "source": "system_history",
            "original": {
                "comment_count": original_count,
                "person_comment_count": original_person,
            },
            "reextracted": {
                "comment_count": reextracted_count,
                "person_comment_count": reextracted_person,
            },
            "auto_status": auto_status,
            "divergence": _divergence_detail(original_count, reextracted_count, original_person, reextracted_person),
            "comments_preview": [
                {
                    "id": c.get("id"),
                    "author": c.get("author"),
                    "author_id": c.get("author_id"),
                    "created_at_local": c.get("created_at_local"),
                    "text_preview": (c.get("text") or "")[:240],
                    "matched_person": person_matches(c, person),
                }
                for c in comments[:20]
            ],
            "stored_person_comments": len(original_comments),
        }
    except AzureDevOpsError as exc:
        return {
            "issue_id": issue_id,
            "url": stored.get("url") if stored else None,
            "auto_status": "nao_verificado",
            "error": str(exc),
            "source": "system_history",
            "original": {"comment_count": original_count, "person_comment_count": original_person},
            "reextracted": None,
        }


def save_manual_review(
    db: Session,
    validation: IssueAuditValidation,
    *,
    issue_id: int,
    status: str,
    real_comment_count: int | None,
    real_person_comment_count: int | None,
    divergence_type: str | None,
    notes: str | None,
    reviewer: str | None,
) -> IssueAuditValidation:
    if status not in {"confere", "divergencia", "nao_verificado"}:
        raise AzureDevOpsConfigError("Status de conferência inválido.")
    payload = dict(validation.payload or {})
    reviews = list(payload.get("manual_reviews") or [])
    entry = {
        "issue_id": issue_id,
        "status": status,
        "real_comment_count": real_comment_count,
        "real_person_comment_count": real_person_comment_count,
        "divergence_type": (divergence_type or "").strip() or None,
        "notes": (notes or "").strip() or None,
        "reviewed_by": (reviewer or "").strip() or None,
        "reviewed_at": _now_iso(),
    }
    reviews = [item for item in reviews if int(item.get("issue_id") or 0) != issue_id]
    reviews.append(entry)
    payload["manual_reviews"] = reviews
    payload["metrics"] = compute_metrics_from_payload(payload)
    validation.payload = payload
    validation.updated_at = _now()
    db.commit()
    db.refresh(validation)
    return validation


def compute_metrics(coverage: dict[str, Any], sample_items: list[dict], row: IssueAuditQuery) -> dict[str, Any]:
    auto_divergence = sum(1 for item in sample_items if item.get("auto_status") == "divergencia")
    auto_ok = sum(1 for item in sample_items if item.get("auto_status") == "confere")
    auto_unknown = sum(1 for item in sample_items if item.get("auto_status") == "nao_verificado")
    sample_size = len(sample_items)
    return {
        "coverage_consistent": coverage.get("consistent"),
        "coverage_percent": 100.0 if coverage.get("consistent") else None,
        "sample_size": sample_size,
        "sample_auto_confere": auto_ok,
        "sample_auto_divergencia": auto_divergence,
        "sample_auto_nao_verificado": auto_unknown,
        "sample_divergence_rate": (auto_divergence / sample_size) if sample_size else None,
        "manual_confere": 0,
        "manual_divergencia": 0,
        "manual_nao_verificado": sample_size,
        "manual_divergence_rate": None,
        "disclaimer": (
            f"Validação amostral sobre {sample_size} Issues — não implica 100% de precisão "
            f"sobre {row.issues_found} Issues da consulta."
        ),
    }


def compute_metrics_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(payload.get("metrics") or {})
    reviews = payload.get("manual_reviews") or []
    sample_ids = set(payload.get("sample", {}).get("issue_ids") or [])
    reviewed_ids = {int(r["issue_id"]) for r in reviews if r.get("issue_id") is not None}
    metrics["manual_confere"] = sum(1 for r in reviews if r.get("status") == "confere")
    metrics["manual_divergencia"] = sum(1 for r in reviews if r.get("status") == "divergencia")
    metrics["manual_nao_verificado"] = len(sample_ids - reviewed_ids) + sum(
        1 for r in reviews if r.get("status") == "nao_verificado"
    )
    verified = metrics["manual_confere"] + metrics["manual_divergencia"]
    metrics["manual_divergence_rate"] = (metrics["manual_divergencia"] / verified) if verified else None
    return metrics


def _divergence_detail(
    original_count: int | None,
    reextracted: int,
    original_person: int | None,
    reextracted_person: int,
) -> str | None:
    parts: list[str] = []
    if original_count is not None and original_count != reextracted:
        parts.append(f"comentários {original_count} → {reextracted}")
    if original_person is not None and original_person != reextracted_person:
        parts.append(f"da pessoa {original_person} → {reextracted_person}")
    return "; ".join(parts) if parts else None


def _stratum_hint(stored: dict[str, Any] | None) -> str:
    if not stored:
        return "unknown"
    if stored.get("error"):
        return "failed_original"
    if stored.get("person_commented"):
        return "with_person"
    if (stored.get("comment_count") or 0) == 0:
        return "zero_comments"
    return "without_person"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

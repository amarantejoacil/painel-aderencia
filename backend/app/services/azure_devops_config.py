from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import azure_devops_configured_from_env, settings
from app.models import AzureDevOpsSettings
from app.services.azure_devops import AzureDevOpsService, normalize_project_names
from app.services.azure_devops_errors import AzureDevOpsConfigError
from app.services.secret_encryption import SecretEncryptionError, decrypt_secret, encrypt_secret


@dataclass
class AzureDevOpsConfigView:
    configured: bool
    base_url: str | None
    organization: str | None
    project: str | None
    projects: list[str]
    pat_configured: bool
    pat_expires_at: date | None
    last_test_at: datetime | None
    last_test_ok: bool | None


def resolve_projects(row: AzureDevOpsSettings | None) -> list[str]:
    if row is None:
        return []
    stored = normalize_project_names(row.projects if isinstance(row.projects, list) else None, row.project)
    if stored:
        return stored
    if azure_devops_configured_from_env():
        return normalize_project_names(
            [item.strip() for item in settings.azure_devops_project.split(",") if item.strip()],
            None,
        )
    return []


def get_settings_row(db: Session) -> AzureDevOpsSettings | None:
    return db.get(AzureDevOpsSettings, 1)


def _ensure_row(db: Session) -> AzureDevOpsSettings:
    row = get_settings_row(db)
    if row is None:
        row = AzureDevOpsSettings(id=1)
        db.add(row)
        db.flush()
    return row


def is_configured(db: Session) -> bool:
    row = get_settings_row(db)
    projects = resolve_projects(row)
    if row and row.base_url and row.organization and projects and row.encrypted_pat:
        return True
    return azure_devops_configured_from_env()


def to_view(row: AzureDevOpsSettings | None) -> AzureDevOpsConfigView:
    if row is None or not row.base_url:
        env_configured = azure_devops_configured_from_env()
        env_projects = normalize_project_names(
            [item.strip() for item in settings.azure_devops_project.split(",") if item.strip()],
            None,
        )
        return AzureDevOpsConfigView(
            configured=env_configured,
            base_url=settings.azure_devops_url or None,
            organization=settings.azure_devops_organization or None,
            project=env_projects[0] if env_projects else settings.azure_devops_project or None,
            projects=env_projects,
            pat_configured=env_configured,
            pat_expires_at=None,
            last_test_at=row.last_test_at if row else None,
            last_test_ok=row.last_test_ok if row else None,
        )

    projects = resolve_projects(row)
    configured = bool(row.base_url and row.organization and projects and row.encrypted_pat)
    return AzureDevOpsConfigView(
        configured=configured,
        base_url=row.base_url,
        organization=row.organization,
        project=projects[0] if projects else row.project,
        projects=projects,
        pat_configured=bool(row.encrypted_pat),
        pat_expires_at=row.pat_expires_at,
        last_test_at=row.last_test_at,
        last_test_ok=row.last_test_ok,
    )


def get_config_view(db: Session) -> AzureDevOpsConfigView:
    return to_view(get_settings_row(db))


def save_settings(
    db: Session,
    *,
    base_url: str,
    organization: str,
    projects: list[str],
    pat: str | None,
    pat_expires_at: date | None,
) -> AzureDevOpsConfigView:
    normalized = normalize_project_names(projects)
    if not normalized:
        raise AzureDevOpsConfigError("Informe ao menos um projeto do Azure DevOps.")

    row = _ensure_row(db)
    row.base_url = base_url.strip().rstrip("/")
    row.organization = organization.strip()
    row.projects = normalized
    row.project = normalized[0]
    row.pat_expires_at = pat_expires_at

    if pat and pat.strip():
        row.encrypted_pat = encrypt_secret(pat.strip())
    elif not row.encrypted_pat and not azure_devops_configured_from_env():
        raise AzureDevOpsConfigError("Informe o Personal Access Token.")

    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(row)
    return to_view(row)


def resolve_pat(row: AzureDevOpsSettings | None) -> str | None:
    if row and row.encrypted_pat:
        try:
            return decrypt_secret(row.encrypted_pat)
        except SecretEncryptionError:
            return None
    if azure_devops_configured_from_env():
        return settings.azure_devops_pat.strip()
    return None


def build_service(db: Session) -> AzureDevOpsService:
    row = get_settings_row(db)
    pat = resolve_pat(row)
    projects = resolve_projects(row)
    if row and row.base_url and row.organization and projects and pat:
        return AzureDevOpsService(
            base_url=row.base_url,
            organization=row.organization,
            projects=projects,
            pat=pat,
            work_date_field=row.work_date_field or settings.azure_devops_field_work_date,
            activity_field=row.activity_field or settings.azure_devops_field_activity,
        )
    if azure_devops_configured_from_env():
        return AzureDevOpsService.from_settings()
    raise AzureDevOpsConfigError("Azure DevOps não configurado.")


def persist_discovered_fields(db: Session, mapping: dict[str, str | None]) -> None:
    row = get_settings_row(db)
    if not row:
        return
    changed = False
    work_date = (mapping.get("work_date_field") or "").strip()
    activity = (mapping.get("activity_field") or "").strip()
    if work_date and not (row.work_date_field or "").strip():
        row.work_date_field = work_date
        changed = True
    if activity and not (row.activity_field or "").strip():
        row.activity_field = activity
        changed = True
    if changed:
        row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()


def record_test_result(db: Session, *, ok: bool) -> None:
    row = _ensure_row(db)
    row.last_test_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.last_test_ok = ok
    db.commit()


def backfill_projects_column(db: Session) -> None:
    row = get_settings_row(db)
    if row is None or not row.project:
        return
    if row.projects:
        return
    row.projects = normalize_project_names(None, row.project)
    db.commit()


def migrate_env_to_db_if_needed(db: Session) -> None:
    if get_settings_row(db) is not None:
        return
    if not azure_devops_configured_from_env():
        return
    env_projects = [
        item.strip()
        for item in settings.azure_devops_project.split(",")
        if item.strip()
    ]
    save_settings(
        db,
        base_url=settings.azure_devops_url,
        organization=settings.azure_devops_organization,
        projects=env_projects or [settings.azure_devops_project.strip()],
        pat=settings.azure_devops_pat,
        pat_expires_at=None,
    )

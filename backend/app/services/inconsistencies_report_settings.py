from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import InconsistenciesReportSettings

DEFAULT_COPY_INTRO_REQUIRES_REVIEW = """Olá, {primeiro_nome}.

Segue o relatório de aderência referente a {periodo} para sua verificação (com base na última importação do Azure DevOps).
Pedimos que confira os apontamentos abaixo. Caso já tenha regularizado no Azure ou identifique divergência, por favor me avise."""

DEFAULT_COPY_INTRO_OK = """Olá, {primeiro_nome}.

Segue a conferência de aderência referente a {periodo}. Não identificamos inconsistências nos seus lançamentos neste período.
Se notar alguma divergência em relação ao Azure DevOps, por favor me avise."""


@dataclass(frozen=True)
class InconsistenciesReportSettingsView:
    copy_intro_requires_review: str
    copy_intro_ok: str
    updated_at: datetime | None


def _get_row(db: Session) -> InconsistenciesReportSettings:
    row = db.get(InconsistenciesReportSettings, 1)
    if row is None:
        row = InconsistenciesReportSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_settings_view(db: Session) -> InconsistenciesReportSettingsView:
    row = _get_row(db)
    return InconsistenciesReportSettingsView(
        copy_intro_requires_review=row.copy_intro_requires_review or DEFAULT_COPY_INTRO_REQUIRES_REVIEW,
        copy_intro_ok=row.copy_intro_ok or DEFAULT_COPY_INTRO_OK,
        updated_at=row.updated_at,
    )


def save_settings(
    db: Session,
    *,
    copy_intro_requires_review: str,
    copy_intro_ok: str,
) -> InconsistenciesReportSettingsView:
    row = _get_row(db)
    row.copy_intro_requires_review = copy_intro_requires_review.strip() or None
    row.copy_intro_ok = copy_intro_ok.strip() or None
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return get_settings_view(db)

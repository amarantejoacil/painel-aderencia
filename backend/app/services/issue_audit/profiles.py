from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class AuditProfile:
    id: str
    label: str
    organization: str
    project: str
    work_item_type: str
    comment_strategy: str
    planning_fields: bool

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "id": self.id,
            "label": self.label,
            "organization": self.organization,
            "project": self.project,
            "work_item_type": self.work_item_type,
            "comment_strategy": self.comment_strategy,
            "planning_fields": self.planning_fields,
        }


PAC_WORK_ITEM_FIELDS = [
    "System.Id",
    "System.Title",
    "System.WorkItemType",
    "System.TeamProject",
    "System.State",
    "System.AssignedTo",
    "System.CreatedDate",
    "System.ChangedDate",
]

CTI_GABINETE = AuditProfile(
    id="cti-gabinete",
    label="Gestão Gabinete Coordenadoria — CTI",
    organization="CTI",
    project="Gestão Gabinete Coordenadoria",
    work_item_type="Issue",
    comment_strategy="history",
    planning_fields=True,
)

NUCLEO_PAC = AuditProfile(
    id="nucleo-pac",
    label="Núcleo de Aquisições – PAC — Nucleo",
    organization="Nucleo",
    project="Núcleo de Aquisições - PAC",
    work_item_type="Issue",
    comment_strategy="comments_api",
    planning_fields=False,
)

AUDIT_PROFILES: tuple[AuditProfile, ...] = (CTI_GABINETE, NUCLEO_PAC)
_BY_ID = {profile.id: profile for profile in AUDIT_PROFILES}


def get_profile(profile_id: str | None) -> AuditProfile | None:
    if not profile_id:
        return None
    return _BY_ID.get(profile_id.strip())


def resolve_audit_profile(
    profile_id: str | None,
    organization: str | None,
    project: str | None,
) -> AuditProfile:
    """Perfil explícito tem prioridade. Consultas antigas sem perfil seguem o comportamento do CTI."""
    chosen = get_profile(profile_id)
    if chosen is not None:
        return chosen
    org = (organization or "").casefold()
    proj = (project or "").casefold()
    for profile in AUDIT_PROFILES:
        if profile.organization.casefold() == org and profile.project.casefold() == proj:
            return profile
    return AuditProfile(
        id="",
        label="",
        organization=(organization or "").strip(),
        project=(project or "").strip(),
        work_item_type="Issue",
        comment_strategy="history",
        planning_fields=True,
    )


def period_bounds(year: int, period_start: date | None, period_end: date | None) -> tuple[date, date]:
    """Intervalo do WIQL: início inclusivo e fim exclusivo. Sem datas, usa o ano civil."""
    if period_start is not None and period_end is not None:
        return period_start, period_end + timedelta(days=1)
    return date(year, 1, 1), date(year + 1, 1, 1)

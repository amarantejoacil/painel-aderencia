from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

WORK_ITEM_BASE_FIELDS = [
    "System.Id",
    "System.Title",
    "System.WorkItemType",
    "System.State",
    "System.AssignedTo",
    "System.CreatedDate",
    "System.ChangedDate",
    "System.Description",
    "System.Tags",
]

# Chaves persistidas em cada issue do resultado da auditoria.
EXTRA_FIELD_KEYS = ("bucket", "areas_internas", "areas_externa")


@dataclass(frozen=True)
class _FieldSpec:
    key: str
    label: str
    reference_candidates: tuple[str, ...]
    name_patterns: tuple[re.Pattern[str], ...]


def _norm(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


_FIELD_SPECS: tuple[_FieldSpec, ...] = (
    _FieldSpec(
        "bucket",
        "Bucket",
        ("Custom.Bucket", "Microsoft.VSTS.CMMI.Bucket"),
        (re.compile(r"^bucket$", re.I),),
    ),
    _FieldSpec(
        "areas_internas",
        "Áreas Internas",
        ("Custom.AreasInternas", "Custom.AreaInterna"),
        (
            re.compile(r"areas?\s*internas?", re.I),
            re.compile(r"^areas?\s*internas?$", re.I),
        ),
    ),
    _FieldSpec(
        "areas_externa",
        "Áreas Externa",
        ("Custom.AreasExterna", "Custom.AreaExterna"),
        (
            re.compile(r"areas?\s*externas?", re.I),
            re.compile(r"^areas?\s*externa?$", re.I),
        ),
    ),
)


def _catalog_index(catalog: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_ref: dict[str, dict[str, Any]] = {}
    for item in catalog:
        ref = str(item.get("referenceName") or "").strip()
        if ref:
            by_ref[ref] = item
    return by_ref


def _match_spec(spec: _FieldSpec, catalog: list[dict[str, Any]], by_ref: dict[str, dict[str, Any]]) -> str | None:
    for candidate in spec.reference_candidates:
        if candidate in by_ref:
            return candidate
    for item in catalog:
        name = str(item.get("name") or "")
        reference = str(item.get("referenceName") or "")
        if not reference:
            continue
        normalized_name = _norm(name)
        normalized_ref = _norm(reference)
        for pattern in spec.name_patterns:
            if pattern.search(name) or pattern.search(normalized_name):
                return reference
            if pattern.search(reference) or pattern.search(normalized_ref):
                return reference
    return None


def resolve_issue_work_item_fields(catalog: list[dict[str, Any]]) -> dict[str, Any]:
    """Mapeia campos de planejamento/tags para referenceName do Azure DevOps."""
    by_ref = _catalog_index(catalog)
    mapping: dict[str, str | None] = {}
    refs: list[str] = list(WORK_ITEM_BASE_FIELDS)
    labels: dict[str, str] = {"tags": "Tags"}
    for spec in _FIELD_SPECS:
        ref = _match_spec(spec, catalog, by_ref)
        mapping[spec.key] = ref
        labels[spec.key] = spec.label
        if ref and ref not in refs:
            refs.append(ref)
    return {"refs": refs, "mapping": mapping, "labels": labels}


def load_field_catalog_from_client(client: Any) -> list[dict[str, Any]]:
    preset = getattr(client, "field_catalog", None)
    if preset is not None:
        return list(preset)
    url = f"{client.org_base}/_apis/wit/fields?api-version=7.1"
    payload = client.request("GET", url)
    return list(payload.get("value") or [])


def display_field_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("displayName", "name", "value"):
            part = value.get(key)
            if part is not None and str(part).strip():
                return str(part).strip()
        return ""
    return str(value).strip()


def format_tags(raw: object) -> str:
    if raw is None or not str(raw).strip():
        return ""
    parts = [part.strip() for part in str(raw).split(";") if part.strip()]
    return "; ".join(parts)


def extract_planning_fields(fields: dict[str, Any], mapping: dict[str, str | None]) -> dict[str, str]:
    out = {
        "tags": format_tags(fields.get("System.Tags")),
        "bucket": "",
        "areas_internas": "",
        "areas_externa": "",
    }
    for key in EXTRA_FIELD_KEYS:
        ref = mapping.get(key)
        if ref:
            out[key] = display_field_value(fields.get(ref))
    return out

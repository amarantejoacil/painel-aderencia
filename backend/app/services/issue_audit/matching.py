from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

DISPLAY_TZ = ZoneInfo("America/Cuiaba")
UTC = ZoneInfo("UTC")


@dataclass(frozen=True)
class PersonTarget:
    display_name: str
    identity_id: str | None = None
    unique_name: str | None = None

    @property
    def locked(self) -> bool:
        return bool(self.identity_id or self.unique_name)


def normalize_name(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().split())


def parse_azure_datetime(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def to_local(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(DISPLAY_TZ)


def display_identity(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("displayName") or value.get("uniqueName") or "").strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def author_from_identity(value: Any) -> dict[str, str | None]:
    if not isinstance(value, dict):
        text = str(value or "").strip()
        return {
            "author": text,
            "author_id": None,
            "author_unique_name": None,
            "author_descriptor": None,
        }
    return {
        "author": str(value.get("displayName") or value.get("uniqueName") or "").strip(),
        "author_id": str(value.get("id") or "").strip() or None,
        "author_unique_name": str(value.get("uniqueName") or "").strip() or None,
        "author_descriptor": str(value.get("descriptor") or "").strip() or None,
    }


def author_key(author: dict[str, str | None]) -> str:
    if author.get("author_id"):
        return f"id:{author['author_id']}"
    if author.get("author_unique_name"):
        return f"unique:{author['author_unique_name'].casefold()}"
    return f"name:{normalize_name(author.get('author'))}"


def name_matches(author: dict[str, str | None], target: PersonTarget) -> bool:
    expected = normalize_name(target.display_name)
    if not expected:
        return False
    return normalize_name(author.get("author")) == expected or normalize_name(author.get("author_unique_name")) == expected


def person_matches(author: dict[str, str | None], target: PersonTarget) -> bool:
    if target.identity_id and author.get("author_id"):
        return author["author_id"] == target.identity_id
    if target.unique_name and author.get("author_unique_name"):
        return author["author_unique_name"].casefold() == target.unique_name.casefold()
    if target.locked and (author.get("author_id") or author.get("author_unique_name")):
        return False
    return name_matches(author, target)


def comment_from_update(update: dict[str, Any]) -> dict[str, Any] | None:
    history = (update.get("fields") or {}).get("System.History")
    if not isinstance(history, dict):
        return None
    text = history.get("newValue")
    if not isinstance(text, str) or not text.strip():
        return None
    author = author_from_identity(update.get("revisedBy"))
    created = parse_azure_datetime(str(update.get("revisedDate") or ""))
    local = to_local(created)
    return {
        "id": str(update.get("id") or update.get("rev") or ""),
        "created_at": created.isoformat() if created else None,
        "created_at_local": local.isoformat() if local else None,
        "modified_at": None,
        "text": text,
        "is_deleted": None,
        **author,
    }


def in_selected_year(comment: dict[str, Any], year: int) -> bool:
    local = str(comment.get("created_at_local") or "")
    if len(local) >= 4 and local[:4].isdigit():
        return int(local[:4]) == year
    created = parse_azure_datetime(comment.get("created_at"))
    local_dt = to_local(created)
    return bool(local_dt and local_dt.year == year)


def candidate_from_comment(comment: dict[str, Any]) -> dict[str, str | None]:
    return {
        "id": comment.get("author_id"),
        "display_name": comment.get("author"),
        "unique_name": comment.get("author_unique_name"),
        "descriptor": comment.get("author_descriptor"),
    }

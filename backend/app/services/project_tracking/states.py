from __future__ import annotations

COMPLETED_STATES = frozenset({"closed", "resolved", "done"})


def normalize_state(state: str | None) -> str:
    return (state or "").strip().lower()


def is_completed_state(state: str | None) -> bool:
    return normalize_state(state) in COMPLETED_STATES


def is_removed_state(state: str | None) -> bool:
    return normalize_state(state) == "removed"

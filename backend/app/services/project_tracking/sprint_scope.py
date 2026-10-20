from __future__ import annotations

import re
import unicodedata


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "", text.casefold())
    return text


def area_leaf(area_path: str) -> str:
    return area_path.split("\\")[-1].strip()


def sprint_scope_segments(sprint_path: str, team_project: str) -> tuple[str | None, str | None]:
    parts = [part.strip() for part in sprint_path.split("\\") if part.strip()]
    if len(parts) < 2 or parts[0] != team_project:
        return None, None
    folder = parts[1]
    subproduct: str | None = None
    if len(parts) >= 5 and parts[2].isdigit() and len(parts[2]) == 4:
        subproduct = parts[3]
    return folder, subproduct


def iteration_folder_from_sprint_path(sprint_path: str, team_project: str) -> str | None:
    folder, _ = sprint_scope_segments(sprint_path, team_project)
    return folder


def sprint_matches_area(*, sprint_path: str, team_project: str, area_path: str) -> bool:
    folder, subproduct = sprint_scope_segments(sprint_path, team_project)
    if not folder:
        return False

    leaf = area_leaf(area_path)
    leaf_norm = _normalize(leaf)
    if not leaf_norm:
        return False

    if subproduct:
        sub_norm = _normalize(subproduct)
        if sub_norm == leaf_norm:
            return True
        # Ex.: área «Protocolo-PAV» e Sprint em NiaHub\…\NiaHub - Protocolo PAV\…
        if leaf_norm and sub_norm.endswith(leaf_norm):
            return True
        return False

    folder_norm = _normalize(folder)
    if leaf_norm == folder_norm:
        return True
    if leaf_norm in folder_norm or folder_norm in leaf_norm:
        return True
    if leaf_norm == "pan" and "pan" in folder_norm:
        return True
    if "iaadministrativa" in leaf_norm and "iaadministrativa" in folder_norm:
        return True
    if "radardemateria" in leaf_norm and "radardemateria" in folder_norm:
        return True
    if "nucleoapi" in leaf_norm and "nucleoapi" in folder_norm:
        return True
    return False

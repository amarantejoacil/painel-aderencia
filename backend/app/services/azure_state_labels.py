"""Mapeamento de status de Work Items do Azure Boards para exibição."""

AZURE_STATE_LABELS: dict[str, str] = {
    "closed": "Concluído",
    "done": "Concluído",
    "resolved": "Resolvido",
    "active": "Ativo",
    "new": "Novo",
    "removed": "Removido",
    "cut": "Cortado",
    "inactive": "Inativo",
    "in progress": "Em andamento",
    "inprogress": "Em andamento",
}


def translate_azure_state(state: str | None) -> str:
    if not state or not str(state).strip():
        return "—"
    key = str(state).strip().lower()
    return AZURE_STATE_LABELS.get(key, state.strip())


COMPLETED_AZURE_STATES = frozenset({"closed", "done"})


def is_azure_state_completed(state: str | None) -> bool:
    if not state or not str(state).strip():
        return False
    return str(state).strip().lower() in COMPLETED_AZURE_STATES

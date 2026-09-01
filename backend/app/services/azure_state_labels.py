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

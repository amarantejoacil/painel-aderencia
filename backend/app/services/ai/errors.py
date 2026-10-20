from __future__ import annotations


class AiError(Exception):
    """Erro genérico de integração com IA."""


class AiConfigError(AiError):
    """Configuração ausente ou inválida."""


class AiAuthError(AiError):
    """Chave de API inválida ou não autorizada."""


class AiModelUnavailableError(AiError):
    """Modelo indisponível ou não encontrado."""


class AiRateLimitError(AiError):
    """Limite de utilização atingido."""


class AiConnectionError(AiError):
    """Falha de comunicação ou timeout."""

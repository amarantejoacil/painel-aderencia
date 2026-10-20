"""Serviços reutilizáveis de IA (Google Gemini)."""

__all__ = ["AiExecutionResult", "AiService"]


def __getattr__(name: str):
    if name in __all__:
        from app.services.ai.service import AiExecutionResult, AiService

        return AiExecutionResult if name == "AiExecutionResult" else AiService
    raise AttributeError(name)

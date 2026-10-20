from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Type

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.models import AiUsageLog
from app.services.ai.errors import AiConfigError, AiError
from app.services.ai.gemini_client import GeminiClient
from app.services.gemini_config import is_enabled_for_use, require_api_key, require_model


@dataclass
class AiExecutionResult:
    content: str
    parsed: Any | None
    model: str
    status: str
    input_tokens: int | None
    output_tokens: int | None
    duration_ms: int | None
    error_message: str | None = None


def _sanitize_error(message: str) -> str:
    cleaned = message.strip()
    if len(cleaned) > 480:
        return cleaned[:477] + "..."
    lowered = cleaned.lower()
    if "api key" in lowered or "api_key" in lowered:
        return "Falha na integração de IA."
    return cleaned


def _log_usage(
    db: Session,
    *,
    module: str,
    model: str | None,
    status: str,
    input_tokens: int | None,
    output_tokens: int | None,
    duration_ms: int | None,
    error_message: str | None,
) -> None:
    entry = AiUsageLog(
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        module=module[:100],
        model=model,
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=duration_ms,
        error_message=_sanitize_error(error_message) if error_message else None,
    )
    db.add(entry)
    db.commit()


class AiService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _client(self) -> tuple[GeminiClient, str]:
        _row, api_key = require_api_key(self._db)
        return GeminiClient(api_key), api_key

    def generate_text(
        self,
        *,
        module: str,
        user_content: str,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        require_enabled: bool = True,
    ) -> AiExecutionResult:
        if require_enabled and not is_enabled_for_use(self._db):
            raise AiConfigError("Integração de IA desabilitada ou não configurada.")

        row, _ = require_api_key(self._db)
        model_id = model or require_model(row)
        client, _ = self._client()

        try:
            result = client.generate_content(
                model_id=model_id,
                system_instruction=system_instruction,
                user_content=user_content,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            _log_usage(
                self._db,
                module=module,
                model=result.model,
                status="success",
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=result.duration_ms,
                error_message=None,
            )
            return AiExecutionResult(
                content=result.text,
                parsed=None,
                model=result.model,
                status="success",
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=result.duration_ms,
            )
        except AiError as exc:
            _log_usage(
                self._db,
                module=module,
                model=model_id,
                status="error",
                input_tokens=None,
                output_tokens=None,
                duration_ms=None,
                error_message=str(exc),
            )
            raise

    def generate_structured(
        self,
        *,
        module: str,
        user_content: str,
        schema_model: Type[BaseModel],
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        require_enabled: bool = True,
    ) -> AiExecutionResult:
        if require_enabled and not is_enabled_for_use(self._db):
            raise AiConfigError("Integração de IA desabilitada ou não configurada.")

        schema = schema_model.model_json_schema()
        row, _ = require_api_key(self._db)
        model_id = model or require_model(row)
        client, _ = self._client()

        try:
            result = client.generate_content(
                model_id=model_id,
                system_instruction=system_instruction,
                user_content=user_content,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_json=True,
                response_schema=schema,
            )
            parsed = schema_model.model_validate_json(result.text)
            _log_usage(
                self._db,
                module=module,
                model=result.model,
                status="success",
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=result.duration_ms,
                error_message=None,
            )
            return AiExecutionResult(
                content=result.text,
                parsed=parsed,
                model=result.model,
                status="success",
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=result.duration_ms,
            )
        except ValidationError as exc:
            _log_usage(
                self._db,
                module=module,
                model=model_id,
                status="error",
                input_tokens=None,
                output_tokens=None,
                duration_ms=None,
                error_message="Resposta fora do esquema esperado.",
            )
            raise AiConfigError("Resposta fora do esquema esperado.") from exc
        except AiError:
            raise
        except json.JSONDecodeError as exc:
            _log_usage(
                self._db,
                module=module,
                model=model_id,
                status="error",
                input_tokens=None,
                output_tokens=None,
                duration_ms=None,
                error_message="Resposta JSON inválida.",
            )
            raise AiConfigError("Resposta JSON inválida.") from exc

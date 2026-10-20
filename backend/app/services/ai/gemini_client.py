from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from app.services.ai.errors import (
    AiAuthError,
    AiConnectionError,
    AiError,
    AiModelUnavailableError,
    AiRateLimitError,
)

_TEST_PROMPT = "Responda apenas com a palavra OK."


@dataclass
class GeminiModelInfo:
    id: str
    display_name: str | None


@dataclass
class GeminiGenerateResult:
    text: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    duration_ms: int


def _generation_model_priority(model_id: str) -> int:
    lower = model_id.casefold()
    score = 0
    if "flash" in lower:
        score += 10_000
    version = re.search(r"gemini-(\d+)(?:\.(\d+))?", lower)
    if version:
        score += int(version.group(1)) * 100
        if version.group(2):
            score += int(version.group(2)) * 10
    if "preview" in lower or "exp" in lower:
        score -= 80
    if "embed" in lower:
        score -= 5_000
    if "image" in lower or "imagen" in lower:
        score -= 3_000
    if "tts" in lower or "audio" in lower:
        score -= 3_000
    return score


def _normalize_model_id(name: str) -> str:
    value = name.strip()
    if value.startswith("models/"):
        return value.removeprefix("models/")
    return value


def _map_exception(exc: Exception) -> AiError:
    message = str(exc).lower()
    if any(token in message for token in ("api key", "api_key", "unauthorized", "permission", "401", "403")):
        return AiAuthError("Chave inválida.")
    if any(token in message for token in ("429", "quota", "rate limit", "resource exhausted")):
        return AiRateLimitError("Limite de utilização atingido.")
    if any(token in message for token in ("404", "not found", "model", "unavailable")):
        if "model" in message or "404" in message:
            return AiModelUnavailableError("Modelo indisponível.")
    if any(token in message for token in ("timeout", "timed out", "connection", "network", "503", "502")):
        return AiConnectionError("Falha de comunicação.")
    return AiConnectionError("Falha de comunicação.")


def _usage_from_response(response: Any) -> tuple[int | None, int | None]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None, None
    prompt = getattr(usage, "prompt_token_count", None)
    candidates = getattr(usage, "candidates_token_count", None)
    if prompt is None and hasattr(usage, "promptTokenCount"):
        prompt = usage.promptTokenCount
    if candidates is None and hasattr(usage, "candidatesTokenCount"):
        candidates = usage.candidatesTokenCount
    return prompt, candidates


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def _client(self) -> genai.Client:
        return genai.Client(api_key=self._api_key)

    def list_generation_models(self) -> list[GeminiModelInfo]:
        try:
            client = self._client()
            models: list[GeminiModelInfo] = []
            for item in client.models.list():
                actions = getattr(item, "supported_actions", None) or []
                if actions and "generateContent" not in actions:
                    continue
                raw_name = getattr(item, "name", "") or ""
                model_id = _normalize_model_id(raw_name)
                if not model_id:
                    continue
                display = getattr(item, "display_name", None) or getattr(item, "displayName", None)
                models.append(GeminiModelInfo(id=model_id, display_name=display))
            models.sort(key=lambda m: (-_generation_model_priority(m.id), m.id))
            return models
        except AiError:
            raise
        except Exception as exc:
            raise _map_exception(exc) from exc

    def test_connection(self, model_id: str) -> GeminiGenerateResult:
        return self.generate_content(
            model_id=model_id,
            system_instruction=None,
            user_content=_TEST_PROMPT,
            temperature=0,
            max_output_tokens=16,
        )

    def generate_content(
        self,
        *,
        model_id: str,
        system_instruction: str | None,
        user_content: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        response_json: bool = False,
        response_schema: dict[str, Any] | None = None,
    ) -> GeminiGenerateResult:
        started = time.perf_counter()
        config_kwargs: dict[str, Any] = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if temperature is not None:
            config_kwargs["temperature"] = temperature
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = max_output_tokens
        if response_json:
            config_kwargs["response_mime_type"] = "application/json"
            if response_schema:
                config_kwargs["response_schema"] = response_schema

        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        try:
            client = self._client()
            response = client.models.generate_content(
                model=model_id,
                contents=user_content,
                config=config,
            )
            text = (response.text or "").strip()
            if not text and response_json:
                text = _extract_json_text(response)
            duration_ms = int((time.perf_counter() - started) * 1000)
            prompt_tokens, output_tokens = _usage_from_response(response)
            return GeminiGenerateResult(
                text=text,
                model=model_id,
                input_tokens=prompt_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
            )
        except AiError:
            raise
        except Exception as exc:
            mapped = _map_exception(exc)
            if isinstance(mapped, AiModelUnavailableError):
                raise mapped
            if re.search(r"model.*(not found|invalid|unsupported)", str(exc), re.I):
                raise AiModelUnavailableError("Modelo indisponível.") from exc
            raise mapped from exc


def _extract_json_text(response: Any) -> str:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        parts = getattr(content, "parts", None) or []
        for part in parts:
            text = getattr(part, "text", None)
            if text:
                return str(text).strip()
    return ""

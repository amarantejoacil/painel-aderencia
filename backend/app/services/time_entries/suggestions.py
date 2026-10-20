from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.analysis.engine import q
from app.services.ai.errors import AiConfigError, AiError
from app.services.ai.service import AiService
from app.services.time_entries.errors import TimeEntryError

CATEGORIES = (
    "Acompanhamento dos projetos",
    "Planejamento e priorização",
    "Monitoramento de sprints",
    "Organização de backlog",
    "Alinhamento com analistas",
    "Reuniões com equipe técnica",
    "Apoio à gestão estratégica",
    "Acompanhamento de impedimentos",
    "Monitoramento de chamados e infraestrutura",
    "Elaboração de relatórios gerenciais",
    "Atualização de cronogramas",
    "Comunicação e acompanhamento das entregas",
    "Organização de demandas institucionais",
    "Apoio ao planejamento de novas iniciativas",
    "Acompanhamento de requisitos e validações",
)

STYLE_EXAMPLES = """
Estes exemplos são modelos de redação, não atividades realizadas.

Acompanhamento de projetos
Título: Acompanhamento e monitoramento dos projetos do Núcleo de IA.
Descrição: Acompanhamento das demandas e atividades dos projetos do Núcleo de Inteligência Artificial, incluindo verificação do andamento das entregas, alinhamento com a equipe técnica e identificação de pontos que necessitam de direcionamento.

Planejamento e backlog
Título: Revisão e organização do backlog dos projetos.
Descrição: Revisão das demandas registradas nos backlogs dos projetos, identificação de pendências, análise de prioridades e apoio à organização das próximas atividades de desenvolvimento.

Alinhamento com equipe
Título: Alinhamento de demandas e acompanhamento das equipes.
Descrição: Participação em alinhamentos com integrantes das equipes técnicas e de análise, visando acompanhar atividades em andamento, esclarecer dúvidas, organizar prioridades e apoiar a continuidade das entregas.

Apoio à gestão estratégica
Título: Apoio à gestão estratégica e acompanhamento das demandas do NIA.
Descrição: Apoio ao acompanhamento das demandas institucionais do Núcleo de Inteligência Artificial, incluindo organização de informações, verificação de prioridades e suporte aos encaminhamentos necessários.
""".strip()

ROLE_CONTEXT = (
    "O usuário atua como gerente de projeto do Núcleo de Inteligência Artificial (NIA). "
    "Redija título e descrição nesse contexto institucional, sem inventar outro cargo ou área."
)

SUGGEST_INSTRUCTION = """
Você redige o título e a descrição de uma Task de gestão de projetos, em português do Brasil.
As ações marcadas são o que o usuário declara ter realizado. Cubra somente essas ações.
Se houver relato, use-o para detalhar as ações marcadas. Não acrescente ação que não foi marcada.
Os exemplos são estilo de redação, não fatos.
Não invente decisão, entrega específica, impedimento ou resultado que o usuário não tenha informado.
Não trate atualização de Task como reunião.
Não afirme participação em reunião se "Reuniões com equipe técnica" não estiver marcada e o relato não a descrever.
Os registros encontrados no Azure são contexto separado e não são o trabalho declarado.
Não escreva checklist, instruções, meta-comentários nem texto em inglês.
O título deve ser uma frase objetiva de trabalho realizado, nunca palavras como "empty", "yes" ou rótulos de campo.
Se o usuário não detalhou atividades além das ações marcadas, deixe activities nulo.
Se o usuário não informou resultado, deixe result nulo.
Se o usuário não informou o tempo, deixe hours nulo. Não invente horas.
""".strip()

SUGGEST_TEXT_FALLBACK = """
Responda exatamente neste formato, em português, sem markdown:
TÍTULO: ...
DESCRIÇÃO: ...
ATIVIDADES: ...
RESULTADO: ...
HORAS: ...
""".strip()

EMPTY_MARKERS = {
    "",
    "vazio",
    "vazia",
    "não informado",
    "nao informado",
    "n/a",
    "na",
    "-",
    "—",
    "empty",
    "yes",
    "yes.",
    "null",
    "none",
}
FIELD_NAMES = (
    "TÍTULO",
    "TITULO",
    "TITLE",
    "DESCRIÇÃO",
    "DESCRICAO",
    "DESCRIPTION",
    "ATIVIDADES",
    "ACTIVITIES",
    "RESULTADO",
    "RESULT",
    "HORAS",
    "HOURS",
)
_META_LINE = re.compile(r"(?i)^(\*?\s*[-•]?\s*)?(check all|verify|ensure|make sure|included in)")
_GARBAGE_TITLE = re.compile(r"(?i)^(empty\s*:|yes\.?|n/a|null|none|check all)")


class SuggestionAiModel(BaseModel):
    title: str = Field(min_length=8, max_length=256)
    description: str = Field(min_length=20, max_length=4000)
    activities: str | None = Field(default=None, max_length=2000)
    result: str | None = Field(default=None, max_length=2000)
    hours: float | None = Field(default=None, ge=0.01, le=24)


@dataclass
class Suggestion:
    title: str
    description: str
    activities: str | None
    result: str | None
    hours: Decimal | None


def build_suggestion_prompt(
    *,
    categories: list[str],
    text: str,
    hours: Decimal | None,
    existing_titles: list[str],
) -> str:
    titles = [item.strip() for item in existing_titles if item and item.strip()]
    found = "\n".join(f"- {item}" for item in titles) or "- Nenhum registro encontrado foi informado para esta data."
    selected = "\n".join(f"- {item}" for item in categories)
    informed_hours = "não informado" if hours is None else str(q(hours))
    narrative = text.strip()
    if narrative:
        declared = (
            "Ações marcadas pelo usuário:\n"
            f"{selected}\n\n"
            "Relato do usuário sobre o que foi realizado:\n"
            f"{narrative}"
        )
    else:
        declared = (
            "Ações marcadas pelo usuário. Elas são o que ele declara ter realizado. "
            "Redija o texto somente a partir delas:\n"
            f"{selected}"
        )
    return (
        f"{ROLE_CONTEXT}\n\n"
        f"{declared}\n\n"
        "Registros encontrados no Azure nesta data (não são o relato do usuário):\n"
        f"{found}\n\n"
        f"Tempo informado pelo usuário: {informed_hours}\n\n"
        f"{STYLE_EXAMPLES}"
    )


def parse_suggestion(
    raw: str,
    *,
    informed_hours: Decimal | None,
    categories: list[str] | None = None,
) -> Suggestion:
    fields = _labeled_fields(raw)
    title = _clean(
        fields.get("TÍTULO")
        or fields.get("TITULO")
        or fields.get("TITLE")
    )
    description = _clean(
        fields.get("DESCRIÇÃO")
        or fields.get("DESCRICAO")
        or fields.get("DESCRIPTION")
    )
    activities = _optional(fields.get("ATIVIDADES") or fields.get("ACTIVITIES"))
    result = _optional(fields.get("RESULTADO") or fields.get("RESULT"))
    if _is_garbage_title(title):
        title = ""
    description = _strip_meta_lines(description)
    if not title and not description:
        lines = [
            line.strip()
            for line in (raw or "").splitlines()
            if line.strip() and not _META_LINE.match(line.strip())
        ]
        if lines:
            first = _split_label(lines[0])
            if first[0]:
                title = _clean(first[1]) if not _is_garbage_title(_clean(first[1])) else ""
                description = _strip_meta_lines("\n".join(lines[1:]))
            else:
                title = lines[0] if not _is_garbage_title(lines[0]) else ""
                description = _strip_meta_lines("\n".join(lines[1:]))
    if not title or _is_garbage_title(title):
        if categories:
            title = _fallback_title(categories)
        else:
            raise TimeEntryError("A sugestão não trouxe um título válido. Tente Gerar com IA novamente.")
    if len(description.strip()) < 20:
        description = _fallback_description(categories or [], activities, result)
    composed = compose_description(description, activities, result)
    if len(composed.strip()) < 20:
        raise TimeEntryError("A sugestão não trouxe uma descrição válida. Tente Gerar com IA novamente.")
    hours = q(informed_hours) if informed_hours is not None else None
    return Suggestion(
        title=title.strip(),
        description=composed,
        activities=activities,
        result=result,
        hours=hours,
    )


def compose_description(description: str, activities: str | None, result: str | None) -> str:
    parts: list[str] = []
    if description.strip():
        parts.append(description.strip())
    if activities:
        parts.append(f"A atividade contemplou:\n{activities}")
    if result:
        parts.append(f"Resultado:\n{result}")
    return "\n\n".join(parts)


def suggest_entry(
    db: Session,
    *,
    categories: list[str],
    text: str,
    hours: Decimal | None,
    existing_titles: list[str],
) -> Suggestion:
    narrative = text.strip()
    if len(narrative) > 2000:
        raise TimeEntryError("O texto para a IA deve ter no máximo 2000 caracteres.")
    selected = _selected_categories(categories)
    if not selected:
        raise TimeEntryError("Marque ao menos uma ação para sugerir o texto.")
    prompt = build_suggestion_prompt(
        categories=selected,
        text=narrative,
        hours=hours,
        existing_titles=existing_titles,
    )
    ai = AiService(db)
    try:
        structured = ai.generate_structured(
            module="time_entries_suggest",
            user_content=prompt,
            schema_model=SuggestionAiModel,
            system_instruction=SUGGEST_INSTRUCTION,
            temperature=0.2,
            max_output_tokens=1200,
        )
        if isinstance(structured.parsed, SuggestionAiModel):
            return _from_structured(structured.parsed, informed_hours=hours, categories=selected)
    except AiConfigError as exc:
        raise TimeEntryError(
            "A integração de IA está desabilitada ou não configurada.",
            status_code=503,
        ) from exc
    except (AiError, ValidationError):
        pass

    try:
        result = ai.generate_text(
            module="time_entries_suggest",
            user_content=f"{prompt}\n\n{SUGGEST_TEXT_FALLBACK}",
            system_instruction=SUGGEST_INSTRUCTION,
            temperature=0.2,
            max_output_tokens=1200,
        )
    except AiConfigError as exc:
        raise TimeEntryError(
            "A integração de IA está desabilitada ou não configurada.",
            status_code=503,
        ) from exc
    except AiError as exc:
        raise TimeEntryError("Não foi possível sugerir o texto agora.", status_code=502) from exc
    return parse_suggestion(result.content or "", informed_hours=hours, categories=selected)


def _from_structured(
    model: SuggestionAiModel,
    *,
    informed_hours: Decimal | None,
    categories: list[str],
) -> Suggestion:
    title = _clean(model.title)
    if _is_garbage_title(title):
        title = _fallback_title(categories)
    activities = _optional(model.activities)
    result = _optional(model.result)
    description = _strip_meta_lines(_clean(model.description))
    if not description:
        description = _fallback_description(categories, activities, result)
    composed = compose_description(description, activities, result)
    hours_value = q(informed_hours) if informed_hours is not None else None
    if hours_value is None and model.hours is not None:
        hours_value = q(Decimal(str(model.hours)))
    return Suggestion(
        title=title,
        description=composed,
        activities=activities,
        result=result,
        hours=hours_value,
    )


def _fallback_title(categories: list[str]) -> str:
    if not categories:
        return "Atividades de gestão de projetos do NIA"
    if len(categories) == 1:
        return categories[0]
    if len(categories) <= 3:
        return ", ".join(categories)
    head = ", ".join(categories[:2])
    return f"{head} e demais frentes de gestão do NIA"


def _fallback_description(
    categories: list[str],
    activities: str | None,
    result: str | None,
) -> str:
    if activities:
        return compose_description(
            "Atividades de gerência de projetos do Núcleo de Inteligência Artificial.",
            activities,
            result,
        )
    if not categories:
        return "Atividades de gerência de projetos do Núcleo de Inteligência Artificial."
    listed = "\n".join(f"- {item}" for item in categories)
    return (
        "Atuação na gerência de projetos do Núcleo de Inteligência Artificial, contemplando:\n"
        f"{listed}"
    )


def _is_garbage_title(value: str) -> bool:
    text = (value or "").strip()
    if len(text) < 5:
        return True
    if text.casefold() in EMPTY_MARKERS:
        return True
    return bool(_GARBAGE_TITLE.search(text))


def _strip_meta_lines(value: str) -> str:
    lines: list[str] = []
    for line in (value or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _META_LINE.search(stripped):
            continue
        if stripped.casefold().startswith("check all"):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _selected_categories(categories: list[str]) -> list[str]:
    known = {item.casefold(): item for item in CATEGORIES}
    selected: list[str] = []
    for item in categories:
        canonical = known.get(item.strip().casefold())
        if canonical and canonical not in selected:
            selected.append(canonical)
    return selected


def _labeled_fields(raw: str) -> dict[str, str]:
    fields: dict[str, list[str]] = {}
    current: str | None = None
    for line in (raw or "").splitlines():
        label, value = _split_label(line)
        if label:
            current = label
            fields.setdefault(current, [])
            if value:
                fields[current].append(value)
            continue
        if current and line.strip():
            fields[current].append(line.strip())
    return {key: "\n".join(value).strip() for key, value in fields.items()}


def _split_label(line: str) -> tuple[str | None, str]:
    stripped = line.strip().lstrip("#").strip()
    if ":" not in stripped:
        return None, ""
    label, value = stripped.split(":", 1)
    normalized = label.strip().upper()
    canonical = {
        "TITLE": "TITULO",
        "DESCRIPTION": "DESCRICAO",
        "ACTIVITIES": "ATIVIDADES",
        "RESULT": "RESULTADO",
        "HOURS": "HORAS",
    }.get(normalized, normalized)
    if canonical not in FIELD_NAMES and normalized not in FIELD_NAMES:
        return None, ""
    return canonical if canonical in FIELD_NAMES else normalized, value.strip()


def _clean(value: str | None) -> str:
    text = (value or "").strip().strip('"')
    if text.casefold() in EMPTY_MARKERS:
        return ""
    return text


def _optional(value: str | None) -> str | None:
    text = _clean(value)
    return text or None

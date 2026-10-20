from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analysis.engine import is_weekend, month_days
from app.models import Collaborator, TimeEntryOperation, TimeEntrySettings
from app.services.analysis_context import load_calendar_exceptions_by_date, load_collaborator_absences
from app.services.csv_parser import normalize_name
from app.services.time_entries.azure import AzureIdentity, AzureTaskHit, CreatedTask, StoryInfo, TimeEntryAzure
from app.services.time_entries.conference import assert_executed_capacity, load_conference
from app.services.time_entries.dates import today_cuiaba, utc_now_naive
from app.services.time_entries.errors import (
    DuplicateHit,
    TimeEntryDuplicate,
    TimeEntryError,
    TimeEntryRejected,
    TimeEntryTransportError,
)
from app.services.time_entries.payload import (
    ADHERENCE_NOTE,
    DEFAULT_ATIVIDADE,
    DEFAULT_HOURS,
    DEFAULT_IMPEDIMENTO,
    CLOSED_TASK_STATE,
    DEFAULT_TIPO_TAREFA,
    clean_description,
    clean_title,
    ensure_reference_date,
    ensure_user_story,
    normalize_title,
    parse_hours,
    story_blocked_reason,
)
from app.services.ai.errors import AiConfigError, AiError
from app.services.ai.service import AiService

EXCEPTION_LABEL = {
    "holiday": "Feriado",
    "optional_day": "Ponto facultativo",
    "work_release": "Liberação de expediente",
}
ABSENCE_LABEL = {
    "medical_certificate": "Atestado médico",
    "vacation": "Férias",
    "day_off": "Folga",
    "leave": "Licença",
    "work_release": "Liberação de expediente",
    "other": "Ausência",
}

REWRITE_INSTRUCTION = (
    "Você reescreve apontamentos de atividades para o Azure Boards. "
    "Preserve o sentido original. Não invente reuniões, entregas, decisões, impedimentos "
    "nem atividades que não estejam no texto. Use linguagem profissional, clara e curta. "
    "Não use markdown. Devolva somente o texto reescrito."
)


@dataclass
class LaunchDefaults:
    task_type: str
    activity: str
    executed_hours: str
    impediment: str
    impediment_hours: str
    state: str
    assignee: str | None


@dataclass
class StoryBinding:
    id: int
    title: str
    state: str | None
    project: str
    area_path: str | None
    iteration_path: str | None
    url: str | None
    accessible: bool
    blocked_reason: str | None


@dataclass
class TimeEntryContext:
    azure_configured: bool
    azure_error: str | None
    projects: list[str]
    assignee_name: str | None
    suggested_hours: Decimal
    today: date
    story: StoryBinding | None
    defaults: LaunchDefaults
    adherence_note: str


@dataclass
class PreparedEntry:
    reference_date: date
    title: str
    description: str
    estimated_hours: Decimal


@dataclass
class EntryPreview:
    story_id: int
    story_title: str
    title: str
    description: str
    reference_date: date
    estimated_hours: Decimal
    task_type: str
    activity: str
    assignee: str
    state: str
    duplicates: list[DuplicateHit]


@dataclass
class RegisterResult:
    operation_key: str
    task_id: int | None
    title: str
    reference_date: date
    url: str | None
    already_registered: bool
    message: str
    estimated_hours: Decimal


@dataclass
class DayTask:
    task_id: int | None
    title: str
    estimated_hours: Decimal | None
    executed_hours: Decimal | None
    state: str | None
    url: str | None
    origin: str
    operation_status: str | None


@dataclass
class DayTasks:
    date: date
    azure_checked: bool
    azure_error: str | None
    tasks: list[DayTask]


@dataclass
class LastEntry:
    title: str
    description: str
    estimated_hours: Decimal
    reference_date: date


@dataclass
class CalendarDay:
    date: date
    weekend: bool
    exception_label: str | None
    exception_type: str | None
    absence_label: str | None
    suggested: bool
    launch_state: str | None = None
    status_label: str | None = None


@dataclass
class MonthCalendar:
    year: int
    month: int
    suggested_hours: Decimal
    days: list[CalendarDay]


@dataclass
class BatchItemResult:
    operation_key: str
    reference_date: date
    title: str
    description: str | None
    estimated_hours: Decimal | None
    status: str
    message: str
    task_id: int | None = None
    url: str | None = None
    duplicates: list[DuplicateHit] | None = None


@dataclass
class BatchResult:
    total: int
    created: int
    pending: int
    failed: int
    items: list[BatchItemResult]


def _settings(db: Session) -> TimeEntrySettings:
    row = db.get(TimeEntrySettings, 1)
    if row is None:
        row = TimeEntrySettings(id=1, suggested_hours=DEFAULT_HOURS, story_accessible=True)
        db.add(row)
        db.flush()
    return row


def _defaults(assignee: str | None) -> LaunchDefaults:
    return LaunchDefaults(
        task_type=DEFAULT_TIPO_TAREFA,
        activity=DEFAULT_ATIVIDADE,
        executed_hours="igual às horas estimadas",
        impediment=DEFAULT_IMPEDIMENTO,
        impediment_hours="vazio",
        state=CLOSED_TASK_STATE,
        assignee=assignee,
    )


def _binding_from_row(row: TimeEntrySettings) -> StoryBinding | None:
    if row.story_id is None or not row.story_project:
        return None
    return StoryBinding(
        id=row.story_id,
        title=row.story_title or f"User Story {row.story_id}",
        state=row.story_state,
        project=row.story_project,
        area_path=row.story_area_path,
        iteration_path=row.story_iteration_path,
        url=row.story_url,
        accessible=bool(row.story_accessible),
        blocked_reason=story_blocked_reason(row.story_state, accessible=bool(row.story_accessible)),
    )


def _apply_story(row: TimeEntrySettings, story: StoryInfo, *, accessible: bool = True) -> None:
    row.story_id = story.id
    row.story_title = story.title
    row.story_state = story.state
    row.story_project = story.project
    row.story_area_path = story.area_path or None
    row.story_iteration_path = story.iteration_path or None
    row.story_url = story.url
    row.story_accessible = accessible
    row.updated_at = utc_now_naive()


def _remember_identity(row: TimeEntrySettings, identity: AzureIdentity) -> None:
    row.azure_display_name = identity.display_name
    row.azure_unique_name = identity.unique_name
    row.azure_identity_id = identity.identity_id
    row.updated_at = utc_now_naive()


def _context(row: TimeEntrySettings, *, projects: list[str], azure_error: str | None, configured: bool) -> TimeEntryContext:
    hours = row.suggested_hours if row.suggested_hours is not None else DEFAULT_HOURS
    return TimeEntryContext(
        azure_configured=configured,
        azure_error=azure_error,
        projects=projects,
        assignee_name=row.azure_display_name,
        suggested_hours=hours,
        today=today_cuiaba(),
        story=_binding_from_row(row),
        defaults=_defaults(row.azure_display_name),
        adherence_note=ADHERENCE_NOTE,
    )


def load_context(db: Session, azure: TimeEntryAzure | None) -> TimeEntryContext:
    row = _settings(db)
    if azure is None:
        db.commit()
        return _context(row, projects=[], azure_error="Azure DevOps não configurado.", configured=False)

    azure_error: str | None = None
    try:
        identity = azure.identity()
        _remember_identity(row, identity)
    except TimeEntryError as exc:
        azure_error = exc.message

    if row.story_id is not None:
        try:
            story = azure.get_story(row.story_id)
            ensure_user_story(story.work_item_type, story.id)
            _apply_story(row, story, accessible=True)
        except TimeEntryError as exc:
            if exc.status_code == 404:
                row.story_accessible = False
                row.updated_at = utc_now_naive()
            elif azure_error is None:
                azure_error = exc.message
    db.commit()
    projects: list[str] = []
    try:
        projects = azure.projects()
    except Exception:
        projects = []
    return _context(row, projects=projects, azure_error=azure_error, configured=True)


def lookup_story(azure: TimeEntryAzure, story_id: int) -> StoryBinding:
    story = azure.get_story(story_id)
    ensure_user_story(story.work_item_type, story.id)
    return _binding_from_info(story)


def search_stories(azure: TimeEntryAzure, project: str, query: str) -> list[StoryBinding]:
    return [_binding_from_info(item) for item in azure.search_stories(project, query)]


def _binding_from_info(story: StoryInfo) -> StoryBinding:
    return StoryBinding(
        id=story.id,
        title=story.title,
        state=story.state,
        project=story.project,
        area_path=story.area_path or None,
        iteration_path=story.iteration_path or None,
        url=story.url,
        accessible=True,
        blocked_reason=story_blocked_reason(story.state, accessible=True),
    )


def save_story(db: Session, azure: TimeEntryAzure, story_id: int) -> TimeEntryContext:
    story = azure.get_story(story_id)
    ensure_user_story(story.work_item_type, story.id)
    if not story.area_path or not story.iteration_path:
        raise TimeEntryError("A User Story não possui Area Path ou Iteration Path.")
    row = _settings(db)
    try:
        _remember_identity(row, azure.identity())
    except TimeEntryError:
        if not row.azure_display_name:
            raise
    _apply_story(row, story, accessible=True)
    db.commit()
    return _context(row, projects=azure.projects(), azure_error=None, configured=True)


def clear_story(db: Session) -> TimeEntryContext:
    row = _settings(db)
    row.story_id = None
    row.story_title = None
    row.story_state = None
    row.story_project = None
    row.story_area_path = None
    row.story_iteration_path = None
    row.story_url = None
    row.story_accessible = True
    row.updated_at = utc_now_naive()
    db.commit()
    return _context(row, projects=[], azure_error=None, configured=True)


def _prepare(reference_date: date, title: str, description: str, estimated_hours: Decimal) -> PreparedEntry:
    return PreparedEntry(
        reference_date=ensure_reference_date(reference_date),
        title=clean_title(title),
        description=clean_description(description),
        estimated_hours=parse_hours(estimated_hours),
    )


def _require_open_story(db: Session, azure: TimeEntryAzure) -> tuple[TimeEntrySettings, StoryInfo, AzureIdentity]:
    row = _settings(db)
    if row.story_id is None:
        raise TimeEntryError("Vincule uma User Story antes de registrar atividades.")
    try:
        identity = azure.identity()
    except TimeEntryError:
        raise
    _remember_identity(row, identity)
    try:
        story = azure.get_story(row.story_id)
    except TimeEntryError as exc:
        if exc.status_code == 404:
            row.story_accessible = False
            row.updated_at = utc_now_naive()
            db.commit()
        raise
    ensure_user_story(story.work_item_type, story.id)
    _apply_story(row, story, accessible=True)
    reason = story_blocked_reason(story.state, accessible=True)
    if reason:
        db.commit()
        raise TimeEntryError(reason)
    if not story.area_path or not story.iteration_path:
        db.commit()
        raise TimeEntryError("A User Story não possui Area Path ou Iteration Path.")
    if not identity.display_name:
        raise TimeEntryError("Não foi possível identificar o responsável no Azure DevOps.")
    return row, story, identity


def parse_operation_key(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise TimeEntryError("Identificador da operação inválido.") from exc


def _operation_by_key(db: Session, key: str) -> TimeEntryOperation | None:
    return db.scalar(select(TimeEntryOperation).where(TimeEntryOperation.operation_key == key))


def _duplicate_from_operation(row: TimeEntryOperation) -> DuplicateHit:
    return DuplicateHit(
        task_id=row.task_id,
        title=row.title,
        reference_date=row.reference_date,
        estimated_hours=row.estimated_hours,
        origin="module",
    )


def _duplicate_from_azure(day: date, hit: AzureTaskHit) -> DuplicateHit:
    return DuplicateHit(
        task_id=hit.id,
        title=hit.title,
        reference_date=day,
        estimated_hours=hit.estimated_hours,
        origin="azure",
    )


def _find_duplicates(
    db: Session,
    azure: TimeEntryAzure,
    *,
    story: StoryInfo,
    prepared: PreparedEntry,
    ignore_operation_id: int | None,
) -> list[DuplicateHit]:
    target = normalize_title(prepared.title)
    found: list[DuplicateHit] = []
    seen: set[tuple[str, int | None]] = set()
    rows = db.scalars(
        select(TimeEntryOperation).where(
            TimeEntryOperation.story_id == story.id,
            TimeEntryOperation.reference_date == prepared.reference_date,
            TimeEntryOperation.status == "confirmed",
        )
    ).all()
    for row in rows:
        if ignore_operation_id is not None and row.id == ignore_operation_id:
            continue
        if normalize_title(row.title) != target:
            continue
        hit = _duplicate_from_operation(row)
        key = ("module", row.task_id or row.id)
        if key not in seen:
            seen.add(key)
            found.append(hit)
    try:
        remote = azure.tasks_between(
            project=story.project,
            story_id=story.id,
            start=prepared.reference_date,
            end=prepared.reference_date,
        )
    except TimeEntryError:
        return found
    known_ids = {item.task_id for item in found if item.task_id is not None}
    for day, hit in remote:
        if day != prepared.reference_date:
            continue
        if normalize_title(hit.title) != target or hit.id in known_ids:
            continue
        found.append(_duplicate_from_azure(prepared.reference_date, hit))
    return found


def _match_existing_task(
    azure: TimeEntryAzure,
    story: StoryInfo,
    row: TimeEntryOperation,
) -> AzureTaskHit | None:
    remote = azure.tasks_between(
        project=story.project,
        story_id=story.id,
        start=row.reference_date,
        end=row.reference_date,
    )
    target = normalize_title(row.title)
    for day, hit in remote:
        if day == row.reference_date and normalize_title(hit.title) == target:
            return hit
    return None


def _fill_operation(
    row: TimeEntryOperation,
    *,
    story: StoryInfo,
    prepared: PreparedEntry,
    assignee_name: str,
    justification: str | None,
) -> None:
    row.story_id = story.id
    row.story_title = story.title
    row.story_project = story.project
    row.reference_date = prepared.reference_date
    row.title = prepared.title
    row.description = prepared.description or None
    row.estimated_hours = prepared.estimated_hours
    row.assignee_name = assignee_name
    row.justification = (justification or "").strip()[:500] or None
    row.error_message = None


def _confirm_created(row: TimeEntryOperation, created: CreatedTask) -> None:
    row.status = "confirmed"
    row.task_id = created.id
    row.task_url = created.url
    row.task_state = created.state
    row.error_message = None
    row.submitted_at = utc_now_naive()


def _confirm_hit(row: TimeEntryOperation, hit: AzureTaskHit) -> None:
    row.status = "confirmed"
    row.task_id = hit.id
    row.task_url = hit.url
    row.task_state = hit.state
    row.error_message = None
    row.submitted_at = row.submitted_at or utc_now_naive()


def _result(row: TimeEntryOperation, *, already: bool, message: str) -> RegisterResult:
    return RegisterResult(
        operation_key=row.operation_key,
        task_id=row.task_id,
        title=row.title,
        reference_date=row.reference_date,
        url=row.task_url,
        already_registered=already,
        message=message,
        estimated_hours=row.estimated_hours,
    )


def preview_entry(
    db: Session,
    azure: TimeEntryAzure,
    *,
    reference_date: date,
    title: str,
    description: str,
    estimated_hours: Decimal,
) -> EntryPreview:
    prepared = _prepare(reference_date, title, description, estimated_hours)
    _row, story, identity = _require_open_story(db, azure)
    db.commit()
    duplicates = _find_duplicates(db, azure, story=story, prepared=prepared, ignore_operation_id=None)
    return EntryPreview(
        story_id=story.id,
        story_title=story.title,
        title=prepared.title,
        description=prepared.description,
        reference_date=prepared.reference_date,
        estimated_hours=prepared.estimated_hours,
        task_type=DEFAULT_TIPO_TAREFA,
        activity=DEFAULT_ATIVIDADE,
        assignee=identity.display_name,
        state=CLOSED_TASK_STATE,
        duplicates=duplicates,
    )


def register_entry(
    db: Session,
    azure: TimeEntryAzure,
    *,
    reference_date: date,
    title: str,
    description: str,
    estimated_hours: Decimal,
    operation_key: str,
    confirm: bool,
    acknowledge_duplicate: bool,
    justification: str | None,
) -> RegisterResult:
    if not confirm:
        raise TimeEntryError("Confirme o lançamento antes de registrar no Azure DevOps.")
    key = parse_operation_key(operation_key)
    existing = _operation_by_key(db, key)
    if existing and existing.status == "confirmed":
        return _result(
            existing,
            already=True,
            message="Esta atividade já havia sido registrada no Azure DevOps.",
        )
    prepared = _prepare(reference_date, title, description, estimated_hours)
    if existing and existing.status == "pending":
        age = utc_now_naive() - existing.created_at
        if age < timedelta(minutes=2):
            raise TimeEntryError(
                "Este lançamento já está em envio. Atualize o histórico antes de tentar de novo.",
                status_code=409,
            )

    row_settings, story, identity = _require_open_story(db, azure)
    azure.assert_task_defaults(story.project)
    del row_settings

    if existing and existing.status in {"uncertain", "pending"}:
        match = _match_existing_task(azure, story, existing)
        if match:
            _confirm_hit(existing, match)
            db.commit()
            return _result(
                existing,
                already=True,
                message="A Task já existia no Azure DevOps e foi confirmada no histórico.",
            )

    duplicates = _find_duplicates(
        db,
        azure,
        story=story,
        prepared=prepared,
        ignore_operation_id=existing.id if existing else None,
    )
    if duplicates and not acknowledge_duplicate:
        raise TimeEntryDuplicate(
            "Já existe um lançamento parecido nesta data. Confirme se deseja registrar outro.",
            duplicates,
        )
    if duplicates and not (justification or "").strip():
        raise TimeEntryError("Informe uma justificativa para registrar um lançamento distinto.")

    _ensure_executed_capacity(
        db,
        azure,
        identity.display_name,
        prepared.reference_date,
        added=prepared.estimated_hours,
    )

    row = existing or TimeEntryOperation(
        operation_key=key,
        status="pending",
        created_at=utc_now_naive(),
        story_id=story.id,
        reference_date=prepared.reference_date,
        title=prepared.title,
        estimated_hours=prepared.estimated_hours,
        assignee_name=identity.display_name,
    )
    _fill_operation(
        row,
        story=story,
        prepared=prepared,
        assignee_name=identity.display_name,
        justification=justification,
    )
    row.status = "pending"
    if existing is None:
        db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TimeEntryError(
            "Não foi possível iniciar o lançamento. Tente novamente.",
            status_code=409,
        ) from exc
    db.refresh(row)

    try:
        created = azure.create_task(
            project=story.project,
            title=prepared.title,
            description=prepared.description,
            reference_date=prepared.reference_date,
            estimated_hours=prepared.estimated_hours,
            assignee=identity.assigned_to,
            area_path=story.area_path,
            iteration_path=story.iteration_path,
            parent_id=story.id,
        )
    except TimeEntryTransportError as exc:
        row.status = "uncertain"
        row.error_message = exc.message[:500]
        db.commit()
        raise TimeEntryError(
            "Não foi possível confirmar o envio. O histórico marcou a operação como incerta. "
            "Ao repetir, o sistema consulta o Azure antes de criar outra Task.",
            status_code=503,
        ) from exc
    except TimeEntryRejected as exc:
        row.status = "failed"
        row.error_message = exc.message[:500]
        db.commit()
        raise TimeEntryError(exc.message) from exc

    _confirm_created(row, created)
    db.commit()
    return _result(row, already=False, message="Atividade registrada com sucesso no Azure DevOps.")


def day_tasks(db: Session, azure: TimeEntryAzure, day: date) -> DayTasks:
    row = _settings(db)
    local = db.scalars(
        select(TimeEntryOperation).where(TimeEntryOperation.reference_date == day)
    ).all()
    module_by_task = {item.task_id: item for item in local if item.task_id is not None}
    tasks: list[DayTask] = []
    azure_checked = False
    azure_error: str | None = None
    remote_ids: set[int] = set()

    if row.story_id is None:
        azure_error = (
            "Nenhuma User Story vinculada. A lista local não prova a ausência de atividades no Azure."
        )
    elif not row.story_accessible:
        azure_error = (
            "A User Story vinculada não está acessível. A lista local não prova a ausência de atividades no Azure."
        )
    elif row.story_project:
        try:
            remote = azure.tasks_between(
                project=row.story_project,
                story_id=row.story_id,
                start=day,
                end=day,
            )
            azure_checked = True
            for reference_day, hit in remote:
                if reference_day != day:
                    continue
                remote_ids.add(hit.id)
                operation = module_by_task.get(hit.id)
                tasks.append(
                    DayTask(
                        task_id=hit.id,
                        title=hit.title,
                        estimated_hours=hit.estimated_hours,
                        executed_hours=hit.executed_hours,
                        state=hit.state,
                        url=hit.url,
                        origin="module" if operation and operation.status == "confirmed" else "azure",
                        operation_status=operation.status if operation else None,
                    )
                )
        except TimeEntryError as exc:
            azure_error = exc.message

    for item in local:
        if item.task_id in remote_ids:
            continue
        if item.status not in {"confirmed", "uncertain", "failed", "pending"}:
            continue
        tasks.append(
            DayTask(
                task_id=item.task_id,
                title=item.title,
                estimated_hours=item.estimated_hours,
                executed_hours=None,
                state=item.task_state,
                url=item.task_url,
                origin="module",
                operation_status=item.status,
            )
        )
    tasks.sort(key=lambda item: (item.task_id or 0, item.title))
    return DayTasks(date=day, azure_checked=azure_checked, azure_error=azure_error, tasks=tasks)


def last_entry(db: Session) -> LastEntry:
    row = db.scalar(
        select(TimeEntryOperation)
        .where(TimeEntryOperation.status == "confirmed")
        .order_by(TimeEntryOperation.submitted_at.desc(), TimeEntryOperation.id.desc())
    )
    if row is None:
        raise TimeEntryError("Ainda não há lançamento confirmado para repetir.", status_code=404)
    return LastEntry(
        title=row.title,
        description=row.description or "",
        estimated_hours=row.estimated_hours,
        reference_date=row.reference_date,
    )


def improve_description(db: Session, text: str) -> str:
    source = text.strip()
    if not source:
        raise TimeEntryError("Informe o que foi realizado para melhorar a descrição.")
    if len(source) > 2000:
        raise TimeEntryError("O texto para a IA deve ter no máximo 2000 caracteres.")
    try:
        result = AiService(db).generate_text(
            module="time_entries_description",
            user_content=source,
            system_instruction=REWRITE_INSTRUCTION,
            temperature=0.2,
            max_output_tokens=400,
        )
    except AiConfigError as exc:
        raise TimeEntryError(
            "A integração de IA está desabilitada ou não configurada.",
            status_code=503,
        ) from exc
    except AiError as exc:
        raise TimeEntryError("Não foi possível melhorar a descrição agora.", status_code=502) from exc
    rewritten = (result.content or "").strip().strip('"')
    if not rewritten:
        raise TimeEntryError("A IA não retornou uma descrição. O texto original foi mantido.")
    return rewritten


def _ensure_executed_capacity(
    db: Session,
    azure: TimeEntryAzure,
    display_name: str,
    day: date,
    *,
    added: Decimal,
) -> None:
    collaborator = _collaborator_for_assignee(db, display_name)
    daily_hours = collaborator.daily_hours if collaborator is not None else Decimal("8")
    names = [display_name]
    if collaborator is not None:
        names.extend([collaborator.azure_name, collaborator.name])
    existing = azure.executed_hours_on(day, names)
    assert_executed_capacity(existing, added, daily_hours)


def _collaborator_for_assignee(db: Session, display_name: str | None) -> Collaborator | None:
    if not display_name:
        return None
    target = normalize_name(display_name)
    rows = db.scalars(select(Collaborator)).all()
    for row in rows:
        if normalize_name(row.azure_name) == target or normalize_name(row.name) == target:
            return row
    return None


def month_calendar(db: Session, year: int, month: int, *, azure: TimeEntryAzure | None = None) -> MonthCalendar:
    from app.services.time_entries.conference import launch_state_from_status

    row = _settings(db)
    exceptions = load_calendar_exceptions_by_date(db)
    collaborator = _collaborator_for_assignee(db, row.azure_display_name)
    absences = load_collaborator_absences(db).get(collaborator.id, {}) if collaborator else {}
    conference_days: dict[date, object] = {}
    if azure is not None:
        try:
            report = load_conference(db, azure, year, month)
            conference_days = {item.date: item for item in report.days}
        except TimeEntryError:
            conference_days = {}
    days: list[CalendarDay] = []
    for day in month_days(year, month):
        weekend = is_weekend(day)
        exception = exceptions.get(day)
        absence = absences.get(day)
        exception_label = EXCEPTION_LABEL.get(exception.type, exception.description) if exception else None
        exception_type = exception.type if exception else None
        absence_label = ABSENCE_LABEL.get(absence.type, "Ausência") if absence else None
        suggested = not weekend and exception is None and absence is None
        conference_day = conference_days.get(day)
        launch_state = None
        status_label = None
        if conference_day is not None:
            launch_state = launch_state_from_status(conference_day.status)
            status_label = conference_day.status_label
        days.append(
            CalendarDay(
                date=day,
                weekend=weekend,
                exception_label=exception_label,
                exception_type=exception_type,
                absence_label=absence_label,
                suggested=suggested,
                launch_state=launch_state,
                status_label=status_label,
            )
        )
    hours = row.suggested_hours if row.suggested_hours is not None else DEFAULT_HOURS
    return MonthCalendar(year=year, month=month, suggested_hours=hours, days=days)


def _batch_item(
    *,
    operation_key: str,
    prepared: PreparedEntry | None,
    reference_date: date,
    title: str,
    status: str,
    message: str,
    estimated_hours: Decimal | None = None,
    task_id: int | None = None,
    url: str | None = None,
    duplicates: list[DuplicateHit] | None = None,
) -> BatchItemResult:
    return BatchItemResult(
        operation_key=operation_key,
        reference_date=prepared.reference_date if prepared else reference_date,
        title=prepared.title if prepared else title,
        description=prepared.description if prepared else None,
        estimated_hours=prepared.estimated_hours if prepared else estimated_hours,
        status=status,
        message=message,
        task_id=task_id,
        url=url,
        duplicates=duplicates or [],
    )


def preview_batch(
    db: Session,
    azure: TimeEntryAzure,
    items: list[dict],
) -> list[BatchItemResult]:
    _row, story, _identity = _require_open_story(db, azure)
    db.commit()
    results: list[BatchItemResult] = []
    for item in items:
        key = str(item["operation_key"])
        try:
            prepared = _prepare(
                item["reference_date"],
                item["title"],
                item.get("description") or "",
                item["estimated_hours"],
            )
            parse_operation_key(key)
        except TimeEntryError as exc:
            results.append(
                _batch_item(
                    operation_key=key,
                    prepared=None,
                    reference_date=item["reference_date"],
                    title=str(item.get("title") or ""),
                    status="invalid",
                    message=exc.message,
                )
            )
            continue
        existing = _operation_by_key(db, key)
        if existing and existing.status == "confirmed":
            results.append(
                _batch_item(
                    operation_key=key,
                    prepared=prepared,
                    reference_date=prepared.reference_date,
                    title=prepared.title,
                    status="already_confirmed",
                    message="Já registrada. Não será enviada de novo.",
                    task_id=existing.task_id,
                    url=existing.task_url,
                )
            )
            continue
        duplicates = _find_duplicates(db, azure, story=story, prepared=prepared, ignore_operation_id=None)
        exceptional = _is_exceptional(db, prepared.reference_date)
        status = "duplicate" if duplicates else "ready"
        message = "Possível duplicidade." if duplicates else "Pronta para envio."
        if exceptional:
            message = f"{message} Data excepcional, fora do dia útil sugerido."
        results.append(
            _batch_item(
                operation_key=key,
                prepared=prepared,
                reference_date=prepared.reference_date,
                title=prepared.title,
                status=status,
                message=message,
                duplicates=duplicates,
            )
        )
    return results


def _is_exceptional(db: Session, day: date) -> bool:
    if is_weekend(day):
        return True
    if day in load_calendar_exceptions_by_date(db):
        return True
    row = _settings(db)
    collaborator = _collaborator_for_assignee(db, row.azure_display_name)
    if collaborator is None:
        return False
    return day in load_collaborator_absences(db).get(collaborator.id, {})


def register_batch(
    db: Session,
    azure: TimeEntryAzure,
    *,
    confirm: bool,
    items: list[dict],
) -> BatchResult:
    if not confirm:
        raise TimeEntryError("Confirme o lote antes de registrar no Azure DevOps.")
    results: list[BatchItemResult] = []
    created = 0
    pending = 0
    failed = 0
    for item in items:
        key = str(item["operation_key"])
        try:
            result = register_entry(
                db,
                azure,
                reference_date=item["reference_date"],
                title=item["title"],
                description=item.get("description") or "",
                estimated_hours=item["estimated_hours"],
                operation_key=key,
                confirm=True,
                acknowledge_duplicate=bool(item.get("acknowledge_duplicate")),
                justification=item.get("justification"),
            )
        except TimeEntryDuplicate as exc:
            pending += 1
            results.append(
                BatchItemResult(
                    operation_key=key,
                    reference_date=item["reference_date"],
                    title=str(item.get("title") or ""),
                    description=str(item.get("description") or "") or None,
                    estimated_hours=item.get("estimated_hours"),
                    status="duplicate",
                    message=exc.message,
                    duplicates=exc.duplicates,
                )
            )
            continue
        except TimeEntryError as exc:
            if exc.status_code >= 500:
                pending += 1
                status = "uncertain"
            else:
                failed += 1
                status = "failed"
            results.append(
                BatchItemResult(
                    operation_key=key,
                    reference_date=item["reference_date"],
                    title=str(item.get("title") or ""),
                    description=str(item.get("description") or "") or None,
                    estimated_hours=item.get("estimated_hours"),
                    status=status,
                    message=exc.message,
                )
            )
            continue
        created += 1
        results.append(
            BatchItemResult(
                operation_key=result.operation_key,
                reference_date=result.reference_date,
                title=result.title,
                description=None,
                estimated_hours=result.estimated_hours,
                status="already_confirmed" if result.already_registered else "confirmed",
                message=result.message,
                task_id=result.task_id,
                url=result.url,
            )
        )
    return BatchResult(
        total=len(items),
        created=created,
        pending=pending,
        failed=failed,
        items=results,
    )


def list_operations(
    db: Session,
    *,
    year: int | None,
    month: int | None,
    day: date | None,
    story_id: int | None,
    state: str | None,
    status: str | None,
) -> list[TimeEntryOperation]:
    query = select(TimeEntryOperation).order_by(
        TimeEntryOperation.reference_date.desc(),
        TimeEntryOperation.id.desc(),
    )
    if day is not None:
        query = query.where(TimeEntryOperation.reference_date == day)
    elif year is not None and month is not None:
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)
        query = query.where(
            TimeEntryOperation.reference_date >= start,
            TimeEntryOperation.reference_date < end,
        )
    elif year is not None:
        query = query.where(
            TimeEntryOperation.reference_date >= date(year, 1, 1),
            TimeEntryOperation.reference_date < date(year + 1, 1, 1),
        )
    if story_id is not None:
        query = query.where(TimeEntryOperation.story_id == story_id)
    if state:
        query = query.where(TimeEntryOperation.task_state == state)
    if status:
        query = query.where(TimeEntryOperation.status == status)
    return list(db.scalars(query.limit(500)).all())

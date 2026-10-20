from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    BatchItemResultOut,
    BatchPreviewOut,
    BatchRegisterIn,
    BatchRegisterOut,
    DayTasksOut,
    TimeEntryDayTaskOut,
    DuplicateHitOut,
    EntryPreviewOut,
    EntryRegisterIn,
    EntryRegisterOut,
    ConferenceOut,
    ConferenceDayOut,
    ConferenceTaskOut,
    ImproveDescriptionIn,
    ImproveDescriptionOut,
    SuggestIn,
    SuggestOut,
    LastEntryOut,
    StoryBindingOut,
    StoryLookupIn,
    StorySearchIn,
    TimeEntryCalendarOut,
    TimeEntryContextOut,
    TimeEntryOperationOut,
    CalendarDayOut,
    LaunchDefaultsOut,
)
from app.services.azure_devops_config import build_service, is_configured
from app.services.azure_devops_errors import AzureDevOpsConfigError
from app.services.time_entries.azure import TimeEntryAzure
from app.services.time_entries.errors import DuplicateHit, TimeEntryDuplicate, TimeEntryError
from app.services.time_entries.conference import ConferenceDay, ConferenceReport, ConferenceTask, load_conference
from app.services.time_entries.service import (
    BatchItemResult,
    BatchResult,
    CalendarDay,
    DayTask,
    DayTasks,
    EntryPreview,
    LaunchDefaults,
    LastEntry,
    MonthCalendar,
    RegisterResult,
    StoryBinding,
    TimeEntryContext,
    clear_story,
    day_tasks,
    improve_description,
    last_entry,
    list_operations,
    load_context,
    lookup_story,
    month_calendar,
    preview_batch,
    preview_entry,
    register_batch,
    register_entry,
    save_story,
    search_stories,
)
from app.services.time_entries.suggestions import suggest_entry

router = APIRouter(prefix="/time-entries", tags=["time-entries"])


def _conference(report: ConferenceReport) -> ConferenceOut:
    return ConferenceOut(
        year=report.year,
        month=report.month,
        checked_at=report.checked_at,
        assignee_name=report.assignee_name,
        daily_hours=report.daily_hours,
        collaborator_matched=report.collaborator_matched,
        adherence=report.adherence,
        expected_hours=report.expected_hours,
        recognized_hours=report.recognized_hours,
        estimated_hours=report.estimated_hours,
        executed_hours=report.executed_hours,
        obligatory_days=report.obligatory_days,
        complete_days=report.complete_days,
        incomplete_days=report.incomplete_days,
        missing_days=report.missing_days,
        excess_days=report.excess_days,
        dispensed_days=report.dispensed_days,
        missing_hours=report.missing_hours,
        pending=[_conference_day(item) for item in report.pending],
        days=[_conference_day(item) for item in report.days],
        empty_message=report.empty_message,
        executed_limit_note=report.executed_limit_note,
    )


def _conference_day(item: ConferenceDay) -> ConferenceDayOut:
    return ConferenceDayOut(
        date=item.date,
        estimated_hours=item.estimated_hours,
        executed_hours=item.executed_hours,
        recognized_hours=item.recognized_hours,
        missing_hours=item.missing_hours,
        expected_hours=item.expected_hours,
        status=item.status,
        status_label=item.status_label,
        hours_source=item.hours_source,
        hours_source_label=item.hours_source_label,
        suggested_hours=item.suggested_hours,
        pending=item.pending,
        tasks=[_conference_task(task) for task in item.tasks],
    )


def _conference_task(item: ConferenceTask) -> ConferenceTaskOut:
    return ConferenceTaskOut(
        task_id=item.task_id,
        title=item.title,
        state=item.state,
        estimated_hours=item.estimated_hours,
        executed_hours=item.executed_hours,
        url=item.url,
        project=item.project,
    )


def _http(exc: TimeEntryError) -> HTTPException:
    if isinstance(exc, TimeEntryDuplicate):
        return HTTPException(
            status_code=exc.status_code,
            detail={
                "message": exc.message,
                "duplicates": [_duplicate(item).model_dump(mode="json") for item in exc.duplicates],
            },
        )
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _gateway(db: Session) -> TimeEntryAzure:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Azure DevOps não configurado.")
    try:
        return TimeEntryAzure(build_service(db))
    except AzureDevOpsConfigError as exc:
        raise HTTPException(status_code=503, detail="Azure DevOps não configurado.") from exc


def _story(item: StoryBinding) -> StoryBindingOut:
    return StoryBindingOut(
        id=item.id,
        title=item.title,
        state=item.state,
        project=item.project,
        area_path=item.area_path,
        iteration_path=item.iteration_path,
        url=item.url,
        accessible=item.accessible,
        blocked_reason=item.blocked_reason,
    )


def _defaults(item: LaunchDefaults) -> LaunchDefaultsOut:
    return LaunchDefaultsOut(
        task_type=item.task_type,
        activity=item.activity,
        executed_hours=item.executed_hours,
        impediment=item.impediment,
        impediment_hours=item.impediment_hours,
        state=item.state,
        assignee=item.assignee,
    )


def _context(item: TimeEntryContext) -> TimeEntryContextOut:
    return TimeEntryContextOut(
        azure_configured=item.azure_configured,
        azure_error=item.azure_error,
        projects=item.projects,
        assignee_name=item.assignee_name,
        suggested_hours=item.suggested_hours,
        today=item.today,
        story=_story(item.story) if item.story else None,
        defaults=_defaults(item.defaults),
        adherence_note=item.adherence_note,
    )


def _duplicate(item: DuplicateHit) -> DuplicateHitOut:
    return DuplicateHitOut(
        task_id=item.task_id,
        title=item.title,
        reference_date=item.reference_date,
        estimated_hours=item.estimated_hours,
        origin=item.origin,
    )


def _preview(item: EntryPreview) -> EntryPreviewOut:
    return EntryPreviewOut(
        story_id=item.story_id,
        story_title=item.story_title,
        title=item.title,
        description=item.description,
        reference_date=item.reference_date,
        estimated_hours=item.estimated_hours,
        task_type=item.task_type,
        activity=item.activity,
        assignee=item.assignee,
        state=item.state,
        duplicates=[_duplicate(hit) for hit in item.duplicates],
    )


def _registered(item: RegisterResult) -> EntryRegisterOut:
    return EntryRegisterOut(
        operation_key=item.operation_key,
        task_id=item.task_id,
        title=item.title,
        reference_date=item.reference_date,
        url=item.url,
        already_registered=item.already_registered,
        message=item.message,
    )


def _day_task(item: DayTask) -> TimeEntryDayTaskOut:
    return TimeEntryDayTaskOut(
        task_id=item.task_id,
        title=item.title,
        estimated_hours=item.estimated_hours,
        executed_hours=item.executed_hours,
        state=item.state,
        url=item.url,
        origin=item.origin,  # type: ignore[arg-type]
        operation_status=item.operation_status,
    )


def _day(item: DayTasks) -> DayTasksOut:
    return DayTasksOut(
        date=item.date,
        azure_checked=item.azure_checked,
        azure_error=item.azure_error,
        tasks=[_day_task(task) for task in item.tasks],
    )


def _calendar_day(item: CalendarDay) -> CalendarDayOut:
    return CalendarDayOut(
        date=item.date,
        weekend=item.weekend,
        exception_label=item.exception_label,
        exception_type=item.exception_type,
        absence_label=item.absence_label,
        suggested=item.suggested,
        launch_state=item.launch_state,
        status_label=item.status_label,
    )


def _calendar(item: MonthCalendar) -> TimeEntryCalendarOut:
    return TimeEntryCalendarOut(
        year=item.year,
        month=item.month,
        suggested_hours=item.suggested_hours,
        days=[_calendar_day(day) for day in item.days],
    )


def _batch_item(item: BatchItemResult) -> BatchItemResultOut:
    return BatchItemResultOut(
        operation_key=item.operation_key,
        reference_date=item.reference_date,
        title=item.title,
        description=item.description,
        estimated_hours=item.estimated_hours,
        status=item.status,
        message=item.message,
        task_id=item.task_id,
        url=item.url,
        duplicates=[_duplicate(hit) for hit in (item.duplicates or [])],
    )


def _batch(item: BatchResult) -> BatchRegisterOut:
    return BatchRegisterOut(
        total=item.total,
        created=item.created,
        pending=item.pending,
        failed=item.failed,
        items=[_batch_item(row) for row in item.items],
    )


def _entry_dict(payload: EntryRegisterIn) -> dict:
    return {
        "operation_key": payload.operation_key,
        "reference_date": payload.reference_date,
        "title": payload.title,
        "description": payload.description,
        "estimated_hours": payload.estimated_hours,
        "acknowledge_duplicate": payload.acknowledge_duplicate,
        "justification": payload.justification,
    }


@router.get("/context", response_model=TimeEntryContextOut)
def get_context(db: Session = Depends(get_db)) -> TimeEntryContextOut:
    azure = None
    if is_configured(db):
        try:
            azure = TimeEntryAzure(build_service(db))
        except AzureDevOpsConfigError:
            azure = None
    try:
        return _context(load_context(db, azure))
    except TimeEntryError as exc:
        raise _http(exc) from exc


@router.post("/story/lookup", response_model=StoryBindingOut)
def post_story_lookup(payload: StoryLookupIn, db: Session = Depends(get_db)) -> StoryBindingOut:
    try:
        return _story(lookup_story(_gateway(db), payload.story_id))
    except TimeEntryError as exc:
        raise _http(exc) from exc


@router.post("/story/search", response_model=list[StoryBindingOut])
def post_story_search(payload: StorySearchIn, db: Session = Depends(get_db)) -> list[StoryBindingOut]:
    try:
        return [_story(item) for item in search_stories(_gateway(db), payload.project, payload.query)]
    except TimeEntryError as exc:
        raise _http(exc) from exc


@router.put("/story", response_model=TimeEntryContextOut)
def put_story(payload: StoryLookupIn, db: Session = Depends(get_db)) -> TimeEntryContextOut:
    try:
        return _context(save_story(db, _gateway(db), payload.story_id))
    except TimeEntryError as exc:
        raise _http(exc) from exc


@router.delete("/story", status_code=204)
def delete_story(db: Session = Depends(get_db)) -> Response:
    clear_story(db)
    return Response(status_code=204)


@router.post("/preview", response_model=EntryPreviewOut)
def post_preview(payload: EntryRegisterIn, db: Session = Depends(get_db)) -> EntryPreviewOut:
    try:
        return _preview(
            preview_entry(
                db,
                _gateway(db),
                reference_date=payload.reference_date,
                title=payload.title,
                description=payload.description,
                estimated_hours=payload.estimated_hours,
            )
        )
    except TimeEntryError as exc:
        raise _http(exc) from exc


@router.post("/register", response_model=EntryRegisterOut)
def post_register(payload: EntryRegisterIn, db: Session = Depends(get_db)) -> EntryRegisterOut:
    try:
        return _registered(
            register_entry(
                db,
                _gateway(db),
                reference_date=payload.reference_date,
                title=payload.title,
                description=payload.description,
                estimated_hours=payload.estimated_hours,
                operation_key=payload.operation_key,
                confirm=payload.confirm,
                acknowledge_duplicate=payload.acknowledge_duplicate,
                justification=payload.justification,
            )
        )
    except TimeEntryError as exc:
        raise _http(exc) from exc


@router.get("/day", response_model=DayTasksOut)
def get_day(day: date = Query(alias="date"), db: Session = Depends(get_db)) -> DayTasksOut:
    azure = None
    if is_configured(db):
        try:
            azure = TimeEntryAzure(build_service(db))
        except AzureDevOpsConfigError:
            azure = None
    if azure is None:
        raise HTTPException(status_code=503, detail="Azure DevOps não configurado.")
    try:
        return _day(day_tasks(db, azure, day))
    except TimeEntryError as exc:
        raise _http(exc) from exc


@router.get("/last", response_model=LastEntryOut)
def get_last(db: Session = Depends(get_db)) -> LastEntryOut:
    try:
        item: LastEntry = last_entry(db)
    except TimeEntryError as exc:
        raise _http(exc) from exc
    return LastEntryOut(
        title=item.title,
        description=item.description,
        estimated_hours=item.estimated_hours,
        reference_date=item.reference_date,
    )


@router.get("/conference", response_model=ConferenceOut)
def get_conference(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
) -> ConferenceOut:
    try:
        return _conference(load_conference(db, _gateway(db), year, month))
    except TimeEntryError as exc:
        raise _http(exc) from exc


@router.post("/suggest", response_model=SuggestOut)
def post_suggest(payload: SuggestIn, db: Session = Depends(get_db)) -> SuggestOut:
    try:
        item = suggest_entry(
            db,
            categories=payload.categories,
            text=payload.text,
            hours=payload.hours,
            existing_titles=payload.existing_titles,
        )
    except TimeEntryError as exc:
        raise _http(exc) from exc
    return SuggestOut(
        title=item.title,
        description=item.description,
        activities=item.activities,
        result=item.result,
        hours=item.hours,
    )


@router.post("/improve-description", response_model=ImproveDescriptionOut)
def post_improve(payload: ImproveDescriptionIn, db: Session = Depends(get_db)) -> ImproveDescriptionOut:
    try:
        return ImproveDescriptionOut(text=improve_description(db, payload.text))
    except TimeEntryError as exc:
        raise _http(exc) from exc


@router.get("/calendar", response_model=TimeEntryCalendarOut)
def get_calendar(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
) -> TimeEntryCalendarOut:
    azure = None
    if is_configured(db):
        try:
            azure = TimeEntryAzure(build_service(db))
        except AzureDevOpsConfigError:
            azure = None
    return _calendar(month_calendar(db, year, month, azure=azure))


@router.post("/batch/preview", response_model=BatchPreviewOut)
def post_batch_preview(payload: BatchRegisterIn, db: Session = Depends(get_db)) -> BatchPreviewOut:
    try:
        items = preview_batch(db, _gateway(db), [_entry_dict(item) for item in payload.items])
    except TimeEntryError as exc:
        raise _http(exc) from exc
    return BatchPreviewOut(items=[_batch_item(item) for item in items])


@router.post("/batch/register", response_model=BatchRegisterOut)
def post_batch_register(payload: BatchRegisterIn, db: Session = Depends(get_db)) -> BatchRegisterOut:
    try:
        return _batch(
            register_batch(
                db,
                _gateway(db),
                confirm=payload.confirm,
                items=[_entry_dict(item) for item in payload.items],
            )
        )
    except TimeEntryError as exc:
        raise _http(exc) from exc


@router.get("/operations", response_model=list[TimeEntryOperationOut])
def get_operations(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    day: date | None = Query(default=None, alias="date"),
    story_id: int | None = None,
    state: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[TimeEntryOperationOut]:
    rows = list_operations(
        db,
        year=year,
        month=month,
        day=day,
        story_id=story_id,
        state=state,
        status=status,
    )
    return [
        TimeEntryOperationOut(
            operation_key=row.operation_key,
            reference_date=row.reference_date,
            title=row.title,
            description=row.description,
            estimated_hours=row.estimated_hours,
            assignee_name=row.assignee_name,
            story_id=row.story_id,
            story_title=row.story_title,
            task_id=row.task_id,
            task_state=row.task_state,
            status=row.status,
            url=row.task_url,
            error_message=row.error_message,
            justification=row.justification,
            submitted_at=row.submitted_at,
        )
        for row in rows
    ]

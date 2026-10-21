from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.analysis.engine import AbsenceInput, ActivityInput, CollaboratorInput, executed_for_day, q
from app.services.time_entries.azure import (
    AzureIdentity,
    AzureTaskHit,
    CreatedTask,
    StoryInfo,
    month_task_wiql,
)
from app.services.time_entries.conference import (
    EMPTY_MESSAGE,
    assert_executed_capacity,
    build_conference,
    launch_state_from_status,
    matches_assignee,
    assignee_keys,
    LAUNCH_COMPLETE,
    LAUNCH_PENDING,
    LAUNCH_DISPENSED,
)
from app.services.time_entries.suggestions import (
    SUGGEST_INSTRUCTION,
    build_suggestion_prompt,
    parse_suggestion,
    suggest_entry,
)
from app.services.time_entries.dates import reference_datetime_utc, today_cuiaba
from app.services.time_entries.errors import TimeEntryDuplicate, TimeEntryError, TimeEntryTransportError
from app.services.time_entries.payload import (
    FIELD_ATIVIDADE,
    FIELD_HORAS_ESTIMADA,
    FIELD_HORAS_EXECUTADAS,
    FIELD_IMPEDIMENTO,
    FIELD_TIPO_TAREFA,
    build_task_document,
    ensure_reference_date,
    ensure_user_story,
    story_blocked_reason,
)
from app.models import Collaborator, TimeEntryOperation, TimeEntrySettings
from app.services.time_entries.service import preview_entry, register_entry, save_story

WORK_DATE = "Custom.6c8e390b-6368-45e4-ba7d-1b704368749b"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Collaborator.__table__.create(engine)
    TimeEntrySettings.__table__.create(engine)
    TimeEntryOperation.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_reference_datetime_uses_cuiaba_midnight() -> None:
    assert reference_datetime_utc(date(2026, 10, 20)) == "2026-10-20T04:00:00Z"
    moment = datetime(2026, 10, 21, 2, 30, tzinfo=timezone.utc)
    assert today_cuiaba(moment) == date(2026, 10, 20)


def test_task_document_uses_process_defaults_and_parent_link() -> None:
    document = build_task_document(
        title="Acompanhamento dos Projetos do Núcleo de IA",
        description="Alinhamento com a equipe.",
        reference_date=date(2026, 10, 20),
        estimated_hours=Decimal("8"),
        assignee="Pessoa <conta>",
        area_path="Inteligência Artificial\\NiaHub",
        iteration_path="Inteligência Artificial\\Sprint",
        work_date_field=WORK_DATE,
        parent_url="https://azure.example/_apis/wit/workItems/10",
    )
    by_path = {item["path"]: item["value"] for item in document}
    assert by_path["/fields/System.State"] == "New"
    assert by_path[f"/fields/{FIELD_TIPO_TAREFA}"] == "Projeto"
    assert by_path[f"/fields/{FIELD_ATIVIDADE}"] == "Gerência"
    assert by_path[f"/fields/{FIELD_HORAS_ESTIMADA}"] == 8.0
    assert by_path[f"/fields/{FIELD_HORAS_EXECUTADAS}"] == 8.0
    assert by_path[f"/fields/{FIELD_IMPEDIMENTO}"] == "Não"
    assert by_path[f"/fields/{WORK_DATE}"] == "2026-10-20T04:00:00Z"
    assert "/fields/Custom.Horasimpedimento" not in by_path
    assert by_path["/relations/-"]["rel"] == "System.LinkTypes.Hierarchy-Reverse"
    assert by_path["/relations/-"]["url"].endswith("/10")


def test_rejects_non_story_and_closed_story() -> None:
    with pytest.raises(TimeEntryError, match="não cria histórias"):
        ensure_user_story("Task", 15)
    assert story_blocked_reason("Closed", accessible=True)
    assert story_blocked_reason("Removed", accessible=True)
    assert story_blocked_reason("Active", accessible=True) is None
    with pytest.raises(TimeEntryError, match="posterior"):
        ensure_reference_date(date(2026, 10, 21), today=date(2026, 10, 20))


def test_open_task_with_estimate_still_uses_presence_rule() -> None:
    task = ActivityInput(
        task_id="1",
        title="Acompanhamento",
        collaborator_id=1,
        work_date=date(2026, 10, 20),
        completed_hours=Decimal("0"),
        estimated_hours=Decimal("8"),
        state="New",
    )
    executed, source = executed_for_day([task], q(8))
    assert executed == Decimal("8.00")
    assert source == "presence"


class FakeAzure:
    def __init__(self, story: StoryInfo) -> None:
        self.story = story
        self.created: list[dict] = []
        self.tasks: list[tuple[date | None, AzureTaskHit]] = []
        self.fail_transport = False
        self.capacity_checked = False
        self.executed_on: dict[date, Decimal] = {}

    def projects(self) -> list[str]:
        return ["Inteligência Artificial"]

    def identity(self) -> AzureIdentity:
        return AzureIdentity("Joacil Amarante de Paula Junior", "conta", "id-1")

    def get_story(self, story_id: int) -> StoryInfo:
        if story_id != self.story.id:
            raise TimeEntryError(f"User Story {story_id} não encontrada no Azure DevOps.", status_code=404)
        return self.story

    def search_stories(self, project: str, query: str) -> list[StoryInfo]:
        if query.casefold() in self.story.title.casefold():
            return [self.story]
        return []

    def assert_task_defaults(self, project: str) -> None:
        return None

    def work_date_field(self) -> str:
        return WORK_DATE

    def create_task(self, **kwargs) -> CreatedTask:
        if self.fail_transport:
            raise TimeEntryTransportError("Tempo esgotado ao criar a Task no Azure DevOps.")
        self.created.append(kwargs)
        task_id = 9000 + len(self.created)
        return CreatedTask(id=task_id, title=kwargs["title"], state="Closed", url=f"https://azure.example/{task_id}")

    def tasks_between(self, **kwargs) -> list[tuple[date | None, AzureTaskHit]]:
        return list(self.tasks)

    def executed_hours_on(self, day: date, names: list[str]) -> Decimal:
        self.capacity_checked = True
        return self.executed_on.get(day, Decimal("0"))


def _story(**overrides) -> StoryInfo:
    data = dict(
        id=321,
        title="Gestão de Outubro",
        state="Active",
        work_item_type="User Story",
        project="Inteligência Artificial",
        area_path="Inteligência Artificial\\Núcleo",
        iteration_path="Inteligência Artificial\\2026",
        url="https://azure.example/321",
    )
    data.update(overrides)
    return StoryInfo(**data)


def test_story_binding_and_idempotent_register(db) -> None:
    azure = FakeAzure(_story())
    day = today_cuiaba()
    try:
        saved = save_story(db, azure, 321)
        assert saved.story is not None
        assert saved.story.id == 321
        assert saved.assignee_name == "Joacil Amarante de Paula Junior"

        key = str(uuid4())
        first = register_entry(
            db,
            azure,
            reference_date=day,
            title="Acompanhamento dos Projetos",
            description="Reunião com a equipe.",
            estimated_hours=Decimal("8"),
            operation_key=key,
            confirm=True,
            acknowledge_duplicate=False,
            justification=None,
        )
        assert first.task_id == 9001
        assert first.already_registered is False
        assert len(azure.created) == 1
        assert azure.created[0]["parent_id"] == 321
        assert azure.created[0]["assignee"].startswith("Joacil")

        second = register_entry(
            db,
            azure,
            reference_date=date(2026, 10, 20),
            title="Acompanhamento dos Projetos",
            description="Reunião com a equipe.",
            estimated_hours=Decimal("8"),
            operation_key=key,
            confirm=True,
            acknowledge_duplicate=False,
            justification=None,
        )
        assert second.already_registered is True
        assert len(azure.created) == 1
    finally:
        db.close()


def test_duplicate_requires_justification_and_distinct_launch_is_allowed(db) -> None:
    azure = FakeAzure(_story())
    day = today_cuiaba()
    try:
        save_story(db, azure, 321)
        register_entry(
            db,
            azure,
            reference_date=date(2026, 10, 20),
            title="Alinhamento de Prioridades",
            description="",
            estimated_hours=Decimal("8"),
            operation_key=str(uuid4()),
            confirm=True,
            acknowledge_duplicate=False,
            justification=None,
        )
        with pytest.raises(TimeEntryDuplicate):
            register_entry(
                db,
                azure,
                reference_date=date(2026, 10, 20),
                title="Alinhamento de Prioridades",
                description="Outra frente.",
                estimated_hours=Decimal("4"),
                operation_key=str(uuid4()),
                confirm=True,
                acknowledge_duplicate=False,
                justification=None,
            )
        created = register_entry(
            db,
            azure,
            reference_date=date(2026, 10, 20),
            title="Alinhamento de Prioridades",
            description="Outra frente.",
            estimated_hours=Decimal("4"),
            operation_key=str(uuid4()),
            confirm=True,
            acknowledge_duplicate=True,
            justification="Atividade distinta no mesmo dia.",
        )
        assert created.task_id == 9002
        assert len(azure.created) == 2
    finally:
        db.close()


def test_closed_story_blocks_creation_without_calling_azure(db) -> None:
    azure = FakeAzure(_story(state="Closed"))
    day = today_cuiaba()
    try:
        save_story(db, azure, 321)
        with pytest.raises(TimeEntryError, match="encerrada"):
            preview_entry(
                db,
                azure,
                reference_date=date(2026, 10, 20),
                title="Monitoramento",
                description="",
                estimated_hours=Decimal("8"),
            )
        assert azure.created == []
    finally:
        db.close()


def test_uncertain_retry_does_not_create_again_when_azure_already_has_the_task(db) -> None:
    azure = FakeAzure(_story())
    azure.fail_transport = True
    key = str(uuid4())
    day = today_cuiaba()
    try:
        save_story(db, azure, 321)
        with pytest.raises(TimeEntryError, match="incerta"):
            register_entry(
                db,
                azure,
                reference_date=date(2026, 10, 20),
                title="Monitoramento das Entregas",
                description="",
                estimated_hours=Decimal("8"),
                operation_key=key,
                confirm=True,
                acknowledge_duplicate=False,
                justification=None,
            )
        assert azure.created == []
        azure.fail_transport = False
        azure.tasks = [
            (
                day,
                AzureTaskHit(
                    id=4555,
                    title="Monitoramento das Entregas",
                    state="New",
                    estimated_hours=Decimal("8"),
                    executed_hours=Decimal("0"),
                    url="https://azure.example/4555",
                ),
            )
        ]
        recovered = register_entry(
            db,
            azure,
            reference_date=date(2026, 10, 20),
            title="Monitoramento das Entregas",
            description="",
            estimated_hours=Decimal("8"),
            operation_key=key,
            confirm=True,
            acknowledge_duplicate=False,
            justification=None,
        )
        assert recovered.task_id == 4555
        assert recovered.already_registered is True
        assert azure.created == []
    finally:
        db.close()


def test_assigned_to_uses_display_name_when_unique_is_cpf() -> None:
    identity = AzureIdentity("JOACIL AMARANTE DE PAULA JUNIOR", "04380529193", "guid-1")
    assert identity.assigned_to == "JOACIL AMARANTE DE PAULA JUNIOR"


def test_assigned_to_uses_combo_when_unique_is_email() -> None:
    identity = AzureIdentity("Joacil", "joacil@example.com", "guid-1")
    assert identity.assigned_to == "Joacil <joacil@example.com>"


def test_assigned_to_uses_combo_when_unique_is_domain_account() -> None:
    identity = AzureIdentity("Joacil", r"PJMT\04380529193", "guid-1")
    assert identity.assigned_to == r"Joacil <PJMT\04380529193>"


def test_launch_state_mapping_for_batch_calendar() -> None:
    assert launch_state_from_status("regular") == LAUNCH_COMPLETE
    assert launch_state_from_status("missing") == LAUNCH_PENDING
    assert launch_state_from_status("incomplete") == LAUNCH_PENDING
    assert launch_state_from_status("excess") == LAUNCH_PENDING
    assert launch_state_from_status("not_required") == LAUNCH_DISPENSED
    assert launch_state_from_status("justified_absence") == LAUNCH_DISPENSED


def test_month_query_is_not_limited_to_the_linked_story() -> None:
    query = month_task_wiql("Inteligência Artificial", WORK_DATE, date(2026, 10, 1), date(2026, 10, 31))
    assert "System.Parent" not in query
    assert "WorkItemType] = 'Task'" in query
    assert "2026-10-01" in query
    assert "2026-10-31" in query
    assert "Removed" in query


def test_assignee_match_uses_the_same_name_normalization() -> None:
    keys = assignee_keys(["Joacil Amarante de Paula Junior"])
    assert matches_assignee("JOACIL AMARANTE DE PAULA JUNIOR", keys)
    assert not matches_assignee("Outra Pessoa", keys)


def test_executed_capacity_rejects_only_positive_overage() -> None:
    assert_executed_capacity(Decimal("4"), Decimal("0"), Decimal("8"))
    assert_executed_capacity(Decimal("8"), Decimal("0"), Decimal("8"))
    assert_executed_capacity(Decimal("9"), Decimal("0"), Decimal("8"))
    assert_executed_capacity(Decimal("4"), Decimal("4"), Decimal("8"))
    with pytest.raises(TimeEntryError):
        assert_executed_capacity(Decimal("4"), Decimal("5"), Decimal("8"))
    with pytest.raises(TimeEntryError):
        assert_executed_capacity(Decimal("8"), Decimal("1"), Decimal("8"))


def test_register_respects_executed_capacity_when_the_day_already_has_four(db) -> None:
    azure = FakeAzure(_story())
    day = today_cuiaba()
    azure.executed_on[day] = Decimal("4")
    save_story(db, azure, 321)
    result = register_entry(
        db,
        azure,
        reference_date=day,
        title="Acompanhamento do dia",
        description="Atividade informada pelo usuário.",
        estimated_hours=Decimal("4"),
        operation_key=str(uuid4()),
        confirm=True,
        acknowledge_duplicate=False,
        justification=None,
    )
    assert result.task_id is not None
    assert azure.capacity_checked is True
    assert len(azure.created) == 1
    assert azure.created[0]["estimated_hours"] == Decimal("4")


def test_register_rejects_executed_overage_on_the_same_day(db) -> None:
    azure = FakeAzure(_story())
    day = today_cuiaba()
    azure.executed_on[day] = Decimal("6")
    save_story(db, azure, 321)
    with pytest.raises(TimeEntryError, match="As horas executadas"):
        register_entry(
            db,
            azure,
            reference_date=day,
            title="Mais quatro horas",
            description="Deveria estourar o teto.",
            estimated_hours=Decimal("4"),
            operation_key=str(uuid4()),
            confirm=True,
            acknowledge_duplicate=False,
            justification=None,
        )


def test_conference_classifies_the_month_without_changing_the_engine() -> None:
    today = date(2026, 10, 20)
    collaborator = CollaboratorInput(
        id=5,
        name="Joacil Amarante de Paula Junior",
        azure_name="JOACIL AMARANTE DE PAULA JUNIOR",
        start_date=date(2026, 1, 1),
        end_date=None,
        daily_hours=Decimal("8"),
        active=True,
    )
    activities = [
        _task("501", date(2026, 10, 5), completed=Decimal("0"), estimated=Decimal("6"), state="Closed"),
        _task("601", date(2026, 10, 6), completed=Decimal("2"), estimated=Decimal("3"), state="Active"),
        _task("602", date(2026, 10, 6), completed=Decimal("2"), estimated=Decimal("5"), state="Active"),
        _task("701", date(2026, 10, 7), completed=Decimal("10"), estimated=Decimal("8"), state="Active"),
        _task("1401", date(2026, 10, 14), completed=Decimal("8"), estimated=Decimal("8"), state="Closed"),
        _task("1501", date(2026, 10, 15), completed=Decimal("4"), estimated=Decimal("8"), state="Active"),
        _task("1901", date(2026, 10, 19), completed=Decimal("0"), estimated=Decimal("8"), state="New"),
    ]
    report = build_conference(
        activities=activities,
        collaborator=collaborator,
        exception_dates={date(2026, 10, 12)},
        absences={date(2026, 10, 13): AbsenceInput(type="vacation", note=None)},
        year=2026,
        month=10,
        today=today,
        assignee_name=collaborator.name,
        checked_at=datetime(2026, 10, 20, 21, 0),
        collaborator_matched=True,
    )
    pending = {item.date: item for item in report.pending}
    assert date(2026, 10, 21) not in pending
    assert _day(report, date(2026, 10, 21)).status == "not_required"
    assert date(2026, 10, 12) not in pending
    assert date(2026, 10, 13) not in pending
    assert _day(report, date(2026, 10, 13)).status == "justified_absence"
    assert date(2026, 10, 3) not in pending

    closed_estimate = _day(report, date(2026, 10, 5))
    assert closed_estimate.hours_source == "closed_estimate"
    assert closed_estimate.estimated_hours == Decimal("6.00")
    assert closed_estimate.executed_hours == Decimal("0.00")
    assert closed_estimate.recognized_hours == Decimal("6.00")
    assert closed_estimate.missing_hours == Decimal("2.00")
    assert closed_estimate.suggested_hours == Decimal("2.00")
    assert date(2026, 10, 5) in pending

    several = _day(report, date(2026, 10, 6))
    assert len(several.tasks) == 2
    assert several.estimated_hours == Decimal("8.00")
    assert several.executed_hours == Decimal("4.00")
    assert several.recognized_hours == Decimal("4.00")
    assert several.status == "incomplete"

    excess = pending[date(2026, 10, 7)]
    assert excess.status == "excess"
    assert excess.recognized_hours == Decimal("10.00")
    assert excess.missing_hours == Decimal("0.00")
    assert excess.suggested_hours == Decimal("0.00")

    complete = _day(report, date(2026, 10, 14))
    assert complete.status == "regular"
    assert complete.hours_source == "logged"
    assert complete.executed_hours == complete.recognized_hours == Decimal("8.00")
    assert date(2026, 10, 14) not in pending

    incomplete = pending[date(2026, 10, 15)]
    assert incomplete.recognized_hours == Decimal("4.00")
    assert incomplete.missing_hours == Decimal("4.00")
    assert incomplete.hours_source == "logged"

    missing = pending[date(2026, 10, 16)]
    assert missing.status == "missing"
    assert missing.tasks == []
    assert missing.recognized_hours == Decimal("0.00")
    assert missing.suggested_hours == Decimal("8.00")

    presence = _day(report, date(2026, 10, 19))
    assert presence.status == "regular"
    assert presence.hours_source == "presence"
    assert presence.estimated_hours == Decimal("8.00")
    assert presence.executed_hours == Decimal("0.00")
    assert presence.recognized_hours == Decimal("8.00")
    assert date(2026, 10, 19) not in pending

    assert report.pending == sorted(report.pending, key=lambda item: item.date)
    assert report.adherence <= Decimal("100")
    assert report.complete_days >= 2
    assert report.empty_message is None


def test_previous_month_stays_pending_and_a_future_month_does_not() -> None:
    collaborator = _joacil()
    previous = build_conference(
        activities=[],
        collaborator=collaborator,
        exception_dates=set(),
        absences={},
        year=2026,
        month=9,
        today=date(2026, 10, 20),
        assignee_name=collaborator.name,
        checked_at=datetime(2026, 10, 20, 12, 0),
        collaborator_matched=True,
    )
    assert date(2026, 9, 1) in {item.date for item in previous.pending}
    assert _day(previous, date(2026, 9, 5)).status == "not_required"
    assert previous.empty_message is None

    future = build_conference(
        activities=[],
        collaborator=collaborator,
        exception_dates=set(),
        absences={},
        year=2026,
        month=11,
        today=date(2026, 10, 20),
        assignee_name=collaborator.name,
        checked_at=datetime(2026, 10, 20, 12, 0),
        collaborator_matched=True,
    )
    assert future.pending == []
    assert future.empty_message == EMPTY_MESSAGE
    assert future.adherence == Decimal("100.00")


def test_suggestion_keeps_only_what_the_user_informed() -> None:
    raw = (
        "TÍTULO: Acompanhamento das entregas\n"
        "DESCRIÇÃO: Verificação informada pelo usuário.\n"
        "ATIVIDADES: vazio\n"
        "RESULTADO: vazio\n"
        "HORAS: 8\n"
    )
    parsed = parse_suggestion(raw, informed_hours=None)
    assert parsed.title == "Acompanhamento das entregas"
    assert parsed.activities is None
    assert parsed.result is None
    assert parsed.hours is None
    assert "8" not in parsed.description

    informed = parse_suggestion(
        "TÍTULO: Relatório\nDESCRIÇÃO: Texto.\nATIVIDADES: revisão do backlog\nRESULTADO: prioridades definidas\nHORAS: 8",
        informed_hours=Decimal("3"),
    )
    assert informed.hours == Decimal("3.00")
    assert informed.activities == "revisão do backlog"
    assert "Resultado:" in informed.description
    assert "prioridades definidas" in informed.description


def test_suggestion_prompt_separates_found_records_from_the_user_text() -> None:
    prompt = build_suggestion_prompt(
        categories=["Acompanhamento dos projetos"],
        text="Revisei as entregas da sprint.",
        hours=None,
        existing_titles=["Task já lançada"],
    )
    assert "Registros encontrados no Azure" in prompt
    assert "Task já lançada" in prompt
    assert "Revisei as entregas da sprint." in prompt
    assert "não são o relato do usuário" in prompt
    assert "modelos de redação" in prompt
    assert "Não trate atualização de Task como reunião" in SUGGEST_INSTRUCTION
    marked = build_suggestion_prompt(
        categories=["Acompanhamento dos projetos", "Organização de backlog"],
        text="",
        hours=None,
        existing_titles=[],
    )
    assert "Ações marcadas pelo usuário" in marked
    assert "Organização de backlog" in marked
    assert "Redija o texto somente a partir delas" in marked
    assert "gerente de projeto do Núcleo de Inteligência Artificial" in prompt
    assert "contexto genérico do NIA" in prompt


def test_fallback_description_adds_generic_nia_context() -> None:
    parsed = parse_suggestion(
        "TÍTULO: Atividades de gestão\nDESCRIÇÃO: Texto.\n",
        informed_hours=None,
        categories=[
            "Acompanhamento dos projetos",
            "Monitoramento de sprints",
            "Organização de backlog",
        ],
    )
    assert "Núcleo de Inteligência Artificial (NIA)" in parsed.description
    assert "contemplando" in parsed.description
    assert "monitoramento de sprints" in parsed.description
    assert "\n-" not in parsed.description


def test_mocked_suggestion_does_not_send_anything_to_azure(db, monkeypatch) -> None:
    captured: dict = {}

    class FakeAi:
        def __init__(self, _db) -> None:
            pass

        def generate_structured(self, **kwargs):
            captured.update(kwargs)
            from app.services.time_entries.suggestions import SuggestionAiModel

            return type(
                "Result",
                (),
                {
                    "parsed": SuggestionAiModel(
                        title="Acompanhamento informado",
                        description="Texto baseado no relato e nas ações marcadas pelo usuário.",
                        activities=None,
                        result=None,
                        hours=None,
                    )
                },
            )()

        def generate_text(self, **kwargs):
            raise AssertionError("generate_text should not run when structured succeeds")

    monkeypatch.setattr("app.services.time_entries.suggestions.AiService", FakeAi)
    suggestion = suggest_entry(
        db,
        categories=["Acompanhamento dos projetos"],
        text="Acompanhei as entregas da sprint.",
        hours=None,
        existing_titles=["Registro encontrado"],
    )
    assert suggestion.title == "Acompanhamento informado"
    assert suggestion.hours is None
    assert suggestion.activities is None
    assert "Registro encontrado" in captured["user_content"]
    assert "Acompanhei as entregas da sprint." in captured["user_content"]
    assert captured["module"] == "time_entries_suggest"


def test_suggestion_rejects_garbage_title_and_recovers_from_categories() -> None:
    raw = (
        "TÍTULO: empty: Yes.\n"
        "DESCRIÇÃO: Check all marked actions included in DESCRIÇÃO:\n"
        "- Monitoramento de\n"
        "ATIVIDADES: vazio\n"
        "RESULTADO: vazio\n"
        "HORAS: vazio\n"
    )
    parsed = parse_suggestion(
        raw,
        informed_hours=None,
        categories=["Monitoramento de sprints", "Planejamento e priorização"],
    )
    assert parsed.title == "Monitoramento de sprints, Planejamento e priorização"
    assert "monitoramento de sprints" in parsed.description.casefold()
    assert "(NIA)" in parsed.description
    assert "check all" not in parsed.description.casefold()


def _joacil() -> CollaboratorInput:
    return CollaboratorInput(
        id=5,
        name="Joacil Amarante de Paula Junior",
        azure_name="JOACIL AMARANTE DE PAULA JUNIOR",
        start_date=date(2026, 1, 1),
        end_date=None,
        daily_hours=Decimal("8"),
        active=True,
    )


def _task(
    task_id: str,
    work_date: date,
    *,
    completed: Decimal | None,
    estimated: Decimal | None,
    state: str,
) -> ActivityInput:
    return ActivityInput(
        task_id=task_id,
        title=f"Task {task_id}",
        collaborator_id=5,
        work_date=work_date,
        completed_hours=completed,
        estimated_hours=estimated,
        state=state,
    )


def _day(report, work_date: date):
    return next(item for item in report.days if item.date == work_date)

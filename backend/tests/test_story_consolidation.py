from types import SimpleNamespace

from app.services.project_tracking.story_consolidation import (
    INDICATOR_CRITERIA,
    SPRINT_IN_PROGRESS_STATES,
    StoryAppearance,
    appearances_from_stories,
    consolidate_appearances,
    consolidate_by_team,
    explicit_impediment_label,
)


def _story(**kwargs):
    defaults = dict(
        work_item_id=1,
        created_in_sprint=False,
        completed_in_sprint=False,
        added_after_start=False,
        state_at_cut="Active",
        impediment=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _appearance(**kwargs) -> StoryAppearance:
    defaults = dict(
        work_item_id=10,
        sprint_start="2026-10-01",
        sprint_name="Sprint 1",
        team_project="Inteligência Artificial",
        created_in_sprint=False,
        completed_in_sprint=False,
        added_after_start=False,
        state_at_cut="Active",
        impediment=None,
    )
    defaults.update(kwargs)
    return StoryAppearance(**defaults)


def test_same_story_in_two_sprints_counts_once() -> None:
    totals = consolidate_appearances(
        [
            _appearance(work_item_id=10, completed_in_sprint=True, state_at_cut="Closed"),
            _appearance(
                work_item_id=10,
                sprint_start="2026-10-15",
                sprint_name="Sprint 2",
                completed_in_sprint=True,
                state_at_cut="Closed",
            ),
            _appearance(work_item_id=11, state_at_cut="New"),
        ]
    )
    assert totals["stories_total"] == 2
    assert totals["stories_completed"] == 1
    assert totals["stories_in_progress"] == 1


def test_completion_in_any_sprint_keeps_story_out_of_pending() -> None:
    totals = consolidate_appearances(
        [
            _appearance(completed_in_sprint=True, state_at_cut="Closed"),
            _appearance(
                sprint_start="2026-10-20",
                sprint_name="Sprint 2",
                completed_in_sprint=False,
                state_at_cut="Active",
            ),
        ]
    )
    assert totals["stories_completed"] == 1
    assert totals["stories_in_progress"] == 0
    assert totals["stories_pending"] == 0


def test_latest_sprint_defines_open_bucket() -> None:
    totals = consolidate_appearances(
        [
            _appearance(state_at_cut="Active"),
            _appearance(
                sprint_start="2026-10-20",
                sprint_name="Sprint 2",
                state_at_cut="To Do",
            ),
        ]
    )
    assert totals["stories_in_progress"] == 0
    assert totals["stories_pending"] == 1


def test_created_and_added_after_start_are_or_across_sprints() -> None:
    totals = consolidate_appearances(
        [
            _appearance(created_in_sprint=True),
            _appearance(
                work_item_id=12,
                sprint_start="2026-10-20",
                added_after_start=True,
                state_at_cut="New",
            ),
        ]
    )
    assert totals["stories_created"] == 1
    assert totals["stories_added_after_start"] == 1


def test_already_done_is_not_pending() -> None:
    totals = consolidate_appearances([_appearance(state_at_cut="Closed")])
    assert totals["stories_total"] == 1
    assert totals["stories_completed"] == 0
    assert totals["stories_pending"] == 0
    assert totals["stories_already_done"] == 1


def test_explicit_impediment_counts_unique_story() -> None:
    totals = consolidate_appearances(
        [
            _appearance(impediment="Sim, impedimento de ambiente"),
            _appearance(sprint_start="2026-10-20", sprint_name="Sprint 2", impediment="não"),
            _appearance(work_item_id=11, impediment="none"),
            _appearance(work_item_id=12, impediment=""),
        ]
    )
    assert totals["impediments_identified"] == 1
    assert explicit_impediment_label("Não") is None
    assert explicit_impediment_label("Teve impedimento na homologação") == "Teve impedimento na homologação"


def test_removed_stories_stay_out_of_period_totals() -> None:
    appearances = appearances_from_stories(
        [_story(work_item_id=7, state_at_cut="Removed"), _story(work_item_id=8, state_at_cut="Active")],
        sprint_start="2026-10-01",
        sprint_name="Sprint 1",
        team_project="Inteligência Artificial",
    )
    assert [item.work_item_id for item in appearances] == [8]


def test_teams_do_not_share_story_counts() -> None:
    by_team = consolidate_by_team(
        [
            _appearance(work_item_id=1, team_project="A", completed_in_sprint=True, state_at_cut="Done"),
            _appearance(
                work_item_id=1,
                team_project="A",
                sprint_start="2026-10-15",
                completed_in_sprint=True,
                state_at_cut="Done",
            ),
            _appearance(work_item_id=2, team_project="B", state_at_cut="New"),
        ]
    )
    assert by_team["A"]["stories_completed"] == 1
    assert by_team["A"]["stories_total"] == 1
    assert by_team["B"]["stories_in_progress"] == 1


def test_sprint_screen_states_stay_narrow() -> None:
    assert "committed" not in SPRINT_IN_PROGRESS_STATES
    assert "active" in SPRINT_IN_PROGRESS_STATES
    keys = {item["key"] for item in INDICATOR_CRITERIA}
    assert "unique_period" in keys
    assert "impediments" in keys

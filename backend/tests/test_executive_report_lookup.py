from types import SimpleNamespace

from app.services.project_tracking.executive_report_job import pick_saved_report, same_sprint_selection


def _row(status: str, row_id: int):
    return SimpleNamespace(status=status, id=row_id)


def test_saved_report_prefers_in_progress_then_latest_success() -> None:
    newest_error = _row("error", 5)
    success = _row("success", 4)
    older = _row("success", 2)
    assert pick_saved_report([newest_error, success, older]) is success
    running = _row("running", 6)
    assert pick_saved_report([running, success]) is running
    assert pick_saved_report([newest_error]) is None
    assert pick_saved_report([]) is None


def test_sprint_selection_ignores_order() -> None:
    assert same_sprint_selection(["b", "a"], ["a", "b"])
    assert not same_sprint_selection(["a"], ["a", "b"])
    assert not same_sprint_selection([], ["a"])

from app.services.project_tracking.catalog import ProjectScope
from app.services.project_tracking.scope_settings import filter_scopes


def test_filter_scopes_removes_ignored_keys() -> None:
    scopes = [
        ProjectScope(key="P::*", label="P", team_project="P", area_path=None),
        ProjectScope(key="P::P\\A", label="A", team_project="P", area_path="P\\A"),
        ProjectScope(key="P::P\\B", label="B", team_project="P", area_path="P\\B"),
    ]
    filtered = filter_scopes(scopes, {"P::P\\A"})
    assert [item.key for item in filtered] == ["P::*", "P::P\\B"]

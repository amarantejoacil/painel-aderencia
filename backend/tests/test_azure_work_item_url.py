from app.services.azure_work_item_url import resolve_work_item_url


def test_resolve_work_item_url_builds_edit_link() -> None:
    url = resolve_work_item_url(
        base_url="https://azure-devops.example.test",
        organization="CTI",
        team_project="Gestão Gabinete",
        task_id="4999",
    )
    assert url == "https://azure-devops.example.test/CTI/Gest%C3%A3o%20Gabinete/_workitems/edit/4999"


def test_resolve_work_item_url_returns_none_without_project() -> None:
    assert resolve_work_item_url(base_url="https://x.test", organization="CTI", team_project=None, task_id="1") is None


def test_resolve_work_item_url_normalizes_area_path_backslash() -> None:
    url = resolve_work_item_url(
        base_url="https://azure-devops.example.test",
        organization="NucleoIA",
        team_project=r"Inteligência Artificial\NiaHub CIA",
        task_id="4999",
    )
    assert "Intelig%C3%AAncia%20Artificial/NiaHub%20CIA" in url
    assert "%5C" not in url

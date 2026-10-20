from app.services.project_tracking.sprint_scope import sprint_matches_area


def test_pan_area_matches_portal_iteration_folder() -> None:
    assert sprint_matches_area(
        sprint_path="Inteligência Artificial\\Portal de Atos Normativos - PAN\\2026\\PAN - Sprint 1",
        team_project="Inteligência Artificial",
        area_path="Inteligência Artificial\\PAN",
    )


def test_pan_area_does_not_match_niahub_sprint() -> None:
    assert not sprint_matches_area(
        sprint_path="Inteligência Artificial\\NiaHub\\2026\\NiaHub - Sprint 1 - Outubro - 2026",
        team_project="Inteligência Artificial",
        area_path="Inteligência Artificial\\PAN",
    )


def test_niahub_subarea_matches_subproduct_segment() -> None:
    assert sprint_matches_area(
        sprint_path=(
            "Inteligência Artificial\\NiaHub\\2026\\NiaHub - CategorizaIA\\"
            "NiaHub CategorizaIA - Sprint 1 - Outubro - 2026"
        ),
        team_project="Inteligência Artificial",
        area_path="Inteligência Artificial\\NiaHub - CategorizaIA",
    )


def test_protocolo_pav_area_matches_niahub_subproduct_sprint() -> None:
    assert sprint_matches_area(
        sprint_path=(
            "Inteligência Artificial\\NiaHub\\2026\\NiaHub - Protocolo PAV\\"
            "NiaHub - Protocolo PAV - Sprint 2 - Outubro - 2026"
        ),
        team_project="Inteligência Artificial",
        area_path="Inteligência Artificial\\Protocolo-PAV",
    )


def test_niahub_pan_does_not_match_categoriza_area() -> None:
    assert not sprint_matches_area(
        sprint_path=(
            "Inteligência Artificial\\NiaHub\\2026\\NiaHub - PAN\\"
            "NiaHub PAN - Sprint 1 - Outubro - 2026"
        ),
        team_project="Inteligência Artificial",
        area_path="Inteligência Artificial\\NiaHub - CategorizaIA",
    )

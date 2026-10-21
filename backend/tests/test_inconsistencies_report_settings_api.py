from app.services.inconsistencies_report_settings import (
    DEFAULT_COPY_INTRO_OK,
    DEFAULT_COPY_INTRO_REQUIRES_REVIEW,
    get_settings_view,
)


def test_inconsistencies_report_settings_defaults(client) -> None:
    response = client.get("/api/settings/inconsistencies-report")
    assert response.status_code == 200
    body = response.json()
    assert body["copy_intro_requires_review"] == DEFAULT_COPY_INTRO_REQUIRES_REVIEW
    assert body["copy_intro_ok"] == DEFAULT_COPY_INTRO_OK


def test_inconsistencies_report_settings_update(client) -> None:
    custom = "Olá, {primeiro_nome}. Verifique {periodo}."
    response = client.put(
        "/api/settings/inconsistencies-report",
        json={
            "copy_intro_requires_review": custom,
            "copy_intro_ok": "OK {nome_completo}",
        },
    )
    assert response.status_code == 200
    assert response.json()["copy_intro_requires_review"] == custom

    from tests.conftest import TestingSession

    db = TestingSession()
    try:
        view = get_settings_view(db)
        assert view.copy_intro_requires_review == custom
        assert view.copy_intro_ok == "OK {nome_completo}"
    finally:
        db.close()

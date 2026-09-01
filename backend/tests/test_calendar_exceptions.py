def test_update_calendar_exception(client) -> None:
    created = client.post(
        "/api/calendar-exceptions",
        json={"date": "2026-12-25", "type": "holiday", "description": "Natal"},
    )
    assert created.status_code == 201
    exception_id = created.json()["id"]

    updated = client.put(
        f"/api/calendar-exceptions/{exception_id}",
        json={"date": "2026-12-25", "type": "holiday", "description": "Natal — TJMT"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Natal — TJMT"


def test_update_calendar_exception_returns_404_for_unknown_id(client) -> None:
    response = client.put(
        "/api/calendar-exceptions/99999",
        json={"date": "2026-12-25", "type": "holiday", "description": "Natal"},
    )
    assert response.status_code == 404

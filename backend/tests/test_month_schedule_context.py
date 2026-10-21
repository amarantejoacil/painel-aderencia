def test_inconsistencies_report_includes_month_schedule(client) -> None:
    response = client.get("/api/inconsistencies-report?year=2026&month=10")
    assert response.status_code == 200
    body = response.json()
    assert "month_schedule" in body
    schedule = body["month_schedule"]
    assert "calendar_exceptions" in schedule
    assert "absences" in schedule
    assert "summary" in schedule
    assert "medical_certificate" in schedule["summary"]

from datetime import date
from decimal import Decimal

import pytest

from app.services.csv_parser import CsvValidationError, extract_assignee_name, parse_csv

SAMPLE = b"""Work Item Type,ID,Data refer\xc3\xaancia,Title,Assigned To,State
"Task","3846","03/08/2026 00:00:00","Onboarding","Alisson de Souza Louly <PJMT\\05172210121>","Closed"
"Task","3847","04/08/2026 00:00:00","Estudo","Alisson de Souza Louly <PJMT\\05172210121>","Closed"
"""

HOURS_CSV = b"""ID,Title,Assigned To,Data refer\xc3\xaancia,Completed Work,State
"10","Task A","Jo\xc3\xa3o Silva <PJMT\\1>","20/08/2026 00:00:00","3","Closed"
"11","Task B","Jo\xc3\xa3o Silva <PJMT\\1>","20/08/2026 00:00:00","5","Closed"
"""


def test_parse_relatorio_contrato() -> None:
    result = parse_csv(SAMPLE)
    assert len(result.activities) == 2
    first = result.activities[0]
    assert first.task_id == "3846"
    assert first.work_date == date(2026, 8, 3)
    assert first.assignee_name == "Alisson de Souza Louly"
    assert first.completed_hours is None
    assert any(item["kind"] == "hours_absent" for item in result.warnings)


def test_parse_hours_when_present() -> None:
    result = parse_csv(HOURS_CSV)
    assert [item.completed_hours for item in result.activities] == [Decimal("3.00"), Decimal("5.00")]


def test_missing_required_column() -> None:
    with pytest.raises(CsvValidationError) as exc:
        parse_csv(b"ID,Title,State,Extra\n1,Test,Closed,x\n")
    assert "colunas obrigat" in exc.value.message.lower()


def test_extract_assignee_name() -> None:
    assert extract_assignee_name("JOACIL AMARANTE DE PAULA JUNIOR <PJMT\\04380529193>") == (
        "JOACIL AMARANTE DE PAULA JUNIOR"
    )

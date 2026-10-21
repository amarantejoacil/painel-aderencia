from app.services.issue_audit.field_refs import (
    extract_planning_fields,
    format_tags,
    resolve_issue_work_item_fields,
)


def test_resolve_fields_by_portuguese_labels() -> None:
    catalog = [
        {"referenceName": "Custom.X1", "name": "Áreas Internas"},
        {"referenceName": "Custom.X2", "name": "Áreas Externa"},
        {"referenceName": "Custom.X3", "name": "Bucket"},
    ]
    resolved = resolve_issue_work_item_fields(catalog)
    assert resolved["mapping"]["areas_internas"] == "Custom.X1"
    assert resolved["mapping"]["areas_externa"] == "Custom.X2"
    assert resolved["mapping"]["bucket"] == "Custom.X3"
    assert "System.Tags" in resolved["refs"]


def test_extract_planning_fields_from_work_item() -> None:
    mapping = {
        "bucket": "Custom.X3",
        "areas_internas": "Custom.X1",
        "areas_externa": "Custom.X2",
    }
    fields = {
        "System.Tags": "DSI; Urgente",
        "Custom.X3": "Concluído",
        "Custom.X1": "DSI",
        "Custom.X2": None,
    }
    extracted = extract_planning_fields(fields, mapping)
    assert extracted["tags"] == "DSI; Urgente"
    assert extracted["bucket"] == "Concluído"
    assert extracted["areas_internas"] == "DSI"
    assert extracted["areas_externa"] == ""


def test_format_tags() -> None:
    assert format_tags("DSI; Outra") == "DSI; Outra"

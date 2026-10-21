from app.services.issue_audit.comment_storage import comment_storage_report, full_comments_exportable


def test_complete_storage_is_exportable() -> None:
    result = {
        "comments_analyzed": 3,
        "comments_storage_version": 1,
        "issues": [
            {
                "id": 1,
                "comment_count": 3,
                "comments": [{"text": "p1"}],
                "all_comments": [{"text": "a"}, {"text": "b"}, {"text": "p1"}],
            }
        ],
    }
    report = comment_storage_report(result)
    assert report["comments_stored_full"] == 3
    assert report["comments_stored_person"] == 1
    assert report["exportable_full"] is True
    ok, message = full_comments_exportable(result)
    assert ok is True
    assert message is None

from datetime import datetime, timezone

from app.services.project_tracking.revisions import (
    build_snapshots,
    completed_transition_in_range,
    snapshot_at,
)


def test_snapshot_at_picks_last_revision_before_moment() -> None:
    revisions = [
        {
            "rev": 1,
            "fields": {
                "System.ChangedDate": "2026-10-01T10:00:00Z",
                "System.State": "New",
                "System.IterationPath": "Proj\\Sprint 1",
            },
        },
        {
            "rev": 2,
            "fields": {
                "System.ChangedDate": "2026-10-10T10:00:00Z",
                "System.State": "Active",
                "System.IterationPath": "Proj\\Sprint 1",
            },
        },
    ]
    snapshots = build_snapshots(revisions)
    moment = datetime(2026, 10, 5, tzinfo=timezone.utc)
    snap = snapshot_at(snapshots, moment)
    assert snap is not None
    assert snap.state == "New"


def test_completed_transition_in_range() -> None:
    revisions = [
        {
            "rev": 1,
            "fields": {
                "System.ChangedDate": "2026-10-01T10:00:00Z",
                "System.State": "Active",
                "System.IterationPath": "Proj\\Sprint 1",
            },
        },
        {
            "rev": 2,
            "fields": {
                "System.ChangedDate": "2026-10-12T15:00:00Z",
                "System.State": "Closed",
                "System.IterationPath": "Proj\\Sprint 1",
            },
        },
    ]
    snapshots = build_snapshots(revisions)
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    done = completed_transition_in_range(snapshots, start, end)
    assert done is not None
    assert done.state == "Closed"

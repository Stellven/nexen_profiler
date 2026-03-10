from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.inference.recent import infer_recent
from app.signals.types import SignalData


def test_recent_window_strict():
    now = datetime.now(timezone.utc)
    events = {
        "e1": {"event_id": "e1", "timestamp": now - timedelta(days=1), "source": "write", "title": "recent"},
        "e2": {"event_id": "e2", "timestamp": now - timedelta(days=9), "source": "read", "title": "old"},
    }
    signals = [
        SignalData(
            signal_id="s1",
            event_id="e1",
            chunk_id=None,
            type="artifact",
            name="note",
            value={},
            confidence=1.0,
            evidence_spans=[],
            computed_by={},
        )
    ]
    recent = infer_recent("user", events, signals, now, window_days=7)
    assert len(recent) == 1
    assert recent[0].evidence_event_ids == ["e1"]

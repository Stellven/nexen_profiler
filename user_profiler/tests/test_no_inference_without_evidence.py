from __future__ import annotations

from datetime import datetime, timezone

from app.inference.types import InferenceItem
from app.profile.assemble import assemble_profile
from app.signals.types import SignalData


def test_no_inference_without_evidence():
    events = [{"event_id": "e1", "timestamp": datetime.now(timezone.utc)}]
    signals = []
    inferences = [
        InferenceItem(
            inference_id="inf1",
            category="interest",
            label="test",
            description="test",
            probability=None,
            confidence=0.5,
            time_frame={},
            evidence_event_ids=["e1"],
            evidence_signal_ids=[],
            method={},
        )
    ]
    profile = assemble_profile(datetime.now(timezone.utc), events, signals, [], inferences)
    assert profile.profile_view["interests"] == []

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
    profile = assemble_profile(datetime.now(timezone.utc), events, signals, [], inferences)
    assert profile.profile_view["interests"][0]["evidence"]["signal_ids"]

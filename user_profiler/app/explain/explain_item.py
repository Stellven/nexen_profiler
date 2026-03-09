from __future__ import annotations

from typing import Dict

from sqlalchemy.orm import Session

from app.storage.models import Inference, InferenceEventMap, InferenceSignalMap, Signal


def explain_item(session: Session, inference_id: str) -> Dict:
    inference = session.get(Inference, inference_id)
    if not inference:
        return {"error": "not_found"}
    signal_maps = session.query(InferenceSignalMap).filter_by(inference_id=inference_id).all()
    event_maps = session.query(InferenceEventMap).filter_by(inference_id=inference_id).all()
    signal_ids = [m.signal_id for m in signal_maps]
    signals = session.query(Signal).filter(Signal.signal_id.in_(signal_ids)).all() if signal_ids else []

    return {
        "inference_id": inference.inference_id,
        "category": inference.category,
        "label": inference.label,
        "description": inference.description,
        "method": inference.method_json,
        "signals": [
            {
                "signal_id": s.signal_id,
                "type": s.type,
                "name": s.name,
                "confidence": s.confidence,
                "evidence_spans": s.evidence_spans_json,
            }
            for s in signals
        ],
        "event_ids": [m.event_id for m in event_maps],
    }

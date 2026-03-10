from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dateutil import parser as dateparser

from app.ingestion.ingest_dirs import RawInput
from app.parsing.parse_code import parse_code
from app.parsing.parse_html import parse_html
from app.parsing.parse_ipynb import parse_ipynb
from app.parsing.parse_pdf import parse_pdf
from app.parsing.parse_text import parse_text
from app.pipeline.config import PipelineConfig


@dataclass
class EventData:
    event_id: str
    user_id: str
    source: str
    timestamp: datetime
    timestamp_quality: str
    uri: str
    title: Optional[str]
    content_type: str
    content_text: str
    metadata: Dict
    content_hash: str


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _event_id(source: str, uri: str, content_hash: str) -> str:
    base = f"{source}|{uri}|{content_hash}"
    return hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()


def _timestamp_from_mtime(path: Path) -> datetime:
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


def _parse_file(raw: RawInput) -> Dict:
    ext = raw.path.suffix.lower()
    if ext in {".html", ".htm"}:
        return parse_html(raw.path).__dict__
    if ext == ".pdf":
        return parse_pdf(raw.path).__dict__
    if ext == ".ipynb":
        return parse_ipynb(raw.path).__dict__
    if ext == ".py":
        return parse_code(raw.path).__dict__
    return parse_text(raw.path).__dict__


def normalize_events(config: PipelineConfig, raw_inputs: List[RawInput]) -> List[EventData]:
    events: List[EventData] = []

    for raw in raw_inputs:
        parsed = _parse_file(raw)
        content_text = parsed.get("text", "") or ""
        content_hash = _hash_text(content_text)
        event_id = _event_id(raw.source, str(raw.path), content_hash)
        timestamp = _timestamp_from_mtime(raw.path)
        metadata = parsed.get("metadata", {})
        parse_error = parsed.get("parse_error")
        if parse_error:
            metadata = dict(metadata)
            metadata["parse_error"] = parse_error
        events.append(
            EventData(
                event_id=event_id,
                user_id=config.user_id,
                source=raw.source,
                timestamp=timestamp,
                timestamp_quality="mtime",
                uri=str(raw.path),
                title=parsed.get("title"),
                content_type=raw.content_type,
                content_text=content_text,
                metadata=metadata,
                content_hash=content_hash,
            )
        )

    if config.browse_path and config.browse_path.exists():
        events.extend(_normalize_browse(config, config.browse_path))

    return events


def _normalize_browse(config: PipelineConfig, path: Path) -> List[EventData]:
    results: List[EventData] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader):
            timestamp_raw = row.get("timestamp")
            if not timestamp_raw:
                date_raw = row.get("date")
                time_raw = row.get("time")
                if date_raw and time_raw:
                    timestamp_raw = f"{date_raw} {time_raw}"
                else:
                    timestamp_raw = time_raw or date_raw
            if not timestamp_raw:
                continue
            try:
                ts = dateparser.parse(timestamp_raw)
                if not ts.tzinfo:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            url = row.get("url") or row.get("uri") or ""
            title = row.get("title") or ""
            content_text = title
            row_id = row.get("id") or row.get("order")
            row_key = f"{row_id}|{idx}" if row_id else str(idx)
            # Include timestamp and row index to avoid duplicate event_ids for repeated visits.
            content_hash = _hash_text(content_text + url + "|" + ts.isoformat() + "|" + row_key)
            event_id = _event_id("browse", url, content_hash)
            metadata = {"dwell_time": row.get("dwell_time"), "row_id": row_id, "row_index": idx}
            results.append(
                EventData(
                    event_id=event_id,
                    user_id=config.user_id,
                    source="browse",
                    timestamp=ts,
                    timestamp_quality="history",
                    uri=url,
                    title=title,
                    content_type="text/url",
                    content_text=content_text,
                    metadata=metadata,
                    content_hash=content_hash,
                )
            )
    return results

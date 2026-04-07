
from __future__ import annotations

from typing import Any, Dict, List, Optional

def build_timeline_read_model_v2(
    events: List[Dict[str, Any]],
    *,
    document_id: str,
    document_type: str,
    artifact_uri: Optional[str] = None,
) -> Dict[str, Any]:
    needs_review_count = sum(1 for e in events if e.get("review_state") != "auto_confirmed")

    read_events: List[Dict[str, Any]] = []
    for e in events:
        primary = (e.get("citations") or [{}])[0]
        read_events.append({
            "event_id": e["event_id"],
            "date_iso": e["date_iso"],
            "title": e["title"],
            "description": e["description"],
            "event_type": e["event_type"],
            "document_type": e["document_type"],
            "confidence": e.get("confidence"),
            "review_state": e.get("review_state"),
            "provenance_status": e.get("provenance_status"),
            "entities": e.get("entities", {}),
            "evidence_navigation": {
                "document_id": document_id,
                "artifact_uri": artifact_uri,
                "page": primary.get("page"),
                "bbox": primary.get("bbox"),
                "snippet": primary.get("snippet"),
            },
            "citations": e.get("citations", []),
        })

    return {
        "version": "timeline_read_model_v2",
        "document_id": document_id,
        "document_type": document_type,
        "artifact_uri": artifact_uri,
        "total_events": len(read_events),
        "needs_review_count": needs_review_count,
        "events": read_events,
    }

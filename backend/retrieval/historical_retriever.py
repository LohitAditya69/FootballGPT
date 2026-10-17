"""Train-only historical case similarity over recorded event metadata."""

from __future__ import annotations

import gzip
import json
import math
from pathlib import Path
from typing import Any, Iterable


def load_historical_index(path: str | Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _name(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("name")
    return value if isinstance(value, str) else None


def _outcome(event: dict) -> str | None:
    for key in ("pass", "shot", "duel", "interception", "ball_recovery", "dribble", "goalkeeper"):
        value = event.get(key)
        if isinstance(value, dict):
            out = value.get("outcome")
            if isinstance(out, dict) and out.get("name"):
                return out["name"]
    return event.get("event_outcome")


def _features(event: dict) -> dict[str, Any]:
    return {
        "event_type": _name(event.get("type")) or event.get("event_type"),
        "play_pattern": _name(event.get("play_pattern")) or event.get("play_pattern"),
        "location": event.get("location"),
        "event_outcome": _outcome(event),
        "under_pressure": event.get("under_pressure"),
        "counterpress": event.get("counterpress"),
    }


def _location_similarity(a: Any, b: Any) -> float | None:
    if not (isinstance(a, list) and isinstance(b, list) and len(a) >= 2 and len(b) >= 2):
        return None
    # StatsBomb pitch coordinates are 120 x 80. A smooth distance score avoids
    # a brittle same-cell threshold while remaining in the [0, 1] range.
    dx = (float(a[0]) - float(b[0])) / 120.0
    dy = (float(a[1]) - float(b[1])) / 80.0
    return math.exp(-3.0 * math.sqrt(dx * dx + dy * dy))


def _categorical_similarity(a: Any, b: Any) -> float | None:
    return None if a is None or b is None else float(str(a).casefold() == str(b).casefold())


def historical_similarity(query_event: dict, candidate: dict) -> tuple[float, dict[str, float]]:
    q, c = _features(query_event), _features(candidate)
    fields = {
        "event_type": (0.40, _categorical_similarity(q["event_type"], c["event_type"])),
        "play_pattern": (0.15, _categorical_similarity(q["play_pattern"], c["play_pattern"])),
        "location": (0.25, _location_similarity(q["location"], c["location"])),
        "event_outcome": (0.10, _categorical_similarity(q["event_outcome"], c["event_outcome"])),
        "under_pressure": (0.05, _categorical_similarity(q["under_pressure"], c["under_pressure"])),
        "counterpress": (0.05, _categorical_similarity(q["counterpress"], c["counterpress"])),
    }
    available = {k: (weight, score) for k, (weight, score) in fields.items() if score is not None}
    weight_sum = sum(weight for weight, _ in available.values())
    if weight_sum == 0:
        return 0.0, {}
    breakdown = {k: round(score, 6) for k, (_, score) in available.items()}
    score = sum(weight * value for weight, value in available.values()) / weight_sum
    return max(0.0, min(1.0, score)), breakdown


def retrieve_historical(
    query_event: dict,
    candidates: Iterable[dict],
    *,
    exclude_match_id: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Find similar train situations, mandatorily excluding the query match."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    if not exclude_match_id:
        raise ValueError("exclude_match_id is required to prevent match leakage")
    scored = []
    for row in candidates:
        if str(row.get("match_id")) == str(exclude_match_id):
            continue
        score, breakdown = historical_similarity(query_event, row)
        if score <= 0:
            continue
        scored.append((score, row, breakdown))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("case_id"))))
    return [{
        "evidence_id": f"historical:{row['case_id']}",
        "case_id": row["case_id"],
        "match_id": str(row["match_id"]),
        "team": row.get("team"),
        "opponent": row.get("opponent"),
        "timestamp": row.get("timestamp"),
        "event_type": row.get("event_type"),
        "play_pattern": row.get("play_pattern"),
        "location": row.get("location"),
        "formation": row.get("formation"),
        "historical_score": round(score, 6),
        "similarity_breakdown": breakdown,
        "source_split": "train",
        "provenance": row.get("provenance"),
    } for score, row, breakdown in scored[:top_k]]

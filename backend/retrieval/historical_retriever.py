"""Train-only historical case similarity over recorded event metadata."""

from __future__ import annotations

import gzip
import json
import math
import re
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


def _features(event: dict, *, candidate_record: bool = False) -> dict[str, Any]:
    under_pressure = event.get("under_pressure")
    counterpress = event.get("counterpress")
    # The compact train sample stores both flags as False when the source key
    # was absent. Preserve True evidence, but don't treat that lossy default as
    # an observed negative during candidate comparisons.
    if candidate_record and str(event.get("provenance", "")).startswith("StatsBomb-derived train case"):
        under_pressure = None if under_pressure is False else under_pressure
        counterpress = None if counterpress is False else counterpress
    return {
        "event_type": _name(event.get("type")) or event.get("event_type"),
        "play_pattern": _name(event.get("play_pattern")) or event.get("play_pattern"),
        "location": event.get("location"),
        "location_region": event.get("location_region"),
        "event_outcome": _outcome(event),
        "under_pressure": under_pressure,
        "counterpress": counterpress,
    }


def _location_similarity(a: Any, b: Any, region: Any = None) -> float | None:
    if region is not None:
        if not (isinstance(b, list) and len(b) >= 2):
            return None
        try:
            x = float(b[0])
        except (TypeError, ValueError):
            return None
        # Only the non-directional middle third is currently parsed from
        # question text. Team-relative zones need attacking direction metadata.
        if region == "middle_third":
            return float(40.0 <= x <= 80.0)
        return None
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
    q, c = _features(query_event), _features(candidate, candidate_record=True)
    query_fields = {
        "event_type": q["event_type"],
        "play_pattern": q["play_pattern"],
        "location": q["location"] if q["location"] is not None else q["location_region"],
        "event_outcome": q["event_outcome"],
        "under_pressure": q["under_pressure"],
        "counterpress": q["counterpress"],
    }
    query_feature_count = sum(value is not None for value in query_fields.values())
    fields = {
        "event_type": (0.40, _categorical_similarity(q["event_type"], c["event_type"])),
        "play_pattern": (0.15, _categorical_similarity(q["play_pattern"], c["play_pattern"])),
        "location": (0.25, _location_similarity(q["location"], c["location"], q["location_region"])),
        "event_outcome": (0.10, _categorical_similarity(q["event_outcome"], c["event_outcome"])),
        "under_pressure": (0.05, _categorical_similarity(q["under_pressure"], c["under_pressure"])),
        "counterpress": (0.05, _categorical_similarity(q["counterpress"], c["counterpress"])),
    }
    available = {k: (weight, score) for k, (weight, score) in fields.items() if score is not None}
    weight_sum = sum(weight for weight, _ in available.values())
    breakdown = {k: round(score, 6) for k, (_, score) in available.items()}
    breakdown.update({
        "available_weight": round(weight_sum, 6),
        "compared_feature_count": float(len(available)),
        "query_feature_count": float(query_feature_count),
        "feature_coverage": round(weight_sum, 6),
    })
    # Weights sum to 1.0. Missing dimensions contribute no score rather than
    # being renormalized away, so a single easy match cannot look perfect.
    score = sum(weight * value for weight, value in available.values())
    return max(0.0, min(1.0, score)), breakdown


def parse_question_to_event_query(question: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse a natural-language question into bounded event features for historical candidate retrieval.

    Extracts only fields present in StatsBomb candidate records:
    - event_type: Interception, Pass, Shot, Pressure, Substitution
    - play_pattern: From Counter, From Corner, From Free Kick, From Goal Kick, From Keeper, From Throw In, Regular Play
    - location: [x, y] coordinates
    - event_outcome: Incomplete, Goal, Blocked, Saved
    - under_pressure: bool
    - counterpress: bool

    Returns:
        (query_event_dict, unrepresentable_reason):
        - If query represents discrete on-ball event concepts: (dict, None)
        - If query represents unrecorded tactical concepts (off-ball runs, team shape, etc.)
          or no discrete on-ball event: (None, explanation)
    """
    if not question or not isinstance(question, str):
        return None, "Empty or invalid question text."

    ql = question.lower().strip()

    # Detect explicitly unrepresentable concepts (off-ball movement, team shape, compactness, abstract theory)
    unrepresentable_patterns = [
        r"\b(?:create space|creating space|open(?:ing)? space|off[- ]ball|blindside runs?|third[- ]man runs?)\b",
        r"\b(?:defensive block|low block|mid block|high block|compactness|team shape|rest defence|rest defense|zonal marking|man marking)\b",
        r"\b(?:motivation|leadership|psychology|mentality|culture|attitude)\b",
    ]
    has_unrepresentable = any(re.search(pat, ql) for pat in unrepresentable_patterns)

    # Detect discrete on-ball event type. General regain language is mapped to
    # Interception only as a narrow available-index proxy, not as an exact
    # synonym for all ways of winning possession.
    event_type = None
    explicit_interception = bool(re.search(r"\b(?:interception|intercepted|intercepting)\b", ql))
    generic_regain = bool(re.search(r"\b(?:winning the ball|won the ball|win the ball|ball recovery|recovering the ball|recovered the ball|regains?|regaining|regained|turnovers?)\b", ql))
    if explicit_interception or generic_regain:
        event_type = "Interception"
    elif re.search(r"\b(?:shots?|shooting|finish(?:ing)?|strike|attempt on goal|header on goal)\b", ql):
        event_type = "Shot"
    elif re.search(r"\b(?:pass(?:ing|es)?|cross(?:ing|es)?|through ball|build[- ]up|switch of play|delivery|cutbacks?)\b", ql):
        event_type = "Pass"
    elif re.search(r"\b(?:counterpress(?:ing)?|counter-press(?:ing)?|closing down)\b", ql) or (
        re.search(r"\b(?:press(?:ing)?|pressure)\b", ql) and not re.search(r"\bunder pressure\b", ql)
    ):
        event_type = "Pressure"
    elif re.search(r"\b(?:substitutions?|substitutes?)\b", ql):
        event_type = "Substitution"

    if not event_type:
        return (
            None,
            "The question does not specify a discrete on-ball event type recorded in StatsBomb event metadata; "
            "match situation retrieval was skipped.",
        )

    # If unrepresentable concept was present and no concrete on-ball turnover or set piece was the primary subject:
    if has_unrepresentable and not re.search(r"\b(?:interception|won the ball|winning the ball|regain|failed pass|turnover|corner|shot)\b", ql):
        return (
            None,
            "The question asks about off-ball movement, team shape, or structural organization not recorded in "
            "StatsBomb event metadata; no comparable match situations were retrieved.",
        )

    # Detect play pattern
    play_pattern = None
    if re.search(r"\b(?:counter(?:attack(?:ing)?)?|counter-attack(?:ing)?|transitions?|transitional|fast break|breakaway)\b", ql):
        play_pattern = "From Counter"
    elif re.search(r"\b(?:corners?|corner kick)\b", ql):
        play_pattern = "From Corner"
    elif re.search(r"\b(?:free[- ]kick|set[- ]piece|dead[- ]ball)\b", ql):
        play_pattern = "From Free Kick"
    elif re.search(r"\b(?:goal[- ]kick)\b", ql):
        play_pattern = "From Goal Kick"
    elif re.search(r"\b(?:throw[- ]in)\b", ql):
        play_pattern = "From Throw In"
    elif re.search(r"\b(?:goalkeeper distribution|keeper distribution|from the keeper)\b", ql):
        play_pattern = "From Keeper"
    elif re.search(r"\b(?:open play|regular play)\b", ql):
        play_pattern = "Regular Play"

    # Parse only a non-directional region. Never invent a point coordinate for
    # a broad phrase; team-relative zones are unknown without attack direction.
    location = None
    location_region = None
    unresolved_location = None
    if re.search(r"\b(?:midfield|middle third|center circle|central midfield|middle of the pitch)\b", ql):
        location_region = "middle_third"
    elif re.search(r"\b(?:defensive third|own third|own half|defensive half|deep in defence|deep in defense|final third|attacking third|opponent(?:'s)? half|in the box|penalty area|outside the box)\b", ql):
        unresolved_location = (
            "A team-relative or finer location cue was left unknown because the question parser has no resolved attacking direction or zone boundaries."
        )

    # Outcome
    event_outcome = None
    if re.search(r"\b(?:incomplete|failed pass|misplaced pass)\b", ql):
        event_outcome = "Incomplete"
    elif re.search(r"\b(?:scored?|goals?)\b", ql):
        event_outcome = "Goal"
    elif re.search(r"\b(?:blocked)\b", ql):
        event_outcome = "Blocked"
    elif re.search(r"\b(?:saved)\b", ql):
        event_outcome = "Saved"

    # Contextual flags
    under_pressure = True if re.search(r"\b(?:under pressure|tightly pressed|pressured|heavy pressure|pressed tightly)\b", ql) else None
    counterpress = True if re.search(r"\b(?:counterpress|counter-press)\b", ql) else None

    features: dict[str, Any] = {
        "event_type": event_type,
        "play_pattern": play_pattern,
        "location": location,
        "location_region": location_region,
        "event_outcome": event_outcome,
        "under_pressure": under_pressure,
        "counterpress": counterpress,
    }
    if generic_regain and not explicit_interception:
        features["event_type_scope"] = "regain_proxy"
    return features, unresolved_location


def retrieve_historical(
    query_event: dict,
    candidates: Iterable[dict],
    *,
    exclude_match_id: str | None = None,
    top_k: int = 5,
    min_score_threshold: float = 0.35,
) -> list[dict[str, Any]]:
    """Find similar train situations, optionally excluding a user match ID."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    scored = []
    for row in candidates:
        if exclude_match_id and str(row.get("match_id")) == str(exclude_match_id):
            continue
        score, breakdown = historical_similarity(query_event, row)
        if score < min_score_threshold:
            continue
        scored.append((score, row, breakdown))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("case_id"))))
    return [
        {
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
            "label": "similar recorded situation (train split, not UEFA coaching principle)",
            "provenance": row.get("provenance"),
        }
        for score, row, breakdown in scored[:top_k]
    ]

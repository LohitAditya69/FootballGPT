#!/usr/bin/env python3
"""
Build tactical decision-support cases from football match data.

This script is intentionally conservative:
- it does not invent facts that are not present in the input
- it accepts a flexible JSON structure
- it extracts tactical moments into inspectable case records

The script supports:
- a StatsBomb open-data folder containing `data/events`, `data/matches`, and `data/lineups`
- a single StatsBomb events JSON file
- a plain list of event dicts
- an object containing an `events` list

Minimal event fields the script understands:
- minute, second
- team, opponent, player
- type or event_type
- outcome
- period
- x, y, end_x, end_y
- possession_id
- formation
- score_for, score_against

The output is a JSON list of tactical cases. Each case includes:
- case_id
- match context
- trigger event
- evidence items
- candidate actions
- provenance

If your input schema differs, adapt the `get_*` helper functions first.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from contextlib import ExitStack
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


KEY_EVENT_TYPES = {
    "goal",
    "shot",
    "yellow_card",
    "red_card",
    "substitution",
    "turnover",
    "pressure",
    "ball_recovery",
    "interception",
    "counterpress",
    "foul",
    "corner",
    "free_kick",
    "penalty",
}


@dataclass
class EvidenceItem:
    evidence_id: str
    source_type: str
    description: str
    reliability: float
    payload: Dict[str, Any]


@dataclass
class CandidateAction:
    action_id: str
    label: str
    rationale: str
    risk: str
    expected_effect: str
    confidence: float


@dataclass
class TacticalCase:
    case_id: str
    match_id: str
    timestamp: str
    period: Any
    team: Optional[str]
    opponent: Optional[str]
    score_state: Dict[str, Any]
    tactical_state: Dict[str, Any]
    trigger_event: Dict[str, Any]
    evidence: List[EvidenceItem]
    candidate_actions: List[CandidateAction]
    provenance: Dict[str, Any]


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def save_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else value for key, value in row.items()})


def write_jsonl_record(handle, payload: Dict[str, Any]) -> None:
    handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    handle.flush()


def read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_json_file_safe(path: Path) -> Any:
    try:
        return read_json_file(path)
    except (json.JSONDecodeError, OSError):
        return None


def stable_hash_ratio(text: str) -> float:
    digest = hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def format_progress(current: int, total: int, label: str) -> str:
    if total <= 0:
        return f"{label}: {current}"
    percent = (current / total) * 100
    bar_width = 24
    filled = int(round(bar_width * current / total))
    filled = max(0, min(bar_width, filled))
    bar = "█" * filled + "░" * (bar_width - filled)
    return f"{label}: [{bar}] {percent:5.1f}% ({current}/{total})"


def report_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def nested_name(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        name = value.get("name")
        if name is not None:
            return str(name)
        value_id = value.get("id")
        if value_id is not None:
            return str(value_id)
    if value is None:
        return None
    return str(value)


def nested_id(value: Any) -> Optional[Any]:
    if isinstance(value, dict):
        if "id" in value:
            return value["id"]
    return value


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten the StatsBomb fields we care about into plain keys."""
    normalized = dict(event)

    event_type = event.get("type", event.get("event_type", event.get("name")))
    normalized["event_type"] = nested_name(event_type)
    normalized["event_type_id"] = nested_id(event_type)

    team = event.get("team")
    normalized["team_name"] = nested_name(team)
    normalized["team_id"] = nested_id(team)

    possession_team = event.get("possession_team")
    normalized["possession_team_name"] = nested_name(possession_team)
    normalized["possession_team_id"] = nested_id(possession_team)

    play_pattern = event.get("play_pattern")
    normalized["play_pattern_name"] = nested_name(play_pattern)
    normalized["play_pattern_id"] = nested_id(play_pattern)

    player = event.get("player")
    normalized["player_name"] = nested_name(player)
    normalized["player_id"] = nested_id(player)

    position = event.get("position")
    normalized["position_name"] = nested_name(position)
    normalized["position_id"] = nested_id(position)

    for key in [
        "pass",
        "shot",
        "carry",
        "dribble",
        "duel",
        "block",
        "interception",
        "clearance",
        "pressure",
        "goalkeeper",
        "substitution",
        "foul_committed",
        "foul_won",
        "miscontrol",
        "ball_recovery",
        "possession_team",
        "play_pattern",
    ]:
        value = event.get(key)
        if isinstance(value, dict):
            normalized[f"{key}_name"] = nested_name(value.get("name"))
            normalized[f"{key}_id"] = nested_id(value.get("id"))
        elif value is not None:
            normalized[f"{key}_value"] = value

    tactics = event.get("tactics")
    if isinstance(tactics, dict):
        normalized["formation"] = tactics.get("formation")
        if isinstance(tactics.get("lineup"), list):
            normalized["tactics_lineup"] = tactics["lineup"]

    if "period" not in normalized and isinstance(event.get("period"), dict):
        normalized["period"] = event["period"].get("number", event["period"].get("id"))

    if "timestamp" in event:
        normalized["timestamp"] = str(event["timestamp"])

    return normalized


def get_event_type(event: Dict[str, Any]) -> str:
    value = event.get("event_type", event.get("type", event.get("name", "")))
    if isinstance(value, dict):
        value = value.get("name", value.get("id", ""))
    return str(value).strip().lower()


def get_minute(event: Dict[str, Any]) -> int:
    try:
        return int(event.get("minute", 0))
    except (TypeError, ValueError):
        return 0


def get_second(event: Dict[str, Any]) -> int:
    try:
        return int(event.get("second", event.get("seconds", 0)))
    except (TypeError, ValueError):
        return 0


def event_timestamp(event: Dict[str, Any]) -> str:
    timestamp = event.get("timestamp")
    if timestamp:
        return str(timestamp)
    minute = get_minute(event)
    second = get_second(event)
    return f"{minute:02d}:{second:02d}"


def get_score_state(event: Dict[str, Any], match: Dict[str, Any]) -> Dict[str, Any]:
    home_team = match.get("home_team_name")
    away_team = match.get("away_team_name")
    home_score = event.get("home_score")
    away_score = event.get("away_score")
    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "team_score": event.get("team_score"),
        "opponent_score": event.get("opponent_score"),
    }


def get_tactical_state(event: Dict[str, Any], window_events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    formation = event.get("formation")
    if not formation:
        for past_event in reversed(window_events):
            formation = past_event.get("formation")
            if formation:
                break

    possession_id = event.get("possession_id", event.get("possession"))
    phase = event.get("phase")
    if not phase:
        phase = infer_phase(window_events)

    return {
        "formation": formation,
        "possession_id": possession_id,
        "possession_team": event.get("possession_team_name", event.get("possession_team")),
        "play_pattern": event.get("play_pattern_name", event.get("play_pattern")),
        "event_type": event.get("event_type", event.get("type")),
        "player": event.get("player_name", event.get("player")),
        "phase": phase,
        "field_zone": infer_field_zone(event),
        "tempo": infer_tempo(window_events),
        "location": event.get("location"),
    }


def infer_phase(events: Sequence[Dict[str, Any]]) -> str:
    counts = Counter(get_event_type(e) for e in events)
    if counts.get("shot", 0) > 0 or counts.get("goal", 0) > 0:
        return "final_third_attack"
    if counts.get("pressure", 0) + counts.get("counterpress", 0) > 1:
        return "defensive_transition"
    if counts.get("pass", 0) + counts.get("carry", 0) > 0:
        return "settled_possession"
    if counts.get("turnover", 0) + counts.get("interception", 0) > 0:
        return "transition"
    if any(str(e.get("play_pattern_name", "")).lower() == "regular play" for e in events):
        return "settled_possession"
    return "unknown"


def infer_field_zone(event: Dict[str, Any]) -> str:
    location = event.get("location")
    x = event.get("x")
    if x is None and isinstance(location, list) and location:
        x = location[0]
    if x is None:
        return "unknown"
    try:
        x_value = float(x)
    except (TypeError, ValueError):
        return "unknown"
    if x_value < 33:
        return "defensive_third"
    if x_value < 66:
        return "middle_third"
    return "attacking_third"


def infer_tempo(events: Sequence[Dict[str, Any]]) -> str:
    if len(events) >= 8:
        return "high"
    if len(events) >= 4:
        return "medium"
    return "low"


def is_key_event(event: Dict[str, Any]) -> bool:
    event_type = get_event_type(event)
    if event_type in {"starting xi", "half start"}:
        return False
    if event_type in KEY_EVENT_TYPES:
        return True
    if event_type == "pass" and str(event.get("play_pattern_name", "")).lower() == "from free kick":
        return True
    outcome = str(event.get("outcome", "")).strip().lower()
    return outcome in {"goal", "won", "successful", "red", "yellow"}


def window_for_event(events: Sequence[Dict[str, Any]], index: int, before: int = 5, after: int = 5) -> List[Dict[str, Any]]:
    start = max(0, index - before)
    end = min(len(events), index + after + 1)
    return list(events[start:end])


def evidence_from_window(events: Sequence[Dict[str, Any]], match_id: str, case_index: int) -> List[EvidenceItem]:
    items: List[EvidenceItem] = []
    for idx, event in enumerate(events):
        event_type = get_event_type(event)
        reliability = 0.9 if event_type in {"goal", "red_card", "yellow_card", "shot"} else 0.7
        details = event_type or "event"
        if event.get("team_name"):
            details = f"{details} by {event.get('team_name')}"
        if event.get("play_pattern_name"):
            details = f"{details} [{event.get('play_pattern_name')}]"
        items.append(
            EvidenceItem(
                evidence_id=f"{match_id}:e{case_index}:{idx}",
                source_type="match_event",
                description=f"{details} at {event_timestamp(event)}",
                reliability=reliability,
                payload=event,
            )
        )
        related = event.get("related_events")
        if isinstance(related, list) and related:
            items.append(
                EvidenceItem(
                    evidence_id=f"{match_id}:e{case_index}:{idx}:related",
                    source_type="related_events",
                    description=f"related event links for {event_timestamp(event)}",
                    reliability=0.6,
                    payload={"related_events": related},
                )
            )
    return items


def candidate_actions_from_context(event: Dict[str, Any], window_events: Sequence[Dict[str, Any]]) -> List[CandidateAction]:
    phase = infer_phase(window_events)
    field_zone = infer_field_zone(event)
    score_diff = score_difference(event)

    candidates: List[CandidateAction] = []
    if phase == "defensive_transition":
        candidates.append(
            CandidateAction(
                action_id="counterpress",
                label="Counterpress immediately",
                rationale="The nearby sequence suggests a turnover or loose transition moment.",
                risk="medium",
                expected_effect="Recover possession early and prevent a direct attack.",
                confidence=0.74,
            )
        )
        candidates.append(
            CandidateAction(
                action_id="drop_block",
                label="Drop into compact block",
                rationale="A safer option when the opponent has space after transition.",
                risk="low",
                expected_effect="Reduce central penetration and protect the back line.",
                confidence=0.67,
            )
        )
    elif phase == "settled_possession" and field_zone == "attacking_third":
        candidates.append(
            CandidateAction(
                action_id="switch_play",
                label="Switch play",
                rationale="The attack is settled and the ball is in an advanced zone.",
                risk="medium",
                expected_effect="Move the defense laterally and create a new entry lane.",
                confidence=0.71,
            )
        )
        candidates.append(
            CandidateAction(
                action_id="penetrate_half_space",
                label="Attack half-space",
                rationale="Useful when the opponent is compact centrally.",
                risk="medium",
                expected_effect="Create a shot or cut-back opportunity.",
                confidence=0.69,
            )
        )
    elif score_diff is not None and score_diff > 0:
        candidates.append(
            CandidateAction(
                action_id="protect_lead",
                label="Lower risk and protect lead",
                rationale="The team is ahead, so ball security and spacing matter more.",
                risk="low",
                expected_effect="Reduce transition exposure and slow the match down.",
                confidence=0.78,
            )
        )
    else:
        candidates.append(
            CandidateAction(
                action_id="maintain_shape",
                label="Maintain structure",
                rationale="No strong tactical trigger was detected from the input window.",
                risk="low",
                expected_effect="Keep team organization stable while the next action develops.",
                confidence=0.55,
            )
        )

    return candidates


def score_difference(event: Dict[str, Any]) -> Optional[int]:
    home_score = event.get("home_score")
    away_score = event.get("away_score")
    try:
        if home_score is None or away_score is None:
            return None
        return int(home_score) - int(away_score)
    except (TypeError, ValueError):
        return None


def infer_team_and_opponent(event: Dict[str, Any], match: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    team = event.get("team_name", event.get("team"))
    opponent = event.get("opponent")
    if team and opponent:
        return str(team), str(opponent)

    home_team = match.get("home_team_name")
    away_team = match.get("away_team_name")
    if team == home_team:
        return str(home_team), str(away_team) if away_team is not None else None
    if team == away_team:
        return str(away_team), str(home_team) if home_team is not None else None
    return (str(team) if team is not None else None, str(opponent) if opponent is not None else None)


def build_case(match: Dict[str, Any], events: Sequence[Dict[str, Any]], index: int) -> TacticalCase:
    event = events[index]
    window = window_for_event(events, index)
    team, opponent = infer_team_and_opponent(event, match)
    match_id = str(match.get("match_id", match.get("id", "unknown_match")))
    case_id = f"{match_id}:case:{index}"

    evidence = evidence_from_window(window, match_id, index)
    candidates = candidate_actions_from_context(event, window)

    return TacticalCase(
        case_id=case_id,
        match_id=match_id,
        timestamp=event_timestamp(event),
        period=event.get("period"),
        team=team,
        opponent=opponent,
        score_state=get_score_state(event, match),
        tactical_state=get_tactical_state(event, window),
        trigger_event=event,
        evidence=evidence,
        candidate_actions=candidates,
        provenance={
            "source": "input_json",
            "event_index": index,
            "window_size_before": 5,
            "window_size_after": 5,
        },
    )


def build_cases(payload: Dict[str, Any]) -> List[TacticalCase]:
    if isinstance(payload, list):
        match = {}
        events = payload
    else:
        match = payload.get("match", {})
        events = payload.get("events", payload if isinstance(payload.get("events"), list) else [])

    if not isinstance(events, list):
        raise ValueError("input must be a list of events or an object containing an events list")

    sorted_events = sorted(
        [normalize_event(e) for e in events if isinstance(e, dict)],
        key=lambda e: (get_minute(e), get_second(e)),
    )

    cases: List[TacticalCase] = []
    for index, event in enumerate(sorted_events):
        if is_key_event(event):
            cases.append(build_case(match, sorted_events, index))

    if not cases and sorted_events:
        middle_index = len(sorted_events) // 2
        cases.append(build_case(match, sorted_events, middle_index))

    return cases


def normalize_match(match: Dict[str, Any]) -> Dict[str, Any]:
    home_team = match.get("home_team", {}) if isinstance(match.get("home_team"), dict) else {}
    away_team = match.get("away_team", {}) if isinstance(match.get("away_team"), dict) else {}
    return {
        "match_id": match.get("match_id"),
        "match_date": match.get("match_date"),
        "competition_id": match.get("competition", {}).get("competition_id") if isinstance(match.get("competition"), dict) else None,
        "competition_name": match.get("competition", {}).get("competition_name") if isinstance(match.get("competition"), dict) else None,
        "season_id": match.get("season", {}).get("season_id") if isinstance(match.get("season"), dict) else None,
        "season_name": match.get("season", {}).get("season_name") if isinstance(match.get("season"), dict) else None,
        "home_team_name": home_team.get("home_team_name"),
        "home_team_id": home_team.get("home_team_id"),
        "away_team_name": away_team.get("away_team_name"),
        "away_team_id": away_team.get("away_team_id"),
        "home_score": match.get("home_score"),
        "away_score": match.get("away_score"),
        "match_status": match.get("match_status"),
    }


def load_matches_index(data_root: Path) -> Dict[str, Dict[str, Any]]:
    matches_dir = data_root / "data" / "matches"
    index: Dict[str, Dict[str, Any]] = {}
    if not matches_dir.exists():
        return index
    for path in sorted(matches_dir.rglob("*.json")):
        payload = read_json_file_safe(path)
        if isinstance(payload, list):
            for match in payload:
                if isinstance(match, dict) and match.get("match_id") is not None:
                    index[str(match["match_id"])] = normalize_match(match)
    return index


def load_lineups_index(data_root: Path) -> Dict[str, Any]:
    lineups_dir = data_root / "data" / "lineups"
    index: Dict[str, Any] = {}
    if not lineups_dir.exists():
        return index
    for path in sorted(lineups_dir.rglob("*.json")):
        match_id = path.stem
        payload = read_json_file_safe(path)
        if isinstance(payload, list):
            index[str(match_id)] = payload
    return index


def derive_score_timeline(events: Sequence[Dict[str, Any]], match: Dict[str, Any]) -> List[Tuple[Optional[int], Optional[int]]]:
    home_team = match.get("home_team_name")
    away_team = match.get("away_team_name")
    home_score = 0
    away_score = 0
    timeline: List[Tuple[Optional[int], Optional[int]]] = []

    for event in events:
        timeline.append((home_score, away_score))
        if get_event_type(event) == "shot":
            shot = event.get("shot", {})
            if isinstance(shot, dict):
                outcome = str(shot.get("outcome", {}).get("name", "")).lower()
                if outcome == "goal":
                    team_name = event.get("team_name")
                    if team_name == home_team:
                        home_score += 1
                    elif team_name == away_team:
                        away_score += 1
    return timeline


def enrich_score_state(events: Sequence[Dict[str, Any]], match: Dict[str, Any]) -> List[Dict[str, Any]]:
    timeline = derive_score_timeline(events, match)
    enriched: List[Dict[str, Any]] = []
    for event, (home_score, away_score) in zip(events, timeline):
        item = dict(event)
        item["home_score"] = home_score
        item["away_score"] = away_score
        if item.get("team_name") == match.get("home_team_name"):
            item["team_score"] = home_score
            item["opponent_score"] = away_score
        elif item.get("team_name") == match.get("away_team_name"):
            item["team_score"] = away_score
            item["opponent_score"] = home_score
        item["score_diff"] = home_score - away_score
        enriched.append(item)
    return enriched


def build_match_payload(match: Dict[str, Any], events: Sequence[Dict[str, Any]], lineups: Any = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "match": match,
        "events": list(events),
    }
    if lineups is not None:
        payload["lineups"] = lineups
    return payload


def tactical_case_to_flat_row(case: TacticalCase) -> Dict[str, Any]:
    score_state = case.score_state or {}
    tactical_state = case.tactical_state or {}
    trigger_event = case.trigger_event or {}
    provenance = case.provenance or {}
    return {
        "case_id": case.case_id,
        "match_id": case.match_id,
        "timestamp": case.timestamp,
        "period": case.period,
        "team": case.team,
        "opponent": case.opponent,
        "score_home": score_state.get("home_score"),
        "score_away": score_state.get("away_score"),
        "team_score": score_state.get("team_score"),
        "opponent_score": score_state.get("opponent_score"),
        "phase": tactical_state.get("phase"),
        "formation": tactical_state.get("formation"),
        "field_zone": tactical_state.get("field_zone"),
        "tempo": tactical_state.get("tempo"),
        "play_pattern": tactical_state.get("play_pattern"),
        "event_type": tactical_state.get("event_type"),
        "player": tactical_state.get("player"),
        "trigger_type": trigger_event.get("event_type"),
        "trigger_player": trigger_event.get("player_name"),
        "trigger_team": trigger_event.get("team_name"),
        "evidence_count": len(case.evidence),
        "candidate_count": len(case.candidate_actions),
        "source": provenance.get("source"),
        "event_index": provenance.get("event_index"),
    }


def maybe_save_excel(path: Path, cases: Sequence[TacticalCase], train_cases: Sequence[TacticalCase], test_cases: Sequence[TacticalCase]) -> bool:
    try:
        from openpyxl import Workbook
    except Exception:
        return False

    wb = Workbook()
    sheets = [
        ("cases", cases),
        ("train", train_cases),
        ("test", test_cases),
    ]
    first = True
    for sheet_name, records in sheets:
        ws = wb.active if first else wb.create_sheet(title=sheet_name)
        ws.title = sheet_name
        first = False
        rows = [tactical_case_to_flat_row(case) for case in records]
        if not rows:
            ws.append(["empty"])
            continue
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(header) for header in headers])
    wb.save(path)
    return True


def case_to_dict(case: TacticalCase) -> Dict[str, Any]:
    return asdict(case)


def write_streamed_case_outputs(output_dir: Path, cases: Sequence[TacticalCase], test_ratio: float) -> Dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {"cases": 0, "train": 0, "test": 0}
    with ExitStack() as stack:
        cases_handle = stack.enter_context((output_dir / "cases.jsonl").open("w", encoding="utf-8"))
        train_handle = stack.enter_context((output_dir / "train.jsonl").open("w", encoding="utf-8"))
        test_handle = stack.enter_context((output_dir / "test.jsonl").open("w", encoding="utf-8"))
        for case in cases:
            case_dict = case_to_dict(case)
            write_jsonl_record(cases_handle, case_dict)
            counts["cases"] += 1
            if stable_hash_ratio(case.match_id) < test_ratio:
                write_jsonl_record(test_handle, case_dict)
                counts["test"] += 1
            else:
                write_jsonl_record(train_handle, case_dict)
                counts["train"] += 1
    save_json(output_dir / "summary.json", counts)
    return counts


def build_cases_from_match_files(
    data_root: Path,
    match_id_filter: Optional[str] = None,
    max_matches: Optional[int] = None,
    test_ratio: float = 0.2,
    output_dir: Optional[Path] = None,
) -> List[TacticalCase]:
    matches_index = load_matches_index(data_root)
    lineups_index = load_lineups_index(data_root)
    events_dir = data_root / "data" / "events"
    if not events_dir.exists():
        raise FileNotFoundError(f"Could not find events directory at {events_dir}")

    event_files = sorted(events_dir.rglob("*.json"))
    if match_id_filter is not None:
        event_files = [p for p in event_files if p.stem == str(match_id_filter)]
    if max_matches is not None:
        event_files = event_files[:max_matches]

    collect_cases = output_dir is None
    all_cases: List[TacticalCase] = [] if collect_cases else []
    total_files = len(event_files)
    report_progress(f"Processing {total_files} match file(s)")
    streamed_counts = {"cases": 0, "train": 0, "test": 0}
    stream_handles = None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        stream_handles = {
            "cases": (output_dir / "cases.jsonl").open("w", encoding="utf-8"),
            "train": (output_dir / "train.jsonl").open("w", encoding="utf-8"),
            "test": (output_dir / "test.jsonl").open("w", encoding="utf-8"),
        }
    for index, event_path in enumerate(event_files, start=1):
        report_progress(format_progress(index, total_files, f"Match file {event_path.stem}"))
        raw_events = read_json_file_safe(event_path)
        if not isinstance(raw_events, list):
            report_progress(f"Skipping {event_path.stem}: unreadable or non-list JSON")
            continue
        match_id = event_path.stem
        match = matches_index.get(match_id, {"match_id": match_id})
        enriched_events = enrich_score_state([normalize_event(e) for e in raw_events if isinstance(e, dict)], match)
        lineups = lineups_index.get(match_id)
        payload = build_match_payload(match, enriched_events, lineups)
        match_cases = build_cases(payload)
        if collect_cases:
            all_cases.extend(match_cases)
        if stream_handles is not None:
            for case in match_cases:
                case_dict = case_to_dict(case)
                write_jsonl_record(stream_handles["cases"], case_dict)
                streamed_counts["cases"] += 1
                if stable_hash_ratio(case.match_id) < test_ratio:
                    write_jsonl_record(stream_handles["test"], case_dict)
                    streamed_counts["test"] += 1
                else:
                    write_jsonl_record(stream_handles["train"], case_dict)
                    streamed_counts["train"] += 1
        report_progress(f"Finished {match_id}: {len(match_cases)} cases")
    if stream_handles is not None:
        for handle in stream_handles.values():
            handle.close()
        save_json(output_dir / "summary.json", streamed_counts)
    report_progress(f"Completed {total_files} match file(s), {streamed_counts['cases'] if stream_handles is not None else len(all_cases)} total cases")
    return all_cases


def split_cases_by_match(cases: Sequence[TacticalCase], test_ratio: float = 0.2) -> Tuple[List[TacticalCase], List[TacticalCase]]:
    grouped: Dict[str, List[TacticalCase]] = {}
    for case in cases:
        grouped.setdefault(case.match_id, []).append(case)

    if not grouped:
        return [], []

    match_ids = sorted(grouped)
    test_match_ids = [match_id for match_id in match_ids if stable_hash_ratio(match_id) < test_ratio]

    if not test_match_ids and len(match_ids) >= 2:
        test_match_ids = [match_ids[-1]]

    train_match_ids = [match_id for match_id in match_ids if match_id not in test_match_ids]

    if not train_match_ids and len(match_ids) >= 2:
        train_match_ids = [match_ids[0]]
        test_match_ids = [match_id for match_id in match_ids if match_id not in train_match_ids]

    train_cases = [case for case in cases if case.match_id in train_match_ids]
    test_cases = [case for case in cases if case.match_id in test_match_ids]
    return train_cases, test_cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Build tactical cases from StatsBomb football data.")
    parser.add_argument("input", type=Path, help="Path to a StatsBomb data root, events JSON file, or JSON file containing events")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("cases_output"),
        help="Directory where streamed outputs will be written",
    )
    parser.add_argument("--match-id", help="Optional single match ID to process when input is a StatsBomb data root")
    parser.add_argument("--max-matches", type=int, help="Optional limit when processing a data root")
    parser.add_argument("--test-ratio", type=float, default=0.2, help="Fraction of matches to place in the test split")
    parser.add_argument("--skip-excel", action="store_true", help="Skip writing cases.xlsx even if openpyxl is available")
    args = parser.parse_args()

    if args.input.is_dir():
        cases = build_cases_from_match_files(
            args.input,
            match_id_filter=args.match_id,
            max_matches=args.max_matches,
            test_ratio=args.test_ratio,
            output_dir=args.output_dir,
        )
    else:
        payload = read_json_file(args.input)
        if isinstance(payload, list):
            match = {"match_id": args.input.stem}
            cases = build_cases(build_match_payload(match, enrich_score_state([normalize_event(e) for e in payload if isinstance(e, dict)], match)))
        elif isinstance(payload, dict) and isinstance(payload.get("events"), list):
            match = normalize_match(payload.get("match", {})) if isinstance(payload.get("match"), dict) else {}
            enriched_events = enrich_score_state([normalize_event(e) for e in payload["events"] if isinstance(e, dict)], match)
            cases = build_cases(build_match_payload(match, enriched_events, payload.get("lineups")))
        else:
            raise ValueError("Unsupported input. Provide a StatsBomb data folder, an events JSON list, or an object with an events list.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.input.is_dir():
        counts = write_streamed_case_outputs(args.output_dir, cases, test_ratio=args.test_ratio)
        report_progress(f"Completed 1 input file, {counts['cases']} total cases")
    elif not args.skip_excel:
        print("Excel export is skipped for streamed dataset runs to avoid holding all cases in memory.", file=sys.stderr)

    if not args.skip_excel and not args.input.is_dir():
        train_cases, test_cases = split_cases_by_match(cases, test_ratio=args.test_ratio)
        wrote_excel = maybe_save_excel(args.output_dir / "cases.xlsx", cases, train_cases, test_cases)
        if not wrote_excel:
            print("openpyxl is not installed, so cases.xlsx was skipped.", file=sys.stderr)


if __name__ == "__main__":
    main()

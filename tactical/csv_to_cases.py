from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd


# =========================================================
# PROJECT ROOT
# =========================================================

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import tactical_case_builder as tcb


# =========================================================
# VALUE CLEANING
# =========================================================

def clean_value(value: Any) -> Any:
    """
    Convert pandas/numpy values into normal Python values.

    Also attempts to convert stringified dictionaries/lists
    such as:

        "{'formation': 433}"

    into actual Python dictionaries.
    """

    # None
    if value is None:
        return None

    # pandas/numpy NaN
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    # numpy scalar → Python scalar
    if isinstance(value, np.generic):
        return value.item()

    # Dictionary
    if isinstance(value, dict):
        return {
            key: clean_value(val)
            for key, val in value.items()
        }

    # List
    if isinstance(value, list):
        return [
            clean_value(item)
            for item in value
        ]

    # String
    if isinstance(value, str):
        text = value.strip()

        if not text:
            return None

        if text.lower() == "nan":
            return None

        # Try parsing stringified dict/list.
        if text.startswith("{") or text.startswith("["):
            try:
                parsed = ast.literal_eval(text)
                return clean_value(parsed)
            except (ValueError, SyntaxError):
                pass

        return text

    return value


# =========================================================
# STATS BOMB REFERENCE OBJECT
# =========================================================

def make_reference(
    name: Any,
    object_id: Any,
) -> Any:
    """
    Reconstruct a StatsBomb-style reference object.

    Example:

        Canada + 1833

    becomes:

        {
            "id": 1833,
            "name": "Canada"
        }
    """

    name = clean_value(name)
    object_id = clean_value(object_id)

    if name is None and object_id is None:
        return None

    result: Dict[str, Any] = {}

    if object_id is not None:
        try:
            result["id"] = int(float(object_id))
        except (ValueError, TypeError):
            result["id"] = object_id

    if name is not None:
        result["name"] = str(name)

    return result


# =========================================================
# CSV ROW → STRUCTURED STATSBOMB EVENT
# =========================================================

def csv_row_to_event(
    row: pd.Series,
) -> Dict[str, Any]:
    """
    Convert one flattened CSV row into a structured
    StatsBomb-like event dictionary.
    """

    raw: Dict[str, Any] = {
        column: clean_value(row[column])
        for column in row.index
    }

    event: Dict[str, Any] = dict(raw)

    # -----------------------------------------------------
    # Core StatsBomb references
    # -----------------------------------------------------

    event["type"] = make_reference(
        raw.get("type"),
        raw.get("type_id"),
    )

    event["team"] = make_reference(
        raw.get("team"),
        raw.get("team_id"),
    )

    event["possession_team"] = make_reference(
        raw.get("possession_team"),
        raw.get("possession_team_id"),
    )

    event["play_pattern"] = make_reference(
        raw.get("play_pattern"),
        raw.get("play_pattern_id"),
    )

    event["player"] = make_reference(
        raw.get("player"),
        raw.get("player_id"),
    )

    event["position"] = make_reference(
        raw.get("position"),
        raw.get("position_id"),
    )

    # -----------------------------------------------------
    # Tactics
    # -----------------------------------------------------

    tactics = raw.get("tactics")

    if isinstance(tactics, dict):
        event["tactics"] = tactics
    else:
        event.pop("tactics", None)

    # -----------------------------------------------------
    # Nested event fields
    # -----------------------------------------------------

    structured_fields = [
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
        "related_events",
    ]

    for field in structured_fields:
        value = raw.get(field)

        if value is not None:
            event[field] = value

    return event


# =========================================================
# FORMATION PROPAGATION
# =========================================================

def propagate_formations(
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Propagate the latest known formation for every team
    through the match.

    StatsBomb usually provides formation information in
    Starting XI / tactical events rather than every event.

    Example:

        Canada → 4411
        Morocco → 433

    Once discovered, the formation is attached to later
    events involving that team.
    """

    team_formations: Dict[Any, Any] = {}

    for event in events:

        team = event.get("team")

        if not isinstance(team, dict):
            continue

        team_id = team.get("id")

        # ---------------------------------------------
        # Check whether this event provides a formation
        # ---------------------------------------------

        tactics = event.get("tactics")

        if isinstance(tactics, dict):

            formation = tactics.get("formation")

            if formation is not None:
                team_formations[team_id] = formation

        # ---------------------------------------------
        # Propagate previously known formation
        # ---------------------------------------------

        if team_id in team_formations:
            event["formation"] = team_formations[team_id]

    return events


# =========================================================
# LOAD CSV
# =========================================================

def load_csv_events(
    csv_path: Path,
) -> List[Dict[str, Any]]:
    """
    Load flattened StatsBomb CSV and convert it into
    structured events.
    """

    print(f"Reading CSV: {csv_path}")

    df = pd.read_csv(csv_path)

    print(f"Rows found: {len(df)}")

    events: List[Dict[str, Any]] = []

    for _, row in df.iterrows():

        event = csv_row_to_event(row)

        events.append(event)

    print(f"Converted events: {len(events)}")

    # -----------------------------------------------------
    # Propagate formation state
    # -----------------------------------------------------

    events = propagate_formations(events)

    return events


# =========================================================
# MATCH METADATA
# =========================================================

def infer_match_metadata(
    events: List[Dict[str, Any]],
    match_id: str,
) -> Dict[str, Any]:
    """
    Infer basic match metadata from event data.
    """

    teams: List[Dict[str, Any]] = []

    seen_ids = set()

    for event in events:

        team = event.get("team")

        if not isinstance(team, dict):
            continue

        team_id = team.get("id")
        team_name = team.get("name")

        key = (
            team_id
            if team_id is not None
            else team_name
        )

        if key in seen_ids:
            continue

        seen_ids.add(key)

        teams.append(
            {
                "id": team_id,
                "name": team_name,
            }
        )

        if len(teams) >= 2:
            break

    match: Dict[str, Any] = {
        "match_id": str(match_id)
    }

    if len(teams) >= 1:

        match["home_team_id"] = teams[0]["id"]
        match["home_team_name"] = teams[0]["name"]

    if len(teams) >= 2:

        match["away_team_id"] = teams[1]["id"]
        match["away_team_name"] = teams[1]["name"]

    return match


# =========================================================
# SAVE JSONL
# =========================================================

def save_jsonl(
    output_file: Path,
    cases: List[Any],
) -> None:
    """
    Save tactical cases as JSON Lines.
    """

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as handle:

        for case in cases:

            record = tcb.case_to_dict(case)

            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )


# =========================================================
# SAVE SUMMARY
# =========================================================

def save_summary(
    output_dir: Path,
    summary: Dict[str, Any],
) -> None:

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    with (
        output_dir / "summary.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            summary,
            handle,
            indent=2,
            ensure_ascii=False,
        )


# =========================================================
# BUILD CASES
# =========================================================

def build_tactical_cases(
    events: List[Dict[str, Any]],
    match: Dict[str, Any],
) -> List[Any]:
    """
    Feed structured events into the existing
    tactical_case_builder.py.
    """

    print("Normalizing events...")

    normalized_events = [
        tcb.normalize_event(event)
        for event in events
    ]

    print(
        f"Normalized events: "
        f"{len(normalized_events)}"
    )

    # ---------------------------------------------
    # Add score state
    # ---------------------------------------------

    print("Enriching score state...")

    enriched_events = tcb.enrich_score_state(
        normalized_events,
        match,
    )

    # ---------------------------------------------
    # Create match payload
    # ---------------------------------------------

    payload = tcb.build_match_payload(
        match,
        enriched_events,
    )

    # ---------------------------------------------
    # Generate tactical cases
    # ---------------------------------------------

    print("Building tactical cases...")

    cases = tcb.build_cases(payload)

    print(
        f"Generated cases: "
        f"{len(cases)}"
    )

    return cases


# =========================================================
# VALIDATION
# =========================================================

def validate_cases(
    cases: List[Any],
) -> Dict[str, Any]:
    """
    Basic quality checks for generated tactical cases.
    """

    total = len(cases)

    with_evidence = 0
    without_evidence = 0

    with_formation = 0
    without_formation = 0

    phase_counts: Dict[str, int] = {}
    zone_counts: Dict[str, int] = {}

    for case in cases:

        tactical_state = (
            case.tactical_state
            if case.tactical_state
            else {}
        )

        # ----------------------------
        # Evidence
        # ----------------------------

        if case.evidence:
            with_evidence += 1
        else:
            without_evidence += 1

        # ----------------------------
        # Formation
        # ----------------------------

        formation = tactical_state.get(
            "formation"
        )

        if formation is None:
            without_formation += 1
        else:
            with_formation += 1

        # ----------------------------
        # Phase
        # ----------------------------

        phase = tactical_state.get(
            "phase",
            "unknown",
        )

        phase_counts[phase] = (
            phase_counts.get(phase, 0)
            + 1
        )

        # ----------------------------
        # Zone
        # ----------------------------

        zone = tactical_state.get(
            "field_zone",
            "unknown",
        )

        zone_counts[zone] = (
            zone_counts.get(zone, 0)
            + 1
        )

    return {
        "total_cases": total,
        "with_evidence": with_evidence,
        "without_evidence": without_evidence,
        "with_formation": with_formation,
        "without_formation": without_formation,
        "phase_distribution": phase_counts,
        "zone_distribution": zone_counts,
    }


# =========================================================
# MAIN
# =========================================================

def main() -> None:

    if len(sys.argv) < 2:

        print(
            "\nUsage:\n"
            "  python tactical/csv_to_cases.py "
            "<csv_file> [output_dir]\n"
        )

        sys.exit(1)

    csv_path = Path(sys.argv[1])

    if not csv_path.exists():

        print(
            f"ERROR: File does not exist:\n"
            f"{csv_path}"
        )

        sys.exit(1)

    output_dir = (
        Path(sys.argv[2])
        if len(sys.argv) >= 3
        else Path(
            "data/processed/tactical_cases"
        )
    )

    print()
    print("=" * 70)
    print("FootballGPT - CSV → Tactical Cases")
    print("=" * 70)

    print(f"Input : {csv_path}")
    print(f"Output: {output_dir}")

    # =====================================================
    # STEP 1 — LOAD EVENTS
    # =====================================================

    print()
    print("[1/5] Loading StatsBomb CSV")

    events = load_csv_events(
        csv_path
    )

    if not events:

        print(
            "ERROR: No events were found."
        )

        sys.exit(1)

    # =====================================================
    # STEP 2 — MATCH METADATA
    # =====================================================

    print()
    print("[2/5] Building match metadata")

    match_id = csv_path.stem

    match = infer_match_metadata(
        events,
        match_id,
    )

    print(
        f"Match ID : "
        f"{match.get('match_id')}"
    )

    print(
        f"Home     : "
        f"{match.get('home_team_name')}"
    )

    print(
        f"Away     : "
        f"{match.get('away_team_name')}"
    )

    # =====================================================
    # STEP 3 — BUILD TACTICAL CASES
    # =====================================================

    print()
    print("[3/5] Building tactical cases")

    cases = build_tactical_cases(
        events,
        match,
    )

    if not cases:

        print(
            "ERROR: No tactical cases generated."
        )

        sys.exit(1)

    # =====================================================
    # STEP 4 — VALIDATION
    # =====================================================

    print()
    print("[4/5] Validating generated cases")

    validation = validate_cases(
        cases
    )

    print(
        f"Total cases       : "
        f"{validation['total_cases']}"
    )

    print(
        f"With evidence     : "
        f"{validation['with_evidence']}"
    )

    print(
        f"Without evidence  : "
        f"{validation['without_evidence']}"
    )

    print(
        f"With formation    : "
        f"{validation['with_formation']}"
    )

    print(
        f"Without formation : "
        f"{validation['without_formation']}"
    )

    print()
    print("Phase distribution:")

    for phase, count in sorted(
        validation["phase_distribution"].items(),
        key=lambda item: item[1],
        reverse=True,
    ):

        print(
            f"  {phase}: {count}"
        )

    print()
    print("Field-zone distribution:")

    for zone, count in sorted(
        validation["zone_distribution"].items(),
        key=lambda item: item[1],
        reverse=True,
    ):

        print(
            f"  {zone}: {count}"
        )

    # =====================================================
    # STEP 5 — SAVE
    # =====================================================

    print()
    print("[5/5] Saving output")

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    cases_file = (
        output_dir / "cases.jsonl"
    )

    save_jsonl(
        cases_file,
        cases,
    )

    summary = {
        "match_id": match_id,
        "source_file": str(csv_path),
        "event_count": len(events),
        "case_count": len(cases),
        "home_team": match.get(
            "home_team_name"
        ),
        "away_team": match.get(
            "away_team_name"
        ),
        "validation": validation,
    }

    save_summary(
        output_dir,
        summary,
    )

    # =====================================================
    # DONE
    # =====================================================

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)

    print(
        f"Events : {len(events)}"
    )

    print(
        f"Cases  : {len(cases)}"
    )

    print(
        f"Output : {cases_file}"
    )

    print()
    print(
        "Next step: inspect summary.json "
        "and verify formation coverage."
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()
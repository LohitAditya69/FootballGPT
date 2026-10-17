#!/usr/bin/env python3
"""Deterministically sample a bounded, match-stratified train-only case index."""

from __future__ import annotations

import gzip
import hashlib
import heapq
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "cases_output_full/train.jsonl"
OUTPUT = ROOT / "backend/data/historical_train_sample.jsonl.gz"
PER_MATCH = 3
PROGRESS_EVERY = 100_000


def compact(row: dict) -> dict:
    state = row.get("tactical_state") or {}
    event = row.get("trigger_event") or {}
    evtype = event.get("type") or {}
    play = event.get("play_pattern") or {}
    team = event.get("team") or {}
    opp = row.get("opponent")
    pos = state.get("location") or event.get("location")
    score = row.get("score_state") or {}
    return {
        "case_id": row.get("case_id"),
        "match_id": str(row.get("match_id")),
        "timestamp": row.get("timestamp"),
        "period": row.get("period", event.get("period")),
        "team": row.get("team") or team.get("name"),
        "opponent": opp,
        "score_diff": score.get("score_diff", state.get("score_diff")),
        "formation": state.get("formation"),
        "event_id": event.get("id"),
        "event_type": evtype.get("name") or event.get("event_type"),
        "play_pattern": play.get("name") or event.get("play_pattern_name"),
        "location": pos if isinstance(pos, list) and len(pos) >= 2 else None,
        "under_pressure": bool(event.get("under_pressure", False)),
        "counterpress": bool(event.get("counterpress", False)),
        "event_outcome": _event_outcome(event),
        "provenance": "StatsBomb-derived train case; phase and field-zone omitted",
    }


def _event_outcome(event: dict) -> str | None:
    for key in ("pass", "shot", "duel", "interception", "ball_recovery", "dribble", "goalkeeper"):
        obj = event.get(key)
        if isinstance(obj, dict):
            outcome = obj.get("outcome")
            if isinstance(outcome, dict) and outcome.get("name"):
                return str(outcome["name"])
    return None


def main() -> int:
    if not TRAIN.is_file():
        print(f"Missing train split: {TRAIN}", file=sys.stderr)
        return 1
    # Keep the three smallest stable hashes per match, a deterministic uniform-like
    # sample that does not depend on source ordering or evaluation labels.
    chosen: dict[str, list[tuple[int, str, dict]]] = {}
    parsed = 0
    matches = set()
    types = Counter()
    try:
        with TRAIN.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                parsed += 1
                match_id = str(row.get("match_id", ""))
                if not match_id:
                    continue
                matches.add(match_id)
                slim = compact(row)
                if not slim["event_type"]:
                    continue
                types[slim["event_type"]] += 1
                key = int.from_bytes(hashlib.sha256(str(slim["case_id"]).encode()).digest()[:8], "big")
                bucket = chosen.setdefault(match_id, [])
                candidate = (-key, str(slim["case_id"]), slim)
                if len(bucket) < PER_MATCH:
                    heapq.heappush(bucket, candidate)
                elif candidate > bucket[0]:
                    heapq.heapreplace(bucket, candidate)
                if parsed % PROGRESS_EVERY == 0:
                    print(f"Scanned {parsed:,} train cases across {len(matches):,} matches", flush=True)
        records = [entry[2] for bucket in chosen.values() for entry in bucket]
        records.sort(key=lambda r: (r["match_id"], r.get("timestamp") or "", str(r["case_id"])))
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(OUTPUT, "wt", encoding="utf-8", newline="\n", compresslevel=6) as out:
            for record in records:
                out.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Train sample preparation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Scanned {parsed:,} train cases in {len(matches):,} matches.")
    print(f"Saved {len(records):,} deterministic candidates ({PER_MATCH} maximum per match) to {OUTPUT.relative_to(ROOT)}.")
    print(f"Event types represented: {len(types)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

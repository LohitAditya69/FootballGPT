"""Audit train/test match separation and create expert-review seed questions."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = PROJECT_ROOT / "cases_output_full"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "case_corpus_audit.md"
DEFAULT_SEEDS = PROJECT_ROOT / "reports" / "evaluation_seed_questions.csv"
PATTERNS = {
    "case_id": re.compile(rb'"case_id"\s*:\s*"([^"]*)"'),
    "match_id": re.compile(rb'"match_id"\s*:\s*"?([^",}]+)'),
    "event_type": re.compile(rb'"event_type"\s*:\s*(?:"([^"]*)"|(null))'),
    "field_zone": re.compile(rb'"field_zone"\s*:\s*(?:"([^"]*)"|(null))'),
    "phase": re.compile(rb'"phase"\s*:\s*(?:"([^"]*)"|(null))'),
}


def extract(field: str, line: bytes) -> str | None:
    match = PATTERNS[field].search(line)
    if not match or match.group(1) in (None, b"null"):
        return None
    return match.group(1).decode("utf-8", errors="replace")


def priority(case_id: str) -> int:
    return int.from_bytes(hashlib.blake2b(case_id.encode(), digest_size=8).digest(), "big")


def audit_split(path: Path, name: str, samples_per_event: int) -> dict[str, Any]:
    matches: Counter[str] = Counter()
    events: Counter[str] = Counter()
    zones: Counter[str] = Counter()
    phases: Counter[str] = Counter()
    samples: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    rows = missing_case = missing_match = 0
    with path.open("rb") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows += 1
            case_id = extract("case_id", line)
            match_id = extract("match_id", line)
            event_type = extract("event_type", line)
            zone = extract("field_zone", line)
            phase = extract("phase", line)
            missing_case += case_id is None
            missing_match += match_id is None
            if match_id:
                matches[match_id] += 1
            if event_type:
                events[event_type] += 1
            if zone:
                zones[zone] += 1
            if phase:
                phases[phase] += 1

            # Select deterministic low-hash examples by event type from test only.
            if name == "test" and case_id and event_type and samples_per_event:
                candidates = samples.setdefault(event_type, [])
                score = priority(case_id)
                if len(candidates) < samples_per_event or score < candidates[-1][0]:
                    try:
                        record = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        record = None
                    if record is not None:
                        candidates.append((score, record))
                        candidates.sort(key=lambda item: item[0])
                        del candidates[samples_per_event:]
            if rows % 250_000 == 0:
                print(f"{name}: scanned {rows:,} records", flush=True)
    return {"rows": rows, "matches": matches, "events": events, "zones": zones,
            "phases": phases, "samples": samples, "missing_case": missing_case,
            "missing_match": missing_match}


def evidence_refs(record: dict[str, Any]) -> str:
    trigger = record.get("trigger_event") or {}
    trigger_type = trigger.get("event_type") or trigger.get("type", {})
    if isinstance(trigger_type, dict):
        trigger_type = trigger_type.get("name", "unknown")
    trigger_team = trigger.get("team_name") or trigger.get("team", {})
    if isinstance(trigger_team, dict):
        trigger_team = trigger_team.get("name", "unknown")
    refs = [
        f"TRIGGER {trigger.get('id', '')}: {trigger_type} by {trigger_team} at "
        f"{trigger.get('timestamp', record.get('timestamp', ''))}"
    ]
    for item in record.get("evidence") or []:
        if item.get("source_type") == "match_event":
            refs.append(f"{item.get('evidence_id', '')}: {item.get('description', '')}")
        if len(refs) >= 6:
            break
    return " | ".join(refs)


def verify_source_event(record: dict[str, Any], raw_root: Path) -> tuple[str, str]:
    match_id = str(record.get("match_id", ""))
    path = raw_root / f"{match_id}.json"
    trigger = record.get("trigger_event") or {}
    trigger_id = trigger.get("id")
    if not path.is_file():
        return str(path), "raw match file missing"
    try:
        events = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return str(path), "raw match file invalid"
    if not isinstance(events, list) or not trigger_id:
        return str(path), "trigger event ID unavailable"
    source = next((event for event in events if event.get("id") == trigger_id), None)
    if source is None:
        return str(path), "trigger ID not found in raw match"
    source_type = source.get("type", {})
    source_type = source_type.get("name") if isinstance(source_type, dict) else source_type
    expected_type = trigger.get("event_type") or trigger.get("type", {})
    expected_type = expected_type.get("name") if isinstance(expected_type, dict) else expected_type
    if source_type != expected_type or source.get("timestamp") != trigger.get("timestamp"):
        return str(path), "trigger ID found, but type/timestamp mismatch"
    return str(path), "verified against raw event ID, type, and timestamp"


def write_seeds(path: Path, samples: dict[str, list[tuple[int, dict[str, Any]]]], limit: int) -> tuple[int, int]:
    columns = ["case_id", "split", "question_seed", "match_id", "period", "timestamp",
               "team", "opponent", "event_type", "phase", "field_zone",
               "trigger_event_id", "trigger_event_team", "trigger_event_player",
               "source_event_index", "raw_match_file", "raw_source_status",
               "evidence_references", "heuristic_action_suggestions",
               "expert_reference_answer", "reviewer", "context_status", "review_status"]
    rows: list[dict[str, Any]] = []
    verified_count = 0
    raw_root = PROJECT_ROOT / "archive (3)" / "data" / "events"
    for event_type in sorted(samples):
        for _, record in samples[event_type]:
            state = record.get("tactical_state") or {}
            raw_zone = state.get("field_zone")
            raw_phase = state.get("phase")
            if raw_zone not in {"attacking_third", "middle_third", "defensive_third"}:
                continue
            if not raw_phase or raw_phase == "unknown":
                continue
            team = record.get("team") or "the team"
            trigger = record.get("trigger_event") or {}
            trigger_type = trigger.get("event_type") or state.get("event_type", event_type)
            if isinstance(trigger_type, dict):
                trigger_type = trigger_type.get("name", event_type)
            trigger_team = trigger.get("team_name") or ""
            trigger_player = trigger.get("player_name") or ""
            source_path, source_status = verify_source_event(record, raw_root)
            if source_status != "verified against raw event ID, type, and timestamp":
                continue
            verified_count += 1
            zone = raw_zone.replace("_", " ")
            phase = raw_phase.replace("_", " ")
            question = (f"For {team}, the event record shows {trigger_type} in the {zone} "
                        f"during a case-builder-inferred {phase}. What tactical options should "
                        "be considered, and what additional evidence is needed before choosing one?")
            provenance = record.get("provenance") or {}
            suggestions = [a.get("label", "") for a in record.get("candidate_actions", [])]
            match_id = str(record.get("match_id", ""))
            rows.append({
                "case_id": record.get("case_id", ""), "split": "test",
                "question_seed": question, "match_id": match_id,
                "period": record.get("period", ""), "timestamp": record.get("timestamp", ""),
                "team": team, "opponent": record.get("opponent", ""),
                "event_type": trigger_type, "phase": raw_phase, "field_zone": raw_zone,
                "trigger_event_id": trigger.get("id", ""),
                "trigger_event_team": trigger_team, "trigger_event_player": trigger_player,
                "source_event_index": provenance.get("event_index", ""),
                "raw_match_file": source_path, "raw_source_status": source_status,
                "evidence_references": evidence_refs(record),
                "heuristic_action_suggestions": " | ".join(suggestions),
                "expert_reference_answer": "", "reviewer": "",
                "context_status": "phase and field zone are case-builder heuristics; verify against source",
                "review_status": "needs expert review",
            })
            if len(rows) >= limit:
                break
        if len(rows) >= limit:
            break
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows), verified_count

def top_lines(counter: Counter[str], limit: int = 10) -> str:
    return "\n".join(f"- {key}: {count:,}" for key, count in counter.most_common(limit)) or "- None"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--samples-per-event", type=int, default=3)
    parser.add_argument("--max-seeds", type=int, default=12)
    args = parser.parse_args()

    summary = json.loads((args.corpus_dir / "summary.json").read_text(encoding="utf-8"))
    train = audit_split(args.corpus_dir / "train.jsonl", "train", 0)
    test = audit_split(args.corpus_dir / "test.jsonl", "test", args.samples_per_event)
    seeds, verified_seeds = write_seeds(args.seeds, test["samples"], args.max_seeds)
    overlap = sorted(set(train["matches"]) & set(test["matches"]))
    events_dir = PROJECT_ROOT / "archive (3)" / "data" / "events"
    available_match_ids = {p.stem for p in events_dir.glob("*.json")}
    corpus_match_ids = set(train["matches"]) | set(test["matches"])
    raw_matches_without_cases = sorted(available_match_ids - corpus_match_ids)
    case_matches_without_raw = sorted(corpus_match_ids - available_match_ids)
    rate_limit_files = sorted(
        p.stem for p in events_dir.glob("*.json")
        if p.stat().st_size <= 200 and b"temporarily unavailable" in p.read_bytes()
    )
    lineups_dir = PROJECT_ROOT / "archive (3)" / "data" / "lineups"
    invalid_lineup_files = sorted(
        p.stem for p in lineups_dir.glob("*.json")
        if p.stat().st_size <= 200 and b"temporarily unavailable" in p.read_bytes()
    )
    valid_raw_without_cases = sorted(set(raw_matches_without_cases) - set(rate_limit_files))
    rows = [("train", train["rows"], summary.get("train")),
            ("test", test["rows"], summary.get("test")),
            ("total", train["rows"] + test["rows"], summary.get("cases"))]

    lines = [
        "# Case Corpus Audit", "", "## Split integrity", "",
        f"- Train rows scanned: {train['rows']:,}",
        f"- Test rows scanned: {test['rows']:,}",
        f"- Unique train match IDs: {len(train['matches']):,}",
        f"- Unique test match IDs: {len(test['matches']):,}",
        f"- Match IDs in both splits: {len(overlap):,}",
        f"- Missing case IDs: {train['missing_case'] + test['missing_case']:,}",
        f"- Missing match IDs: {train['missing_match'] + test['missing_match']:,}",
        f"- Raw StatsBomb matches with no cases: {len(raw_matches_without_cases):,}",
        f"- Event files containing the 96-byte rate-limit error: {len(rate_limit_files):,}",
        f"- Lineup files containing the 96-byte rate-limit error: {len(invalid_lineup_files):,}",
        f"- Valid raw matches without cases: {len(valid_raw_without_cases):,}",
        f"- Case match IDs absent from raw event files: {len(case_matches_without_raw):,}",
        "", "| Count | Scanned | summary.json | result |", "|---|---:|---:|---|",
    ]
    for label, actual, expected in rows:
        lines.append(f"| {label} | {actual:,} | {expected:,} | {'match' if actual == expected else 'MISMATCH'} |")
    if not overlap and not train["missing_match"] and not test["missing_match"]:
        lines += ["", "Conclusion: no match leakage found; each match is confined to one split."]
    else:
        lines += ["", "Conclusion: split integrity needs correction before reporting held-out metrics."]
    lines += [
        "", "## Sample review", "",
        f"- Created {seeds} deterministic, stratified seed rows from the held-out test split.",
        f"- Frequent train event types:\n{top_lines(train['events'])}",
        f"- Frequent test event types:\n{top_lines(test['events'])}",
        f"- Frequent test field zones:\n{top_lines(test['zones'])}",
        f"- Frequent test phases:\n{top_lines(test['phases'])}",
        "", f"All {verified_seeds} seed trigger events were matched to the raw StatsBomb event ID, type, and timestamp. Phase and field-zone values are case-builder heuristics. Candidate actions are generated heuristics, not verified facts or expert answers.",
        "", "## Question-set status", "",
        f"The review-ready CSV is `{args.seeds}`. It contains {seeds} question/evidence seeds, blank expert answers, and `needs expert review` status. No expert validation is claimed.",
        "Review each row against the cited raw match event and adjacent events. Add a concise reference answer with evidence IDs, or remove/rewrite the question if the evidence does not support an answer. Only reviewed rows should become the gold evaluation set.",
        "", "## Split implementation", "",
        "The current case-builder code assigns splits using a stable hash of match_id. This audit scanned the saved train and test files to verify the persisted corpus directly.",
    ]
    if overlap:
        lines += ["", "Overlapping match IDs (first 100): " + ", ".join(overlap[:100])]
    if rate_limit_files:
        lines += ["", f"Invalid raw event files containing the service error (first 50 of {len(rate_limit_files)}): " + ", ".join(rate_limit_files[:50])]
    if invalid_lineup_files:
        lines += ["", "Invalid lineup file IDs: " + ", ".join(invalid_lineup_files)]
    if valid_raw_without_cases:
        lines += ["", f"Valid raw matches without generated cases (first 50 of {len(valid_raw_without_cases)}): " + ", ".join(valid_raw_without_cases[:50])]
    if case_matches_without_raw:
        lines += ["", f"Case match IDs missing from the raw dataset (first 50 of {len(case_matches_without_raw)}): " + ", ".join(case_matches_without_raw[:50])]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Scanned train={train['rows']:,}, test={test['rows']:,}")
    print(f"Train matches={len(train['matches']):,}, test matches={len(test['matches']):,}, overlap={len(overlap):,}")
    print(f"Wrote report: {args.report}")
    print(f"Wrote expert-review seeds: {args.seeds} ({seeds} rows; {verified_seeds} raw triggers verified)")


if __name__ == "__main__":
    main()

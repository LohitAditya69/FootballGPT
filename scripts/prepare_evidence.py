#!/usr/bin/env python3
"""Prepare reproducible, page-cited UEFA text and bounded StatsBomb evidence windows."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports/uefa_report_manifest.json"
SEEDS = ROOT / "reports/evaluation_seed_questions.csv"
UEFA_OUT = ROOT / "backend/data/uefa_evidence_chunks.jsonl"
EVENT_OUT = ROOT / "backend/data/question_event_evidence.jsonl"
WORDS_PER_CHUNK = 300
WORD_OVERLAP = 40
EVENT_RADIUS = 5


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def extract_uefa() -> list[dict]:
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext is required (install Poppler) to extract the UEFA PDFs")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records: list[dict] = []
    for source in manifest["sources"]:
        pdf = ROOT / source["file"]
        if not pdf.is_file():
            raise FileNotFoundError(pdf)
        actual_hash = sha256(pdf)
        if actual_hash != source["sha256"]:
            raise ValueError(f"SHA-256 differs from locked manifest: {source['file']}")
        result = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
            check=True, capture_output=True, text=True,
        )
        pages = result.stdout.split("\f")
        if pages and not pages[-1].strip():
            pages.pop()
        if len(pages) != source["pages"]:
            raise ValueError(f"Expected {source['pages']} pages in {pdf.name}, extracted {len(pages)}")
        for page_no, page in enumerate(pages, start=1):
            words = re.findall(r"\S+", page)
            if not words:
                continue
            step = WORDS_PER_CHUNK - WORD_OVERLAP
            for chunk_no, start in enumerate(range(0, len(words), step), start=1):
                chunk_words = words[start : start + WORDS_PER_CHUNK]
                if not chunk_words:
                    continue
                records.append({
                    "evidence_id": f"{source['source_id']}:p{page_no}:c{chunk_no}",
                    "source_id": source["source_id"],
                    "source_title": source["title"],
                    "source_file": source["file"],
                    "source_sha256": actual_hash,
                    "page": page_no,
                    "citation": f"{source['source_id']} p.{page_no}",
                    "chunk_index": chunk_no,
                    "chunk_word_start": start,
                    "text": " ".join(chunk_words),
                })
                if start + WORDS_PER_CHUNK >= len(words):
                    break
    write_jsonl(UEFA_OUT, records)
    return records


def selected_event(event: dict, index: int, trigger_index: int) -> dict:
    kind = (event.get("type") or {}).get("name")
    data = {k: event[k] for k in ("id", "index", "period", "timestamp", "minute", "second", "location", "duration", "under_pressure", "play_pattern") if k in event}
    data.update({
        "window_offset": index - trigger_index,
        "type": kind,
        "team": (event.get("team") or {}).get("name"),
        "player": (event.get("player") or {}).get("name"),
        "possession": event.get("possession"),
    })
    for key in ("pass", "shot", "carry", "interception", "pressure", "ball_recovery", "clearance", "dribble", "duel", "block", "goalkeeper"):
        value = event.get(key)
        if not isinstance(value, dict):
            continue
        if key == "pass":
            fields = ("recipient", "length", "angle", "end_location", "outcome", "type", "height", "shot_assist", "assisted_shot_id", "through_ball", "cross", "cut_back")
        elif key == "shot":
            fields = ("statsbomb_xg", "outcome", "body_part", "type", "technique", "key_pass_id", "end_location", "freeze_frame")
        else:
            fields = tuple(value.keys())
        data[key] = {k: value[k] for k in fields if k in value}
    return data


def extract_events() -> list[dict]:
    with SEEDS.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if r.get("split") == "test"]
    if len(rows) != 12:
        raise ValueError(f"Scope lock expects 12 test seeds, found {len(rows)}")
    records = []
    for row in rows:
        match_id = str(row["match_id"])
        raw = ROOT / "archive (3)" / "data/events" / f"{match_id}.json"
        if not raw.is_file():
            raise FileNotFoundError(f"Missing raw StatsBomb event file for {match_id}: {raw}")
        events = json.loads(raw.read_text(encoding="utf-8"))
        trigger_id = row["trigger_event_id"]
        matches = [i for i, e in enumerate(events) if e.get("id") == trigger_id]
        if len(matches) != 1:
            raise ValueError(f"Expected one trigger {trigger_id} in {raw}, found {len(matches)}")
        trigger_i = matches[0]
        start, end = max(0, trigger_i - EVENT_RADIUS), min(len(events), trigger_i + EVENT_RADIUS + 1)
        records.append({
            "evidence_id": f"statsbomb:{match_id}:{trigger_id}",
            "case_id": row["case_id"],
            "match_id": match_id,
            "question": row.get("revised_question_seed") or row.get("question_seed"),
            "trigger_event_id": trigger_id,
            "trigger_event_index_in_file": trigger_i,
            "trigger_event_type": (events[trigger_i].get("type") or {}).get("name"),
            "trigger_timestamp": events[trigger_i].get("timestamp"),
            "source_file": str(raw.relative_to(ROOT)),
            "window_rule": f"trigger plus up to {EVENT_RADIUS} adjacent file-order events on each side",
            "events": [selected_event(events[i], i, trigger_i) for i in range(start, end)],
        })
    write_jsonl(EVENT_OUT, records)
    return records


def main() -> int:
    try:
        uefa = extract_uefa()
        events = extract_events()
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Evidence preparation failed: {e}", file=sys.stderr)
        return 1
    print(f"Prepared {len(uefa)} cited UEFA page chunks across the locked reports.")
    print(f"Prepared {len(events)} StatsBomb evidence windows for the 12 locked test questions.")
    print(f"UEFA evidence: {UEFA_OUT.relative_to(ROOT)}")
    print(f"Event evidence: {EVENT_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

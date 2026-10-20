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
MAX_WORDS_PER_CHUNK = 180
EVENT_RADIUS = 5


def normalize_retrieval_text(text: str) -> str:
    """Normalize layout whitespace for indexing without changing source text."""
    return re.sub(r"\s+", " ", text).strip()


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return deterministic sentence-like spans, retaining punctuation and wording."""
    spans: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"[.!?](?:[\"'’”)]*)?(?=\s+|$)", text):
        end = match.end()
        if text[start:end].strip():
            spans.append((start, end))
        start = end
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def _bounded_sentence_spans(text: str, max_words: int) -> list[tuple[int, int]]:
    """Split sentences at sentence boundaries, with a hard word bound."""
    bounded: list[tuple[int, int]] = []
    for start, end in _sentence_spans(text):
        sentence = text[start:end]
        word_matches = list(re.finditer(r"\S+", sentence))
        if len(word_matches) <= max_words:
            bounded.append((start, end))
            continue
        for offset in range(0, len(word_matches), max_words):
            group = word_matches[offset : offset + max_words]
            bounded.append((start + group[0].start(), start + group[-1].end()))
    return bounded


def _page_blocks(page_text: str) -> list[str]:
    """Separate blank-line paragraphs and keep standalone headings with their section."""
    blocks: list[str] = []
    current: list[str] = []
    for line in page_text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        letters = [char for char in stripped if char.isalpha()]
        is_standalone_heading = (
            bool(letters)
            and len(stripped) <= 90
            and stripped == stripped.upper()
            and not stripped.endswith((".", ",", ";", ":"))
        )
        if is_standalone_heading and current:
            blocks.append("\n".join(current))
            current = []
        current.append(stripped)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _layout_columns(page_text: str) -> list[str]:
    """Separate left/right cells from Poppler's padded layout lines."""
    rows = [
        [(match.start(), match.group().strip()) for match in re.finditer(r"\S.*?(?= {4,}|$)", line)]
        for line in page_text.splitlines()
    ]
    starts = sorted({x for row in rows for x, text in row if text})
    if len(starts) < 2:
        return [page_text.strip()] if page_text.strip() else []
    gaps = [(starts[index + 1] - starts[index], starts[index], starts[index + 1]) for index in range(len(starts) - 1)]
    gap, left_edge, right_edge = max(gaps)
    if gap < 18:
        return [page_text.strip()] if page_text.strip() else []
    split_at = (left_edge + right_edge) / 2
    columns = [[], []]
    for row in rows:
        for x, text in row:
            columns[int(x >= split_at)].append(text)
    return ["\n".join(lines) for lines in columns if any(line.strip() for line in lines)]


def chunk_page_text(page_text: str, max_words: int = MAX_WORDS_PER_CHUNK) -> list[str]:
    """Create page-local paragraph/sentence groups with an exact-text trace."""
    if max_words < 1:
        raise ValueError("max_words must be positive")
    chunks: list[str] = []
    for column_text in _layout_columns(page_text):
        for raw_paragraph in _page_blocks(column_text):
            paragraph = raw_paragraph.strip()
            groups: list[tuple[int, int]] = []
            group_start: int | None = None
            group_end: int | None = None
            group_words = 0
            for start, end in _bounded_sentence_spans(paragraph, max_words):
                sentence_words = len(re.findall(r"\S+", paragraph[start:end]))
                if group_start is not None and group_words + sentence_words > max_words:
                    groups.append((group_start, group_end or group_start))
                    group_start = None
                    group_words = 0
                if group_start is None:
                    group_start = start
                group_end = end
                group_words += sentence_words
            if group_start is not None and group_end is not None:
                groups.append((group_start, group_end))
            chunks.extend(paragraph[start:end].strip() for start, end in groups)
    return [chunk for chunk in chunks if chunk]


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


def extract_pdf_pages(pdf: Path) -> list[str]:
    """Extract one layout-preserving text string per page with Poppler."""
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext (Poppler) is required to extract the locked UEFA PDFs")
    result = subprocess.run(
        # Layout mode retains word spacing and page mapping. chunk_page_text()
        # uses the padded columns to keep parallel report columns separate.
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    pages = result.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def extract_uefa() -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records: list[dict] = []
    for source in manifest["sources"]:
        pdf = ROOT / source["file"]
        if not pdf.is_file():
            raise FileNotFoundError(pdf)
        actual_hash = sha256(pdf)
        if actual_hash != source["sha256"]:
            raise ValueError(f"SHA-256 differs from locked manifest: {source['file']}")
        pages = extract_pdf_pages(pdf)
        if len(pages) != source["pages"]:
            raise ValueError(f"Expected {source['pages']} pages in {pdf.name}, extracted {len(pages)}")
        for page_no, page in enumerate(pages, start=1):
            page_chunks = chunk_page_text(page)
            word_start = 0
            for chunk_no, chunk_text in enumerate(page_chunks, start=1):
                chunk_words = re.findall(r"\S+", chunk_text)
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
                    "chunk_word_start": word_start,
                    "text": chunk_text,
                    "retrieval_text": normalize_retrieval_text(chunk_text),
                })
                word_start += len(chunk_words)
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

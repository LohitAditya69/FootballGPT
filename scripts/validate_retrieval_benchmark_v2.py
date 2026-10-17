#!/usr/bin/env python3
"""Check v2 question counts, source pages, and split separation."""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "reports/retrieval_benchmark_v2_questions.csv"
V1 = ROOT / "reports/evaluation_seed_questions.csv"
OLD_DEV = ROOT / "reports/retrieval_development_questions.csv"
CHUNKS = ROOT / "backend/data/uefa_evidence_chunks.jsonl"

SOURCE_LABELS = {
    "ucl": "uefa-ucl-2024-25", "uwcl": "uefa-uwcl-2024-25",
    "women's euro": "uefa-weuro-2025", "women’s euro": "uefa-weuro-2025",
}
REF_RE = re.compile(r"\b(UWCL|UCL|Women[’']s\s+EURO)\b\s+pp?\.?\s*(\d+)(?:[-–](\d+))?", re.I)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def source_pages_from_locked(rows: list[dict]) -> set[tuple[str, int]]:
    pages = set()
    for row in rows:
        for m in REF_RE.finditer(row.get("gold_qrel_pages", "")):
            source = SOURCE_LABELS[m.group(1).casefold()]
            first, last = int(m.group(2)), int(m.group(3) or m.group(2))
            pages.update((source, page) for page in range(first, last + 1))
    return pages


def main() -> int:
    v2 = read_csv(V2)
    if len(v2) != 40 or len({r["question_id"] for r in v2}) != 40:
        raise SystemExit("Expected 40 unique v2 questions")
    dev = [r for r in v2 if r["split"] == "dev"]
    test = [r for r in v2 if r["split"] == "test"]
    if len(dev) != 20 or len(test) != 20:
        raise SystemExit(f"Expected 20 dev and 20 test questions; found {len(dev)} and {len(test)}")
    pages = set()
    for line in CHUNKS.open(encoding="utf-8"):
        row = json.loads(line)
        pages.add((row["source_id"], int(row["page"])))
    for q in v2:
        key = (q["source_id"], int(q["relevant_pages"]))
        if key not in pages:
            raise SystemExit(f"Missing report page for {q['question_id']}: {key}")
    v1_rows = read_csv(V1)
    locked_pages = source_pages_from_locked(v1_rows)
    old_dev_pages = {(r["source_id"], int(r["relevant_pages"])) for r in read_csv(OLD_DEV)}
    dev_pages = {(r["source_id"], int(r["relevant_pages"])) for r in dev}
    test_pages = {(r["source_id"], int(r["relevant_pages"])) for r in test}
    if len(dev_pages) != len(dev) or len(test_pages) != len(test):
        raise SystemExit("Each split must target a unique source page")
    if dev_pages & test_pages or test_pages & locked_pages or test_pages & old_dev_pages:
        raise SystemExit("V2 held-out pages overlap development or prior benchmark pages")
    print("V2 validation passed: 20 development and 20 held-out questions; source pages exist; held-out pages are disjoint from v1 qrels, previous dev labels, and v2 development pages.")
    print("Questions per report (dev/test):")
    for source in sorted({r["source_id"] for r in v2}):
        print(source, sum(r["source_id"] == source for r in dev), sum(r["source_id"] == source for r in test))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

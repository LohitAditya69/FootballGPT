#!/usr/bin/env python3
"""Build nested, deterministic H candidate samples for the historical dev split.

Only cases belonging to the candidate match IDs in the frozen split manifest
are read into the outputs. The source training JSONL is read-only, and no
development-query or original test match is written as a candidate.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN = ROOT / "cases_output_full/train.jsonl"
DEFAULT_SPLIT = ROOT / "reports/historical_retrieval_match_split_v1.json"
DEFAULT_OUTPUT_DIR = Path("/private/tmp/footballgpt_historical_candidates_v1")
HASH_NAMESPACE = "footballgpt-historical-candidate-sample-v1"
PROGRESS_EVERY = 250_000

sys.path.insert(0, str(ROOT / "scripts"))
from sample_train_situations import compact  # noqa: E402


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN, help="Original train JSONL (read-only)")
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT, help="Frozen match-split manifest")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Derived outputs directory (default: outside the repository)")
    parser.add_argument("--per-match", type=int, nargs="+", default=[3, 10, 25], help="Nested maximum sample sizes per candidate match")
    args = parser.parse_args()

    if not args.train.is_file():
        parser.error(f"Train split not found: {args.train}")
    if not args.split.is_file():
        parser.error(f"Split manifest not found: {args.split}")
    if any(size < 1 for size in args.per_match) or len(set(args.per_match)) != len(args.per_match):
        parser.error("--per-match values must be positive and unique")

    split = json.loads(args.split.read_text(encoding="utf-8"))
    if split.get("schema_version") != "historical-match-split-v1":
        parser.error("Unsupported historical match-split manifest schema")
    dev_ids = set(map(str, split["dev_query_match_ids"]))
    candidate_ids = set(map(str, split["candidate_match_ids"]))
    if dev_ids & candidate_ids or len(candidate_ids) != split.get("candidate_match_count"):
        parser.error("Invalid or overlapping query/candidate match IDs in split manifest")

    max_per_match = max(args.per_match)
    buckets: dict[str, list[tuple[int, str, dict]]] = {}
    matched_event_types = Counter()
    candidate_matches_seen: set[str] = set()
    rows_scanned = 0
    try:
        with args.train.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                rows_scanned += 1
                match_id = str(row.get("match_id", ""))
                if match_id not in candidate_ids:
                    if match_id in dev_ids:
                        # Expected: development rows are intentionally skipped.
                        pass
                    continue
                slim = compact(row)
                if not slim["case_id"]:
                    raise ValueError(f"Missing case_id at JSONL line {line_number}")
                candidate_matches_seen.add(match_id)
                event_type = slim.get("event_type")
                if not event_type:
                    continue
                matched_event_types[event_type] += 1
                case_id = str(slim["case_id"])
                key = int.from_bytes(
                    hashlib.sha256(f"{HASH_NAMESPACE}:{case_id}".encode("utf-8")).digest()[:8],
                    "big",
                )
                entry = (-key, case_id, slim)
                bucket = buckets.setdefault(match_id, [])
                if len(bucket) < max_per_match:
                    heapq.heappush(bucket, entry)
                elif entry > bucket[0]:
                    heapq.heapreplace(bucket, entry)
                if rows_scanned % PROGRESS_EVERY == 0:
                    print(f"Scanned {rows_scanned:,} rows; candidate matches seen: {len(candidate_matches_seen):,}", flush=True)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Candidate sampling failed: {exc}", file=sys.stderr)
        return 1

    if candidate_matches_seen != candidate_ids:
        missing = sorted(candidate_ids - candidate_matches_seen)
        print(f"Candidate split IDs absent from train rows: {missing[:10]}", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": "historical-dev-candidate-samples-v1",
        "split_id": split["split_id"],
        "source_split": "original train; candidate match IDs only",
        "source_rows_scanned": rows_scanned,
        "candidate_matches": len(candidate_matches_seen),
        "development_query_matches_excluded": len(dev_ids),
        "per_match_samples": {},
        "event_type_counts_before_sampling": dict(sorted(matched_event_types.items())),
    }
    try:
        for per_match in sorted(args.per_match):
            selected = [
                entry[2]
                for bucket in buckets.values()
                for entry in sorted(bucket, key=lambda item: (-item[0], item[1]))[:per_match]
            ]
            def match_order(record: dict) -> tuple[int, int | str]:
                value = record["match_id"]
                return (0, int(value)) if value.isdigit() else (1, value)

            records = sorted(selected, key=lambda record: (match_order(record), record.get("timestamp") or "", str(record["case_id"])))
            output = args.output_dir / f"historical_dev_candidates_{per_match}_per_match.jsonl.gz"
            with gzip.open(output, "wt", encoding="utf-8", newline="\n", compresslevel=6) as target:
                for record in records:
                    target.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            sample_matches = {record["match_id"] for record in records}
            if not sample_matches <= candidate_ids or sample_matches & dev_ids:
                raise ValueError(f"Split leakage detected in {output.name}")
            summary["per_match_samples"][str(per_match)] = {
                "records": len(records),
                "matches_represented": len(sample_matches),
                "compressed_bytes": output.stat().st_size,
                "sha256": file_sha256(output),
                "path": str(output),
            }
    except (OSError, ValueError) as exc:
        print(f"Could not write candidate samples: {exc}", file=sys.stderr)
        return 1

    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scanned {rows_scanned:,} train rows; retained candidates from {len(candidate_matches_seen):,} matches.")
    for size, values in summary["per_match_samples"].items():
        print(f"{size:>2} per match: {values['records']:,} records across {values['matches_represented']:,} matches; {values['compressed_bytes']:,} compressed bytes")
    print(f"Derived outputs (not source data): {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

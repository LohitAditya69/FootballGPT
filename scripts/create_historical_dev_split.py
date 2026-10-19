#!/usr/bin/env python3
"""Create a deterministic match-disjoint dev split from the original train set.

This script reads the existing case corpus but never edits it. Development
query matches are reserved from the original training split; candidate matches
are the remaining original training matches. The original test split is not
read or modified by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN = ROOT / "cases_output_full/train.jsonl"
DEFAULT_OUTPUT = ROOT / "reports/historical_retrieval_match_split_v1.json"
SPLIT_ID = "historical-match-dev-v1"
HASH_NAMESPACE = "footballgpt-historical-dev-v1"
EXPECTED_TRAIN_ROWS = 1_759_328
EXPECTED_TRAIN_MATCHES = 3_341


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN, help="Existing original train JSONL (read-only)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output split manifest JSON")
    parser.add_argument("--dev-fraction", type=float, default=0.10, help="Fraction of original train match IDs reserved for dev (default: 0.10)")
    parser.add_argument("--allow-count-drift", action="store_true", help="Allow counts to differ from the previously audited corpus")
    args = parser.parse_args()

    if not args.train.is_file():
        parser.error(f"Train split not found: {args.train}")
    if not 0 < args.dev_fraction < 1:
        parser.error("--dev-fraction must be greater than 0 and less than 1")

    match_ids: set[str] = set()
    rows_scanned = 0
    try:
        with args.train.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                match_id = row.get("match_id")
                if match_id is None or str(match_id).strip() == "":
                    raise ValueError(f"Missing match_id at JSONL line {line_number}")
                match_ids.add(str(match_id))
                rows_scanned += 1
                if rows_scanned % 250_000 == 0:
                    print(f"Scanned {rows_scanned:,} rows; found {len(match_ids):,} train matches", flush=True)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Could not create split: {exc}", file=sys.stderr)
        return 1

    if not match_ids:
        print("No training match IDs found", file=sys.stderr)
        return 1
    if not args.allow_count_drift and (rows_scanned != EXPECTED_TRAIN_ROWS or len(match_ids) != EXPECTED_TRAIN_MATCHES):
        print(
            "The input differs from the previously audited corpus "
            f"(rows={rows_scanned:,}, matches={len(match_ids):,}; expected "
            f"rows={EXPECTED_TRAIN_ROWS:,}, matches={EXPECTED_TRAIN_MATCHES:,}). "
            "Inspect the input or pass --allow-count-drift to accept it.",
            file=sys.stderr,
        )
        return 1

    ordered = sorted(
        match_ids,
        key=lambda match_id: (hashlib.sha256(f"{HASH_NAMESPACE}:{match_id}".encode("utf-8")).hexdigest(), match_id),
    )
    dev_count = max(1, round(len(ordered) * args.dev_fraction))
    def stable_id_order(value: str) -> tuple[int, int | str]:
        return (0, int(value)) if value.isdigit() else (1, value)

    dev_matches = sorted(ordered[:dev_count], key=stable_id_order)
    candidate_matches = sorted(ordered[dev_count:], key=stable_id_order)
    if set(dev_matches) & set(candidate_matches) or set(dev_matches) | set(candidate_matches) != match_ids:
        print("Split integrity check failed", file=sys.stderr)
        return 1

    payload = {
        "schema_version": "historical-match-split-v1",
        "split_id": SPLIT_ID,
        "source_split": "original train only",
        "source_train_path": str(args.train.relative_to(ROOT)) if args.train.is_relative_to(ROOT) else str(args.train),
        "source_rows_scanned": rows_scanned,
        "source_unique_match_count": len(match_ids),
        "dev_fraction_requested": args.dev_fraction,
        "dev_match_count": len(dev_matches),
        "candidate_match_count": len(candidate_matches),
        "hash_namespace": HASH_NAMESPACE,
        "assignment_rule": "Sort unique original-train match IDs by SHA-256(namespace + ':' + match_id); reserve the first round(fraction * N) IDs for dev queries and assign the rest as candidate matches.",
        "original_test_split_used": False,
        "dev_query_match_ids": dev_matches,
        "candidate_match_ids": candidate_matches,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        print(f"Could not write split manifest: {exc}", file=sys.stderr)
        return 1

    print(f"Scanned {rows_scanned:,} rows across {len(match_ids):,} original-train matches.")
    print(f"Reserved {len(dev_matches):,} dev-query matches; {len(candidate_matches):,} candidate matches.")
    print(f"Match overlap: 0. Manifest: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

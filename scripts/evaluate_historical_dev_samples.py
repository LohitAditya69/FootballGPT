#!/usr/bin/env python3
"""Compare historical candidate sample sizes on the frozen metadata proxy.

One deterministic, event-type-balanced query is selected from each reserved
development match. Relevance grades are computed against the fixed
25-per-match candidate reference pool; 3-, 10-, and 25-per-match indexes are
then ranked with the unchanged historical retriever.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN = ROOT / "cases_output_full/train.jsonl"
DEFAULT_SPLIT = ROOT / "reports/historical_retrieval_match_split_v1.json"
DEFAULT_CANDIDATE_DIR = Path("/private/tmp/footballgpt_historical_candidates_v1")
DEFAULT_OUTPUT_DIR = Path("/private/tmp/footballgpt_historical_evaluation_v1")
EVENT_TYPES = ("Pressure", "Pass", "Shot", "Interception", "Substitution")
QUERY_HASH_NAMESPACE = "footballgpt-historical-dev-query-v1"
PROGRESS_EVERY = 250_000
K = 5

sys.path.insert(0, str(ROOT / "scripts"))
from sample_train_situations import compact  # noqa: E402

sys.path.insert(0, str(ROOT))
from backend.retrieval.historical_retriever import historical_similarity  # noqa: E402


def norm(value: Any) -> str | None:
    return value.strip().casefold() if isinstance(value, str) and value.strip() else None


def location_distance(a: Any, b: Any) -> float | None:
    if not (isinstance(a, list) and isinstance(b, list) and len(a) >= 2 and len(b) >= 2):
        return None
    try:
        ax, ay, bx, by = float(a[0]), float(a[1]), float(b[0]), float(b[1])
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(x) for x in (ax, ay, bx, by)):
        return None
    return math.sqrt(((ax - bx) / 120.0) ** 2 + ((ay - by) / 80.0) ** 2)


def relevance_grade(query: dict, candidate: dict) -> int | None:
    """Return 0/1/2 per the frozen project rubric, or None if ungradable."""
    q_type, c_type = norm(query.get("event_type")), norm(candidate.get("event_type"))
    if q_type is None or c_type is None:
        return None
    q_pattern, c_pattern = norm(query.get("play_pattern")), norm(candidate.get("play_pattern"))
    distance = location_distance(query.get("location"), candidate.get("location"))
    pattern_comparable = q_pattern is not None and c_pattern is not None
    if not pattern_comparable and distance is None:
        return None
    if q_type != c_type:
        return 0
    same_pattern = q_pattern is not None and c_pattern is not None and q_pattern == c_pattern
    if same_pattern and distance is not None and distance <= 0.10:
        return 2
    if same_pattern or (distance is not None and distance <= 0.15):
        return 1
    return 0


def select_queries(train_path: Path, dev_ids: set[str]) -> tuple[list[dict], int]:
    """Keep the lowest stable case hash per match/event type, then balance types."""
    best: dict[str, dict[str, tuple[int, dict]]] = {}
    rows = 0
    with train_path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            rows += 1
            match_id = str(row.get("match_id", ""))
            if match_id not in dev_ids:
                continue
            record = compact(row)
            event_type = record.get("event_type")
            if event_type not in EVENT_TYPES or not record.get("case_id"):
                continue
            case_id = str(record["case_id"])
            key = int.from_bytes(
                hashlib.sha256(f"{QUERY_HASH_NAMESPACE}:{case_id}".encode("utf-8")).digest()[:8],
                "big",
            )
            match_best = best.setdefault(match_id, {})
            if event_type not in match_best or key < match_best[event_type][0]:
                match_best[event_type] = (key, record)
            if rows % PROGRESS_EVERY == 0:
                print(f"Query scan: {rows:,} rows; {len(best):,}/{len(dev_ids):,} dev matches found", flush=True)

    def match_order(value: str) -> tuple[int, int | str]:
        return (0, int(value)) if value.isdigit() else (1, value)

    queries = []
    for match_id in sorted(dev_ids, key=match_order):
        available = best.get(match_id, {})
        if not available:
            raise ValueError(f"No supported event query found for development match {match_id}")
        offset = int.from_bytes(hashlib.sha256(f"{QUERY_HASH_NAMESPACE}:type:{match_id}".encode()).digest()[:4], "big") % len(EVENT_TYPES)
        chosen_type = next(EVENT_TYPES[(offset + step) % len(EVENT_TYPES)] for step in range(len(EVENT_TYPES)) if EVENT_TYPES[(offset + step) % len(EVENT_TYPES)] in available)
        queries.append(available[chosen_type][1])
    return queries, rows


def read_candidates(path: Path, allowed_matches: set[str], dev_matches: set[str]) -> list[dict]:
    records = []
    seen = set()
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            match_id = str(row.get("match_id", ""))
            case_id = str(row.get("case_id", ""))
            if match_id not in allowed_matches or match_id in dev_matches:
                raise ValueError(f"Candidate split leakage in {path.name}: match {match_id}")
            if not case_id or case_id in seen:
                raise ValueError(f"Missing or duplicate case_id in {path.name}: {case_id}")
            seen.add(case_id)
            records.append(row)
    return records


def metrics_for(ranked: list[dict], grades: dict[str, int | None], relevant_count: int, grade_counts: Counter) -> dict[str, float]:
    top = ranked[:K]
    top_grades = [grades.get(str(row.get("case_id")), 0) for row in top]
    hits = sum(grade is not None and grade > 0 for grade in top_grades)
    first = next((index for index, grade in enumerate(top_grades, start=1) if grade is not None and grade > 0), None)
    dcg = sum((2**grade - 1) / math.log2(index + 1) for index, grade in enumerate(top_grades, start=1) if grade is not None)
    ideal = sorted([2] * grade_counts[2] + [1] * grade_counts[1], reverse=True)[:K]
    idcg = sum((2**grade - 1) / math.log2(index + 1) for index, grade in enumerate(ideal, start=1))
    return {
        "P@5": hits / K,
        "Recall@5": hits / relevant_count if relevant_count else 0.0,
        "MRR@5": 1 / first if first else 0.0,
        "nDCG@5": dcg / idcg if idcg else 0.0,
        "ungraded_in_top5": float(sum(grade is None for grade in top_grades)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--candidate-dir", type=Path, default=DEFAULT_CANDIDATE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    for path in (args.train, args.split):
        if not path.is_file():
            parser.error(f"Required input not found: {path}")

    split = json.loads(args.split.read_text(encoding="utf-8"))
    if split.get("schema_version") != "historical-match-split-v1":
        parser.error("Unsupported match split manifest")
    dev_ids = set(map(str, split["dev_query_match_ids"]))
    candidate_ids = set(map(str, split["candidate_match_ids"]))
    if dev_ids & candidate_ids:
        parser.error("Development and candidate match IDs overlap")

    try:
        queries, train_rows = select_queries(args.train, dev_ids)
        if train_rows != split["source_rows_scanned"]:
            raise ValueError(f"Train row count drift: {train_rows} != {split['source_rows_scanned']}")
        if len(queries) != len(dev_ids):
            raise ValueError("Did not select exactly one query per development match")

        query_types = Counter(row["event_type"] for row in queries)
        paths = {size: args.candidate_dir / f"historical_dev_candidates_{size}_per_match.jsonl.gz" for size in (3, 10, 25)}
        candidates_by_size = {size: read_candidates(path, candidate_ids, dev_ids) for size, path in paths.items()}
        reference = candidates_by_size[25]
        if not set(row["case_id"] for row in candidates_by_size[3]) <= set(row["case_id"] for row in candidates_by_size[10]):
            raise ValueError("3-per-match candidate set is not nested in the 10-per-match set")
        if not set(row["case_id"] for row in candidates_by_size[10]) <= set(row["case_id"] for row in reference):
            raise ValueError("10-per-match candidate set is not nested in the 25-per-match set")
        tier_case_ids = {
            size: {str(row["case_id"]) for row in candidates}
            for size, candidates in candidates_by_size.items()
        }

        query_results = []
        total_ungraded = 0
        queries_with_relevant = 0
        for query_number, query in enumerate(queries, start=1):
            grades: dict[str, int | None] = {}
            grade_counts: Counter[int] = Counter()
            ungraded_count = 0
            for candidate in reference:
                if str(candidate["match_id"]) == str(query["match_id"]):
                    continue
                grade = relevance_grade(query, candidate)
                grades[str(candidate["case_id"])] = grade
                if grade is None:
                    ungraded_count += 1
                else:
                    grade_counts[grade] += 1
            relevant_count = grade_counts[1] + grade_counts[2]
            total_ungraded += ungraded_count
            queries_with_relevant += int(relevant_count > 0)
            row_result = {
                "query_id": str(query["case_id"]),
                "query_match_id": str(query["match_id"]),
                "event_type": query["event_type"],
                "reference_candidates": len(reference),
                "relevant_grade1": grade_counts[1],
                "relevant_grade2": grade_counts[2],
                "ungraded_reference_pairs": ungraded_count,
            }
            # H scores are candidate-local. Score the reference candidates once,
            # then recover each nested index's top five from the same ordering.
            scored_reference = []
            for candidate in reference:
                if str(candidate["match_id"]) == str(query["match_id"]):
                    continue
                score, _ = historical_similarity(query, candidate)
                if score > 0:
                    scored_reference.append((score, candidate))
            scored_reference.sort(key=lambda item: (-item[0], str(item[1].get("case_id"))))
            for size in candidates_by_size:
                ranked = []
                for score, candidate in scored_reference:
                    if str(candidate["case_id"]) in tier_case_ids[size]:
                        ranked.append({"case_id": candidate["case_id"], "historical_score": round(score, 6)})
                        if len(ranked) == K:
                            break
                values = metrics_for(ranked, grades, relevant_count, grade_counts)
                row_result[f"{size}_per_match_top5"] = [
                    {"case_id": item["case_id"], "historical_score": item["historical_score"], "metadata_grade": grades.get(str(item["case_id"]))}
                    for item in ranked
                ]
                row_result[f"{size}_per_match_metrics"] = values
            query_results.append(row_result)
            if query_number % 25 == 0:
                print(f"Evaluated {query_number}/{len(queries)} development queries", flush=True)

        if queries_with_relevant == 0:
            raise ValueError("No development query has any relevant candidate under the frozen rubric")
        summary = {
            "schema_version": "historical-metadata-proxy-evaluation-v1",
            "split_id": split["split_id"],
            "label_definition": "Similarity definition v1 in reports/historical_retrieval_development_split.md",
            "query_selection": "one stable hash-selected case per reserved development match; event types balanced by deterministic rotation",
            "query_count": len(queries),
            "query_event_type_counts": dict(sorted(query_types.items())),
            "candidate_reference_pool": "25-per-match sample across candidate match IDs; not all training cases",
            "reference_candidate_count": len(reference),
            "queries_with_at_least_one_relevant_candidate": queries_with_relevant,
            "queries_without_relevant_candidate": len(queries) - queries_with_relevant,
            "ungraded_reference_pairs_total": total_ungraded,
            "metrics": {},
            "development_only": True,
            "not_coach_judged": True,
        }
        # Exclude queries with no relevant reference candidates from macro retrieval metrics.
        selected = [row for row in query_results if row["relevant_grade1"] + row["relevant_grade2"] > 0]
        for size in candidates_by_size:
            summary["metrics"][str(size)] = {
                metric: mean(query[f"{size}_per_match_metrics"][metric] for query in selected)
                for metric in ("P@5", "Recall@5", "MRR@5", "nDCG@5", "ungraded_in_top5")
            }

        args.output_dir.mkdir(parents=True, exist_ok=True)
        query_path = args.output_dir / "historical_dev_queries_v1.jsonl"
        with query_path.open("w", encoding="utf-8", newline="\n") as target:
            for query in queries:
                target.write(json.dumps(query, ensure_ascii=False, separators=(",", ":")) + "\n")
        detail_path = args.output_dir / "historical_dev_sample_evaluation_v1.jsonl"
        with detail_path.open("w", encoding="utf-8", newline="\n") as target:
            for result in query_results:
                target.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
        summary_path = args.output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Queries: {summary['query_count']} (event types: {dict(sorted(query_types.items()))})")
        print(f"Reference candidates: {len(reference):,}; queries with relevant candidates: {queries_with_relevant}")
        for size, values in summary["metrics"].items():
            print(size, " ".join(f"{key}={values[key]:.3f}" for key in ("P@5", "Recall@5", "MRR@5", "nDCG@5")))
        print(f"Outputs (outside repo): {args.output_dir}")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"Historical development evaluation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

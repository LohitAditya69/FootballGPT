#!/usr/bin/env python3
"""Export independent coach-reviewed page judgments from retrieval_review_v1.xlsx.

Only IDs, grades, and provenance are exported. Workbook page text and excerpts
are deliberately not copied into the repository.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reports/retrieval_workbook_review_qrels_v1.csv"
REQUIRED = {
    "question_id", "question", "source_id", "page", "relevance_grade",
    "reviewer_id", "reviewer_background", "reviewer2_relevance_grade",
    "reviewer2_id", "reviewer2_background", "adjudicated_grade",
    "primary_binary_qrel",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="Path to retrieval_review_v1.xlsx")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    workbook = load_workbook(args.workbook, read_only=True, data_only=True)
    if "Reviews" not in workbook.sheetnames:
        raise ValueError("Workbook must contain a 'Reviews' sheet")
    sheet = workbook["Reviews"]
    iterator = sheet.iter_rows(values_only=True)
    header = next(iterator)
    positions = {str(name): index for index, name in enumerate(header) if name is not None}
    missing = REQUIRED - positions.keys()
    if missing:
        raise ValueError(f"Workbook is missing required columns: {sorted(missing)}")

    output_rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, int]] = set()
    for excel_row, values in enumerate(iterator, start=2):
        if not values or all(value is None for value in values):
            continue
        get = lambda key: values[positions[key]]
        qid, source = str(get("question_id")).strip(), str(get("source_id")).strip()
        try:
            page = int(get("page"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid page at Reviews row {excel_row}") from exc
        key = (qid, source, page)
        if not qid or not source or page < 1 or key in seen:
            raise ValueError(f"Missing or duplicate question/source/page at Reviews row {excel_row}: {key}")
        seen.add(key)

        grade = str(get("adjudicated_grade")).strip().lower()
        if grade not in {"0", "1", "2", "uncertain"}:
            raise ValueError(f"Invalid adjudicated grade at Reviews row {excel_row}: {grade}")
        expected_binary = {"2": "1", "1": "0", "0": "0", "uncertain": "uncertain"}[grade]
        actual_binary = str(get("primary_binary_qrel")).strip().lower()
        if actual_binary != expected_binary:
            raise ValueError(f"Primary binary qrel mismatch at Reviews row {excel_row}")

        output_rows.append({
            "question_id": qid,
            "question": str(get("question") or "").strip(),
            "source_id": source,
            "page": str(page),
            "reviewer1_grade": str(get("relevance_grade")).strip().lower(),
            "reviewer1_id": str(get("reviewer_id") or "").strip(),
            "reviewer1_background": str(get("reviewer_background") or "").strip(),
            "reviewer2_grade": str(get("reviewer2_relevance_grade")).strip().lower(),
            "reviewer2_id": str(get("reviewer2_id") or "").strip(),
            "reviewer2_background": str(get("reviewer2_background") or "").strip(),
            "adjudicated_grade": grade,
            "primary_binary_qrel": actual_binary,
            "label_provenance": "independent human coach review; adjudicated; retrieval-generated non-exhaustive candidate pool",
        })

    if not output_rows:
        raise ValueError("No review rows found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Exported {len(output_rows)} coach-reviewed judgments for {len({r['question_id'] for r in output_rows})} questions to {args.output}")
    print("Workbook page text and quoted passages were not exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

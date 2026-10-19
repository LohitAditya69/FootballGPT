#!/usr/bin/env python3
"""Score existing dev rankings against provisional workbook page judgments."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
QRELS = ROOT / "reports/retrieval_workbook_review_qrels_v1.csv"
RANKINGS = ROOT / "reports/dense_retrieval_development_per_question.csv"
DETAILS = ROOT / "reports/retrieval_workbook_review_evaluation_v1.csv"
REPORT = ROOT / "reports/retrieval_workbook_review_evaluation_v1.md"
K = 5
METHODS = {
    "BM25_fixed": "Fixed BM25",
    "Dense": "Dense MiniLM",
    "Hybrid_25D": "BM25 + 25% dense",
    "Hybrid_50D": "BM25 + 50% dense",
    "Hybrid_75D": "BM25 + 75% dense",
    "BM25G_current": "Current BM25 + graph baseline",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parse_top5(value: str) -> list[tuple[str, int]]:
    pages = []
    for item in value.split(";"):
        item = item.strip()
        if not item:
            continue
        source, page = item.rsplit(" p.", 1)
        pages.append((source.strip(), int(page)))
    return pages[:K]


def metrics(ranked: list[tuple[str, int]], judged: dict[tuple[str, int], str], relevant_grades: set[str]) -> dict[str, float]:
    top = ranked[:K]
    gains = [grade for page in top if (grade := judged.get(page)) in {"0", "1", "2"}]
    hits = [rank for rank, page in enumerate(top, 1) if judged.get(page) in relevant_grades]
    denominator = sum(grade in relevant_grades for grade in judged.values())
    return {
        "P@5": len(hits) / K,
        "Recall@5": len(hits) / denominator if denominator else 0.0,
        "MRR": 1 / hits[0] if hits else 0.0,
        "Judged@5": len(gains) / K,
    }


def ndcg5(ranked: list[tuple[str, int]], judged: dict[tuple[str, int], str]) -> float:
    def gain(grade: str | None) -> float:
        return (2 ** int(grade) - 1) if grade in {"0", "1", "2"} else 0.0

    dcg = sum(gain(judged.get(page)) / math.log2(rank + 1) for rank, page in enumerate(ranked[:K], 1))
    ideal = sorted((gain(grade) for grade in judged.values() if grade in {"0", "1", "2"}), reverse=True)[:K]
    idcg = sum(value / math.log2(rank + 1) for rank, value in enumerate(ideal, 1))
    return dcg / idcg if idcg else 0.0


def main() -> int:
    qrels: dict[str, dict[tuple[str, int], str]] = defaultdict(dict)
    questions: dict[str, str] = {}
    for row in read_csv(QRELS):
        qid = row["question_id"]
        key = (row["source_id"], int(row["page"]))
        if key in qrels[qid]:
            raise ValueError(f"Duplicate qrel: {qid} {key}")
        qrels[qid][key] = row["adjudicated_grade"]
        questions[qid] = row["question"]

    rank_rows = read_csv(RANKINGS)
    rank_by_id = {row["dev_id"]: row for row in rank_rows}
    if set(qrels) != set(rank_by_id):
        raise ValueError(f"Question ID mismatch: qrels-only={sorted(set(qrels)-set(rank_by_id))}, rankings-only={sorted(set(rank_by_id)-set(qrels))}")

    detail_by_id: dict[str, dict[str, str | float | int]] = {}
    summary: dict[str, dict[str, float]] = {}
    paired: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    method_results: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for qid in sorted(qrels):
        judged = qrels[qid]
        detail_by_id[qid] = {
            "question_id": qid,
            "question": questions[qid],
            "reviewed_pages": sum(g in {"0", "1", "2"} for g in judged.values()),
            "direct_pages": sum(g == "2" for g in judged.values()),
            "partial_pages": sum(g == "1" for g in judged.values()),
            "uncertain_pages": sum(g == "uncertain" for g in judged.values()),
        }
    for method in METHODS:
        values_for_method = []
        for qid in sorted(qrels):
            ranked = parse_top5(rank_by_id[qid][f"{method}_top5"])
            if len(ranked) != K:
                raise ValueError(f"Expected {K} ranked pages for {qid}/{method}, got {len(ranked)}")
            judged = qrels[qid]
            direct = metrics(ranked, judged, {"2"})
            inclusive = metrics(ranked, judged, {"1", "2"})
            graded = ndcg5(ranked, judged)
            item = detail_by_id[qid]
            for label, metric_values in (("direct", direct), ("direct_or_partial", inclusive)):
                for name, value in metric_values.items():
                    item[f"{method}_{label}_{name}"] = value
            item[f"{method}_nDCG@5"] = graded
            item[f"{method}_top5"] = "; ".join(f"{source} p.{page}" for source, page in ranked)
            method_results[method][qid] = direct
            values_for_method.append((direct, inclusive, graded))
        summary[method] = {
            **{f"direct_{metric}": mean(v[0][metric] for v in values_for_method) for metric in ("P@5", "Recall@5", "MRR", "Judged@5")},
            **{f"inclusive_{metric}": mean(v[1][metric] for v in values_for_method) for metric in ("P@5", "Recall@5", "MRR", "Judged@5")},
            "nDCG@5": mean(v[2] for v in values_for_method),
        }

    # Per-question comparisons use direct-support metrics; this is the workbook's strict primary qrel.
    for other in METHODS:
        if other == "BM25_fixed":
            continue
        for metric in ("P@5", "Recall@5", "MRR", "Judged@5"):
            better = tied = worse = 0
            for qid in sorted(qrels):
                delta = method_results[other][qid][metric] - method_results["BM25_fixed"][qid][metric]
                better += delta > 1e-9
                tied += abs(delta) <= 1e-9
                worse += delta < -1e-9
            paired[other][metric] = [better, tied, worse]

    details = [detail_by_id[qid] for qid in sorted(detail_by_id)]
    fieldnames = list(details[0])
    with DETAILS.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(details)

    grade_counts = defaultdict(int)
    rater1 = defaultdict(int)
    rater2 = defaultdict(int)
    for row in read_csv(QRELS):
        grade_counts[row["adjudicated_grade"]] += 1
        rater1[row["reviewer1_id"]] += 1
        rater2[row["reviewer2_id"]] += 1

    lines = [
        "# Retrieval evaluation using prototype workbook judgments",
        "",
        "## Scope and provenance",
        "",
        f"This rescored the existing top-five development rankings for {len(qrels)} questions against {sum(map(len, qrels.values())):,} page judgments exported from the user's review workbook. The workbook was not modified. It contains two scripted reviewer profiles ({', '.join(sorted(rater1))} and {', '.join(sorted(rater2))}), not independent human or coach judgments; all results below are prototype-only and must not be reported as human-reviewed reliability.",
        "",
        f"Adjudicated labels: {grade_counts['2']} direct (grade 2), {grade_counts['1']} partial (grade 1), {grade_counts['0']} not relevant (grade 0), and {grade_counts['uncertain']} uncertain. Uncertain pages are excluded from graded gains and relevance denominators. The workbook's candidate pages are not exhaustive; unjudged pages in a returned top five count as misses in precision and are exposed via Judged@5, so these scores are conservative and candidate-pool dependent.",
        "",
        "The stricter primary view treats only grade 2 as relevant. A sensitivity view treats grades 1 and 2 as relevant. nDCG@5 uses gain 3 for direct support and gain 1 for partial support. These definitions preserve the workbook rubric without collapsing partial support into direct support silently.",
        "",
        "## Strict direct-support results",
        "",
        "P@5 uses all five returned pages in the denominator. Recall@5 uses the judged direct-support pages per question. MRR is the reciprocal rank of the first direct-support page. Judged@5 is the fraction of returned pages assigned grade 0, 1, or 2 rather than uncertain or unjudged.",
        "",
        "| Method | P@5 | Recall@5 | MRR | Judged@5 |",
        "|---|---:|---:|---:|---:|",
    ]
    for method, label in METHODS.items():
        m = summary[method]
        lines.append(f"| {label} | {m['direct_P@5']:.3f} | {m['direct_Recall@5']:.3f} | {m['direct_MRR']:.3f} | {m['direct_Judged@5']:.3f} |")
    lines += ["", "## Graded and inclusive sensitivity views", "", "| Method | nDCG@5 (2>1>0) | P@5 (grades 1–2) | Recall@5 (grades 1–2) |", "|---|---:|---:|---:|"]
    for method, label in METHODS.items():
        m = summary[method]
        lines.append(f"| {label} | {m['nDCG@5']:.3f} | {m['inclusive_P@5']:.3f} | {m['inclusive_Recall@5']:.3f} |")
    lines += ["", "## Paired outcomes vs fixed BM25", "", "Better / tied / worse by question, under the strict direct-support view:", "", "| Method | P@5 | Recall@5 | MRR | Judged@5 |", "|---|---:|---:|---:|---:|"]
    for method, label in METHODS.items():
        if method == "BM25_fixed":
            continue
        vals = [" / ".join(str(int(n)) for n in paired[method][metric]) for metric in ("P@5", "Recall@5", "MRR", "Judged@5")]
        lines.append(f"| {label} | " + " | ".join(vals) + " |")
    lines += [
        "",
        "## Interpretation and next action",
        "",
        "These results show how the current prototype rankings align with this workbook's labels; they do not establish factual correctness, coach agreement, or general retrieval quality. The reviewer IDs and backgrounds in the workbook describe scripted profiles, and the labels were generated from a candidate pool that included retrieved pages. Treat small differences as diagnostic only. Keep production retrieval settings unchanged pending an actual independent human review with candidate-pool expansion and adjudication.",
        "",
        "The prior AI-qrel comparison is preserved in `dense_retrieval_development_comparison.md`. This report is an additional workbook-label view, not a replacement for that baseline or a held-out evaluation. Per-question details and judged coverage are in `retrieval_workbook_review_evaluation_v1.csv`.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Rescored {len(qrels)} questions using {sum(map(len, qrels.values()))} workbook judgments")
    for method, label in METHODS.items():
        m = summary[method]
        print(f"{label}: direct P@5={m['direct_P@5']:.3f}, R@5={m['direct_Recall@5']:.3f}, MRR={m['direct_MRR']:.3f}, judged@5={m['direct_Judged@5']:.3f}, nDCG@5={m['nDCG@5']:.3f}")
    print(f"Wrote {REPORT.relative_to(ROOT)} and {DETAILS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

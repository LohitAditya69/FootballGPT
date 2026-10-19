#!/usr/bin/env python3
"""Evaluate the live API retrieval path against provisional workbook qrels."""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api.config import settings
from backend.api.schemas import AskRequest
from backend.api.service import TacticalService

OLD_DEV = ROOT / "reports/retrieval_development_questions.csv"
V2_QUESTIONS = ROOT / "reports/retrieval_benchmark_v2_questions.csv"
QRELS = ROOT / "reports/retrieval_workbook_review_qrels_v1.csv"
DETAILS = ROOT / "reports/retrieval_backend_workbook_evaluation_v1.csv"
FUSION_DETAILS = ROOT / "reports/retrieval_backend_fusion_sweep_v1.csv"
REPORT = ROOT / "reports/retrieval_backend_workbook_evaluation_v1.md"
K = settings.top_k_tactical
GRAPH_WEIGHTS = (0.0, 0.1, 0.2, 0.3)


def load_questions() -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    with OLD_DEV.open(encoding="utf-8-sig", newline="") as stream:
        questions.extend(csv.DictReader(stream))
    with V2_QUESTIONS.open(encoding="utf-8-sig", newline="") as stream:
        questions.extend(
            {"dev_id": row["question_id"], "question": row["question"]}
            for row in csv.DictReader(stream)
            if row["split"] == "dev"
        )
    return questions


def load_qrels() -> dict[str, dict[tuple[str, int], str]]:
    qrels: dict[str, dict[tuple[str, int], str]] = defaultdict(dict)
    with QRELS.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            page = (row["source_id"], int(row["page"]))
            if page in qrels[row["question_id"]]:
                raise ValueError(f"Duplicate qrel: {row['question_id']} {page}")
            qrels[row["question_id"]][page] = row["adjudicated_grade"]
    return qrels


def evaluate(service: TacticalService, questions: list[dict[str, str]], qrels: dict[str, dict[tuple[str, int], str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in questions:
        qid = item["dev_id"]
        response = service.ask(AskRequest(question=item["question"]))
        ranked = [(passage.source_id, int(passage.page)) for passage in response.tactical_passages]
        labels = qrels[qid]
        direct = {page for page, grade in labels.items() if grade == "2"}
        hits = [rank for rank, page in enumerate(ranked, 1) if labels.get(page) == "2"]
        gains = [3 if labels.get(page) == "2" else 1 if labels.get(page) == "1" else 0 for page in ranked]
        ideal = sorted((3 if grade == "2" else 1 if grade == "1" else 0 for grade in labels.values()), reverse=True)[:K]
        dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
        idcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(ideal, 1))
        rows.append({
            "question_id": qid,
            "status": response.status,
            "support_status": response.support_status,
            "direct_pages_in_qrels": len(direct),
            "direct_P@3": len(hits) / K,
            "direct_Recall@3": len(hits) / len(direct) if direct else 0.0,
            "direct_MRR": 1 / hits[0] if hits else 0.0,
            "nDCG@3": dcg / idcg if idcg else 0.0,
            "Judged@3": sum(labels.get(page) in {"0", "1", "2"} for page in ranked) / K,
            "top3": "; ".join(f"{source} p.{page}" for source, page in ranked),
        })
    return rows


def mean_metrics(rows: list[dict[str, object]]) -> dict[str, float]:
    metrics = ("direct_P@3", "direct_Recall@3", "direct_MRR", "nDCG@3", "Judged@3")
    return {key: mean(float(row[key]) for row in rows) for key in metrics}


def main() -> int:
    questions, qrels = load_questions(), load_qrels()
    if len(questions) != 42 or {row["dev_id"] for row in questions} != set(qrels):
        raise ValueError("Expected exactly the 42 workbook development questions")

    service = TacticalService(settings)
    service.initialize()
    rows = evaluate(service, questions, qrels)

    with DETAILS.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    summaries = mean_metrics(rows)

    fusion_rows = []
    for graph_weight in GRAPH_WEIGHTS:
        service.tactical_weights = {"V": 1.0 - graph_weight, "G": graph_weight}
        candidate_rows = evaluate(service, questions, qrels)
        fusion_rows.append({"graph_weight": graph_weight, **mean_metrics(candidate_rows)})
    with FUSION_DETAILS.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fusion_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(fusion_rows)
    answered = sum(row["status"] == "answered" for row in rows)
    no_direct_qrels = sum(int(row["direct_pages_in_qrels"]) == 0 for row in rows)
    report = [
        "# Backend-aligned workbook development evaluation",
        "",
        "This run calls `TacticalService.ask()` for all 42 development questions, so it evaluates the current backend path: tactical-chunk filtering, quality/abstention gate, config-driven BM25/graph fusion, fixed-chunk citation validation, and the API top-3 output.",
        "",
        "The workbook labels are provisional scripted profiles over a retrieval-generated candidate set. This is a development diagnostic, not human/coach review or exhaustive relevance evaluation. No v1/v2 held-out labels were used.",
        "",
        f"Questions: {len(rows)}. API answered: {answered}; abstained: {len(rows) - answered}. Questions with no grade-2 workbook page: {no_direct_qrels}.",
        "",
        "| Metric | Backend result |",
        "|---|---:|",
    ]
    report.extend(f"| {key} | {value:.3f} |" for key, value in summaries.items())
    report += [
        "",
        "## Exploratory V:G weight sensitivity",
        "",
        "The following one-factor sweep changes only the relative graph weight while calling the same backend path. These values use the same provisional qrels that the sweep is selecting against; do not treat the best row as an independent result or automatically promote it.",
        "",
        "| Graph weight (G) | Direct P@3 | Direct Recall@3 | Direct MRR | nDCG@3 | Judged@3 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    report.extend(f"| {row['graph_weight']:.2f} | {row['direct_P@3']:.3f} | {row['direct_Recall@3']:.3f} | {row['direct_MRR']:.3f} | {row['nDCG@3']:.3f} | {row['Judged@3']:.3f} |" for row in fusion_rows)
    report += [
        "",
        "In this same-label sensitivity sweep, BM25-only (G=0) is slightly higher than the configured G=0.10 setting on P@3, Recall@3, and nDCG@3, and ties MRR and judged coverage. This is an exploratory candidate, not a promotion: the qrels are scripted, retrieval-generated, and reused to select the candidate.",
        "",
        "Because the workbook qrels come from a retrieval-generated pool and seven questions have no grade-2 page, answer/abstention status is reported separately and these metrics must not be read as proof of factual answerability.",
        "",
        "Per-question results are in `retrieval_backend_workbook_evaluation_v1.csv`; weight sensitivity values are in `retrieval_backend_fusion_sweep_v1.csv`.",
        "",
    ]
    REPORT.write_text("\n".join(report), encoding="utf-8")
    print(f"Questions={len(rows)} answered={answered} abstained={len(rows)-answered} no_direct_qrels={no_direct_qrels}")
    print("Metrics=" + repr({key: round(value, 4) for key, value in summaries.items()}))
    print(f"Fusion sweep={fusion_rows}")
    print(f"Reports: {REPORT.relative_to(ROOT)}, {DETAILS.relative_to(ROOT)}, {FUSION_DETAILS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

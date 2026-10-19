#!/usr/bin/env python3
"""Explore BM25/graph settings against the provisional workbook qrels.

This reports development candidates only. It never writes the serving config.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.retrieval.combined_retriever import normalize_channel
from backend.retrieval.graph_retriever import load_graph, retrieve_graph
from backend.retrieval.vector_retriever import build_bm25_index, retrieve_bm25

DEV_OLD = ROOT / "reports/retrieval_development_questions.csv"
DEV_V2 = ROOT / "reports/retrieval_benchmark_v2_questions.csv"
QRELS = ROOT / "reports/retrieval_workbook_review_qrels_v1.csv"
CHUNKS = ROOT / "backend/data/uefa_evidence_chunks.jsonl"
GRAPH = ROOT / "backend/data/retrieval_graph.json"
CONFIG = ROOT / "backend/retrieval/ranking_config.json"
DETAILS = ROOT / "reports/retrieval_workbook_tuning_v1.csv"
REPORT = ROOT / "reports/retrieval_workbook_tuning_v1.md"
POOL_DETAILS = ROOT / "reports/retrieval_workbook_candidate_pool_v1.csv"
K, POOL = 5, 20
POOL_VALUES = (20, 40, 60, 100, 150, 200)
K1_VALUES = (0.8, 1.2, 1.5, 2.0)
B_VALUES = (0.25, 0.5, 0.75, 1.0)
GRAPH_WEIGHTS = (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5)


def load_questions() -> list[dict[str, str]]:
    with DEV_OLD.open(encoding="utf-8-sig", newline="") as stream:
        questions = list(csv.DictReader(stream))
    with DEV_V2.open(encoding="utf-8-sig", newline="") as stream:
        questions.extend(
            {"dev_id": row["question_id"], "question": row["question"]}
            for row in csv.DictReader(stream)
            if row["split"] == "dev"
        )
    return questions


def read_qrels() -> dict[str, dict[tuple[str, int], str]]:
    result: dict[str, dict[tuple[str, int], str]] = defaultdict(dict)
    with QRELS.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["source_id"], int(row["page"]))
            if key in result[row["question_id"]]:
                raise ValueError(f"Duplicate workbook qrel: {row['question_id']} {key}")
            result[row["question_id"]][key] = row["adjudicated_grade"]
    return result


def fuse_pages(bm25_rows: list[dict], graph_rows: list[dict], graph_weight: float) -> list[tuple[str, int, float]]:
    bm = normalize_channel(bm25_rows, "vector_score")
    graph = normalize_channel(graph_rows, "graph_score")
    docs = {row["evidence_id"]: row for row in bm25_rows + graph_rows}
    scores: dict[tuple[str, int], float] = {}
    for evidence_id in set(bm) | set(graph):
        row = docs[evidence_id]
        key = (row["source_id"], int(row["page"]))
        value = (1 - graph_weight) * bm.get(evidence_id, 0.0) + graph_weight * graph.get(evidence_id, 0.0)
        scores[key] = max(scores.get(key, float("-inf")), value)
    return sorted(((source, page, value) for (source, page), value in scores.items()), key=lambda row: (-row[2], row[0], row[1]))


def score(ranked: list[tuple[str, int, float]], judged: dict[tuple[str, int], str]) -> dict[str, float]:
    top = [(source, page) for source, page, _ in ranked[:K]]
    relevant = {page for page, grade in judged.items() if grade == "2"}
    hits = [rank for rank, page in enumerate(top, 1) if judged.get(page) == "2"]
    gains = [3 if judged.get(page) == "2" else 1 if judged.get(page) == "1" else 0 for page in top]
    ideal = sorted((3 if grade == "2" else 1 if grade == "1" else 0 for grade in judged.values()), reverse=True)[:K]
    dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
    idcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(ideal, 1))
    return {
        "direct_P@5": len(hits) / K,
        "direct_Recall@5": len(hits) / len(relevant) if relevant else 0.0,
        "direct_MRR": 1 / hits[0] if hits else 0.0,
        "nDCG@5": dcg / idcg if idcg else 0.0,
        "Judged@5": sum(judged.get(page) in {"0", "1", "2"} for page in top) / K,
    }


def summarize(per_question: list[dict[str, float]]) -> dict[str, float]:
    return {key: mean(row[key] for row in per_question) for key in per_question[0]}


def main() -> int:
    questions, qrels = load_questions(), read_qrels()
    if len(questions) != 42 or {q["dev_id"] for q in questions} != set(qrels):
        raise ValueError("Expected exactly the 42 workbook development questions")
    graph = load_graph(GRAPH)
    graph_rows = {q["dev_id"]: retrieve_graph(q["question"], graph, POOL) for q in questions}
    bm25_cache: dict[tuple[float, float], dict[str, list[dict]]] = {}
    trials: list[dict[str, float]] = []
    per_config: dict[tuple[float, float, float], list[dict[str, float]]] = {}
    for k1 in K1_VALUES:
        for b in B_VALUES:
            index = build_bm25_index(CHUNKS, k1=k1, b=b)
            rows_by_id = {q["dev_id"]: retrieve_bm25(q["question"], index, POOL) for q in questions}
            bm25_cache[(k1, b)] = rows_by_id
            for graph_weight in GRAPH_WEIGHTS:
                values = [
                    score(fuse_pages(rows_by_id[q["dev_id"]], graph_rows[q["dev_id"]], graph_weight), qrels[q["dev_id"]])
                    for q in questions
                ]
                per_config[(k1, b, graph_weight)] = values
                trials.append({"k1": k1, "b": b, "graph_weight": graph_weight, **summarize(values)})

    # Exploratory ordering: graded nDCG@5, then direct P@5, MRR, recall, and
    # lower graph contribution. It is not a production selection criterion.
    trials.sort(key=lambda row: (row["nDCG@5"], row["direct_P@5"], row["direct_MRR"], row["direct_Recall@5"], -row["graph_weight"]), reverse=True)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    current = (float(config["bm25"]["k1"]), float(config["bm25"]["b"]), float(config["weights"]["beta"] / (config["weights"]["alpha"] + config["weights"]["beta"])))
    if current not in per_config:
        raise ValueError(f"Current serving setting {current} is outside the explored grid")
    current_summary = summarize(per_config[current])
    best = trials[0]
    best_key = (best["k1"], best["b"], best["graph_weight"])

    # Diagnose retrieval depth independently using the unchanged serving
    # weights and BM25 parameters. This is also exploratory, not promotion.
    pool_rows: list[dict[str, float]] = []
    current_index = build_bm25_index(CHUNKS, k1=current[0], b=current[1])
    for pool_size in POOL_VALUES:
        values = []
        for question in questions:
            qid = question["dev_id"]
            bm_rows = retrieve_bm25(question["question"], current_index, pool_size)
            gr_rows = retrieve_graph(question["question"], graph, pool_size)
            values.append(score(fuse_pages(bm_rows, gr_rows, current[2]), qrels[qid]))
        pool_rows.append({"candidate_pool": pool_size, **summarize(values)})

    fields = ["rank", "k1", "b", "graph_weight", "direct_P@5", "direct_Recall@5", "direct_MRR", "nDCG@5", "Judged@5"]
    with DETAILS.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for rank, row in enumerate(trials, 1):
            writer.writerow({"rank": rank, **row})

    with POOL_DETAILS.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["candidate_pool", "direct_P@5", "direct_Recall@5", "direct_MRR", "nDCG@5", "Judged@5"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(pool_rows)

    report = [
        "# Provisional workbook-based BM25/graph tuning sweep",
        "",
        "This is a development-only, exploratory sweep over the 42 workbook questions. It did not read v1 or v2 held-out labels and did not modify `backend/retrieval/ranking_config.json`.",
        "",
        "The workbook qrels are provisional: they use scripted reviewer profiles and a retrieval-generated candidate pool. Results are not human/coach validation. The tuning grid reuses those labels, so the highest score is subject to selection bias and must not be treated as a reliable generalization estimate.",
        "",
        f"Search space: {len(trials)} combinations; `k1={K1_VALUES}`, `b={B_VALUES}`, graph weights `{GRAPH_WEIGHTS}`. Objective ordering for this exploratory report: nDCG@5 (grade 2 gain 3, grade 1 gain 1), then direct-support P@5, direct-support MRR, direct-support recall, then lower graph weight.",
        "",
        "## Current serving setting vs exploratory top candidate",
        "",
        "| Setting | k1 | b | graph weight | direct P@5 | direct Recall@5 | direct MRR | nDCG@5 | Judged@5 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    def line(label: str, params: tuple[float, float, float], values: dict[str, float]) -> str:
        return f"| {label} | {params[0]:g} | {params[1]:g} | {params[2]:.2f} | {values['direct_P@5']:.3f} | {values['direct_Recall@5']:.3f} | {values['direct_MRR']:.3f} | {values['nDCG@5']:.3f} | {values['Judged@5']:.3f} |"
    report += [line("Current serving config", current, current_summary), line("Top exploratory candidate", best_key, summarize(per_config[best_key]))]
    report += [
        "",
        "The top candidate is BM25-only (`k1=1.5`, `b=0.25`, graph weight 0). Against the current setting it ties direct P@5, improves direct MRR and nDCG@5 slightly, and lowers direct recall. No candidate is a consistent improvement across all metrics; do not promote it to serving config from this sweep.",
        "",
        "The next refinement should improve the judgment set or test a separately specified retrieval change with independent review. In a spot audit, the workbook marked UEFA Europa Conference League 2024/25 page 30 as direct support for a question about centre-backs defending large spaces in a high line, but the quoted text discusses Chelsea full-backs leaving teammates 1v1. This is a concrete example of why the current metrics are diagnostic only.",
        "",
        "All 128 grid results are in `retrieval_workbook_tuning_v1.csv`.",
        "",
        "## Candidate-pool depth diagnostic",
        "",
        "The following sweep holds BM25 parameters and BM25/graph weights at the current serving settings, varying only the number of candidates retrieved per channel before page fusion. It reuses the same provisional workbook labels and is therefore diagnostic, not an independent estimate.",
        "",
        "| Candidates per channel | direct P@5 | direct Recall@5 | direct MRR | nDCG@5 | Judged@5 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    report += [f"| {int(row['candidate_pool'])} | {row['direct_P@5']:.3f} | {row['direct_Recall@5']:.3f} | {row['direct_MRR']:.3f} | {row['nDCG@5']:.3f} | {row['Judged@5']:.3f} |" for row in pool_rows]
    report += [
        "",
        "A wider candidate pool can increase direct hits and recall, but the gain is small and nDCG is essentially flat; judged coverage also drops because more unjudged pages enter the ranking. Do not increase production depth from these labels alone. The per-depth values are in `retrieval_workbook_candidate_pool_v1.csv`.",
        "",
    ]
    REPORT.write_text("\n".join(report), encoding="utf-8")
    print(f"Questions: {len(questions)}; trials: {len(trials)}")
    print(f"Current {current}: {current_summary}")
    print(f"Best {best_key}: {summarize(per_config[best_key])}")
    print(f"Candidate-pool sweep: {pool_rows}")
    print(f"Reports: {REPORT.relative_to(ROOT)}, {DETAILS.relative_to(ROOT)}, {POOL_DETAILS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

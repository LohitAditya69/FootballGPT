#!/usr/bin/env python3
"""Compare dense, BM25, and BM25+dense page retrieval on dev qrels only."""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path
from statistics import mean
from importlib.metadata import version

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.retrieval.combined_retriever import normalize_channel
from backend.retrieval.graph_retriever import load_graph, retrieve_graph
from backend.retrieval.vector_retriever import build_bm25_index, retrieve_bm25
from sentence_transformers import SentenceTransformer

BASE_DEV = ROOT / "reports/retrieval_development_questions.csv"
V2_QUESTIONS = ROOT / "reports/retrieval_benchmark_v2_questions.csv"
CHUNKS = ROOT / "backend/data/uefa_evidence_chunks.jsonl"
GRAPH = ROOT / "backend/data/retrieval_graph.json"
CONFIG = ROOT / "backend/retrieval/ranking_config.json"
DETAILS = ROOT / "reports/dense_retrieval_development_per_question.csv"
REPORT = ROOT / "reports/dense_retrieval_development_comparison.md"
MODEL_REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
POOL = 20
K = 5


def load_questions() -> list[dict[str, str]]:
    rows = list(csv.DictReader(BASE_DEV.open(encoding="utf-8-sig", newline="")))
    with V2_QUESTIONS.open(encoding="utf-8-sig", newline="") as stream:
        rows.extend(r for r in csv.DictReader(stream) if r["split"] == "dev")
    return rows


def verify_page_disjoint(questions: list[dict[str, str]]) -> None:
    """Read held-out page references only to enforce the split boundary."""
    locked_refs: set[tuple[str, int]] = set()
    source_map = {
        "UCL": "uefa-ucl-2024-25",
        "UWCL": "uefa-uwcl-2024-25",
        "Women's EURO": "uefa-weuro-2025",
        "Women’s EURO": "uefa-weuro-2025",
    }
    pattern = re.compile(r"(UCL|UWCL|Women[’']s EURO)\s+pp?\.?\s*(\d+)(?:[-–](\d+))?", re.I)
    with (ROOT / "reports/evaluation_seed_questions.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            for match in pattern.finditer(row.get("gold_qrel_pages", "")):
                source = source_map.get(match.group(1), source_map.get(match.group(1).upper()))
                if source:
                    lo, hi = int(match.group(2)), int(match.group(3) or match.group(2))
                    locked_refs.update((source, page) for page in range(lo, hi + 1))

    dev_refs = set().union(*(parse_qrels(q) for q in questions))
    overlap = dev_refs & locked_refs
    if overlap:
        raise ValueError(f"Development qrels overlap v1 locked pages: {sorted(overlap)}")

    with V2_QUESTIONS.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["split"] != "test":
                continue
            test_ref = (row["source_id"], int(row["relevant_pages"]))
            if test_ref in dev_refs or test_ref in locked_refs:
                raise ValueError(f"Development qrels overlap v2 held-out target: {row['question_id']} {test_ref}")


def parse_qrels(question: dict[str, str]) -> set[tuple[str, int]]:
    result = set()
    for item in question.get("relevant_pages", "").split(";"):
        item = item.strip()
        if not item:
            continue
        if ":p." in item:
            source, page = item.rsplit(":p.", 1)
            result.add((source, int(page)))
        else:
            result.add((question["source_id"], int(item)))
    return result


def rank_pages(rows: list[dict], score_key: str) -> list[tuple[str, int, float]]:
    best: dict[tuple[str, int], float] = {}
    for row in rows:
        key = (row["source_id"], int(row["page"]))
        best[key] = max(best.get(key, float("-inf")), float(row[score_key]))
    return sorted(((source, page, score) for (source, page), score in best.items()), key=lambda x: (-x[2], x[0], x[1]))


def rank_fusion(
    channel_rows: list[tuple[list[dict], str, float]],
) -> list[tuple[str, int, float]]:
    normalized: list[tuple[dict[str, float], float]] = []
    docs: dict[str, dict] = {}
    for rows, field, weight in channel_rows:
        normalized.append((normalize_channel(rows, field), weight))
        docs.update({row["evidence_id"]: row for row in rows})
    evidence_ids = set().union(*(scores for scores, _ in normalized))
    page_scores: dict[tuple[str, int], float] = {}
    for evidence_id in evidence_ids:
        row = docs[evidence_id]
        combined = sum(weight * scores.get(evidence_id, 0.0) for scores, weight in normalized)
        key = (row["source_id"], int(row["page"]))
        page_scores[key] = max(page_scores.get(key, float("-inf")), combined)
    return sorted(((s, p, v) for (s, p), v in page_scores.items()), key=lambda x: (-x[2], x[0], x[1]))


def score(ranked: list[tuple[str, int, float]], qrels: set[tuple[str, int]]) -> dict[str, float]:
    top = [(source, page) for source, page, _ in ranked[:K]]
    hits = [rank for rank, item in enumerate(top, 1) if item in qrels]
    return {
        "P@5": len(hits) / K,
        "Recall@5": len(hits) / len(qrels) if qrels else 0.0,
        "MRR": 1 / hits[0] if hits else 0.0,
    }


def main() -> int:
    questions = load_questions()
    if len(questions) != 42:
        raise ValueError(f"Expected 42 development questions, found {len(questions)}")
    if len({q.get("dev_id") or q.get("question_id") for q in questions}) != len(questions):
        raise ValueError("Development question IDs must be unique")
    verify_page_disjoint(questions)
    for q in questions:
        if not parse_qrels(q):
            raise ValueError(f"Missing development qrels: {q.get('dev_id') or q.get('question_id')}")

    chunks = [json.loads(line) for line in CHUNKS.open(encoding="utf-8") if line.strip()]
    texts = [row["text"] for row in chunks]
    model_path = Path(os.environ.get(
        "FOOTBALLGPT_EMBEDDING_MODEL",
        Path.home() / ".cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / MODEL_REVISION,
    ))
    if not model_path.exists():
        raise FileNotFoundError(f"Cached model revision not found: {model_path}")
    model = SentenceTransformer(str(model_path), device=None)
    doc_embeddings = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True)
    query_embeddings = model.encode([q["question"] for q in questions], batch_size=32, normalize_embeddings=True, show_progress_bar=True)
    dense_scores = np.asarray(query_embeddings) @ np.asarray(doc_embeddings).T

    fixed_bm25 = build_bm25_index(CHUNKS, k1=1.5, b=0.75)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    configured_bm25 = build_bm25_index(CHUNKS, k1=config["bm25"]["k1"], b=config["bm25"]["b"])
    graph = load_graph(GRAPH)

    all_details = []
    method_rows: dict[str, list[dict[str, float]]] = {
        "BM25_fixed": [], "Dense": [], "Hybrid_25D": [], "Hybrid_50D": [], "Hybrid_75D": [], "BM25G_current": []
    }
    for query_index, q in enumerate(questions):
        qid = q.get("dev_id") or q["question_id"]
        qrels = parse_qrels(q)
        dense_order = np.argsort(-dense_scores[query_index], kind="stable")[:POOL]
        dense_rows = [{**chunks[i], "vector_score": float(dense_scores[query_index, i])} for i in dense_order]
        fixed_rows = retrieve_bm25(q["question"], fixed_bm25, POOL)
        configured_rows = retrieve_bm25(q["question"], configured_bm25, POOL)
        graph_rows = retrieve_graph(q["question"], graph, POOL)

        dense_rank = rank_pages(dense_rows, "vector_score")
        fixed_rank = rank_pages(fixed_rows, "vector_score")
        current_bm25g_rank = rank_fusion([
            (configured_rows, "vector_score", config["weights"]["alpha"]),
            (graph_rows, "graph_score", config["weights"]["beta"]),
        ])

        candidates = [
            ("BM25_fixed", fixed_rank),
            ("Dense", dense_rank),
            ("Hybrid_25D", rank_fusion([(fixed_rows, "vector_score", .75), (dense_rows, "vector_score", .25)])),
            ("Hybrid_50D", rank_fusion([(fixed_rows, "vector_score", .50), (dense_rows, "vector_score", .50)])),
            ("Hybrid_75D", rank_fusion([(fixed_rows, "vector_score", .25), (dense_rows, "vector_score", .75)])),
            ("BM25G_current", current_bm25g_rank),
        ]
        detail = {
            "dev_id": qid,
            "question": q["question"],
            "relevant_pages": "; ".join(f"{s}:p.{p}" for s, p in sorted(qrels)),
            "annotation_status": q.get("annotation_status", "AI-assisted; incomplete"),
        }
        for name, ranked in candidates:
            values = score(ranked, qrels)
            method_rows[name].append(values)
            detail.update({f"{name}_{metric}": value for metric, value in values.items()})
            detail[f"{name}_top5"] = "; ".join(f"{s} p.{p}" for s, p, _ in ranked[:K])
        all_details.append(detail)

    with DETAILS.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_details[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_details)

    summary = {
        method: {metric: mean(row[metric] for row in rows) for metric in ("P@5", "Recall@5", "MRR")}
        for method, rows in method_rows.items()
    }
    comparisons = {}
    for method in summary:
        if method == "BM25_fixed":
            continue
        comparisons[method] = {}
        for metric in ("P@5", "Recall@5", "MRR"):
            diffs = [
                row[metric] - baseline[metric]
                for row, baseline in zip(method_rows[method], method_rows["BM25_fixed"])
            ]
            comparisons[method][metric] = {
                "better": sum(delta > 1e-9 for delta in diffs),
                "tie": sum(abs(delta) <= 1e-9 for delta in diffs),
                "worse": sum(delta < -1e-9 for delta in diffs),
            }
    best_hybrid = max(("Hybrid_25D", "Hybrid_50D", "Hybrid_75D"), key=lambda name: (summary[name]["MRR"], summary[name]["Recall@5"], summary[name]["P@5"]))
    lines = [
        "# Dense retrieval development comparison",
        "",
        "Scope: 42 development questions only. No v1 or v2 held-out questions were read for selection. The current development qrels are AI-assisted, incomplete candidate-page labels; these metrics are provisional and are not human relevance judgments.",
        "",
        f"Model: `sentence-transformers/all-MiniLM-L6-v2`, cached model revision `{MODEL_REVISION}`, mean-pooled 384-dimensional embeddings with L2 normalization. Document chunks and queries use the same model. Similarity is cosine similarity.",
        f"Runtime used: Python {sys.version.split()[0]}, sentence-transformers {version('sentence-transformers')}, PyTorch {version('torch')}, Transformers {version('transformers')}, NumPy {version('numpy')}. Dependencies are pinned in `requirements-embedding.txt`.",
        "",
        "BM25 fixed uses `k1=1.5`, `b=0.75`. Hybrid scores min-max normalize the top-20 chunk results from BM25 and dense retrieval per query, fuse the union of evidence IDs, then rank pages by their best chunk score. The current BM25+G row uses the unchanged `backend/retrieval/ranking_config.json` settings.",
        "",
        "P@5 counts relevant pages in the top five divided by five; Recall@5 counts retrieved labeled relevant pages divided by the number of labeled relevant pages; MRR uses the first relevant page.",
        "",
        "| Method | P@5 | Recall@5 | MRR |",
        "|---|---:|---:|---:|",
    ]
    labels = {
        "BM25_fixed": "Fixed BM25",
        "Dense": "Dense MiniLM",
        "Hybrid_25D": "BM25 + 25% dense",
        "Hybrid_50D": "BM25 + 50% dense",
        "Hybrid_75D": "BM25 + 75% dense",
        "BM25G_current": "Current BM25 + graph baseline",
    }
    for name, label in labels.items():
        m = summary[name]
        lines.append(f"| {label} | {m['P@5']:.3f} | {m['Recall@5']:.3f} | {m['MRR']:.3f} |")
    lines += ["", "Per-question outcomes versus fixed BM25 (better / tied / worse):", "", "| Method | P@5 | Recall@5 | MRR |", "|---|---:|---:|---:|"]
    for name in labels:
        if name == "BM25_fixed":
            continue
        cells = []
        for metric in ("P@5", "Recall@5", "MRR"):
            c = comparisons[name][metric]
            cells.append(f"{c['better']} / {c['tie']} / {c['worse']}")
        lines.append(f"| {labels[name]} | " + " | ".join(cells) + " |")
    lines += [
        "",
        f"Highest-scoring hybrid by the predeclared development priority MRR, then Recall@5, then P@5: `{best_hybrid}`. This is a development selection only, not a production configuration change.",
        "",
        "## Limitations and decision",
        "",
        "- Qrels are incomplete and AI-assisted; the human review packet must be completed before treating small metric differences as meaningful.",
        "- Results come from one 42-question development set and one model revision; no significance or broad generalization claim is made.",
        "- Keep the current BM25 and graph configuration unchanged until reviewed qrels are available and an improvement is consistent across relevant metrics and questions.",
        "- Per-question results are in `dense_retrieval_development_per_question.csv`.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Questions: {len(questions)}; chunks: {len(chunks)}; embedding dimension: {doc_embeddings.shape[1]}")
    for method, metrics in summary.items():
        print(method, " ".join(f"{metric}={metrics[metric]:.3f}" for metric in ("P@5", "Recall@5", "MRR")))
    print(f"Highest hybrid by dev criteria: {best_hybrid}")
    print(f"Reports: {REPORT.relative_to(ROOT)}, {DETAILS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

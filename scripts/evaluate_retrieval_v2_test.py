#!/usr/bin/env python3
"""Run one held-out retrieval evaluation on the v2 test split."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.retrieval.combined_retriever import normalize_channel
from backend.retrieval.graph_retriever import load_graph, retrieve_graph
from backend.retrieval.vector_retriever import build_bm25_index, load_bm25_index, load_index, retrieve_bm25, retrieve_vector

QUESTIONS = ROOT / "reports/retrieval_benchmark_v2_questions.csv"
CONFIG = ROOT / "backend/retrieval/ranking_config.json"
CHUNKS = ROOT / "backend/data/uefa_evidence_chunks.jsonl"
TFIDF = ROOT / "backend/data/uefa_tfidf_index.json"
BM25 = ROOT / "backend/data/uefa_bm25_index.json"
GRAPH = ROOT / "backend/data/retrieval_graph.json"
OUT_MD = ROOT / "reports/retrieval_v2_heldout_evaluation.md"
OUT_CSV = ROOT / "reports/retrieval_v2_heldout_per_question.csv"
K, POOL = 5, 20


def page_rank(rows: list[dict], field: str) -> list[tuple[str, int, float]]:
    pages: dict[tuple[str, int], float] = {}
    for r in rows:
        key = (r["source_id"], int(r["page"]))
        pages[key] = max(pages.get(key, float("-inf")), float(r[field]))
    return sorted(((s, p, v) for (s, p), v in pages.items()), key=lambda x: (-x[2], x[0], x[1]))


def fused(v_rows: list[dict], g_rows: list[dict], v_weight: float, g_weight: float) -> list[tuple[str, int, float]]:
    v = normalize_channel(v_rows, "vector_score")
    g = normalize_channel(g_rows, "graph_score")
    docs = {r["evidence_id"]: r for r in v_rows + g_rows}
    pages: dict[tuple[str, int], float] = {}
    for eid in set(v) | set(g):
        doc = docs[eid]
        key = (doc["source_id"], int(doc["page"]))
        value = v_weight * v.get(eid, 0) + g_weight * g.get(eid, 0)
        pages[key] = max(pages.get(key, float("-inf")), value)
    return sorted(((s, p, v) for (s, p), v in pages.items()), key=lambda x: (-x[2], x[0], x[1]))


def one_metric(ranked: list[tuple[str, int, float]], source: str, page: int) -> dict[str, float]:
    top = [(s, p) for s, p, _ in ranked[:K]]
    rank = next((n for n, x in enumerate(top, 1) if x == (source, page)), None)
    hit = (source, page) in top
    return {"P@5": float(hit) / K, "Recall@5": float(hit), "MRR": 1 / rank if rank else 0.0}


def fmt(ranked: list[tuple[str, int, float]]) -> str:
    return "; ".join(f"{s} p.{p}" for s, p, _ in ranked[:K])


def main() -> int:
    with QUESTIONS.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["split"] == "test"]
    if len(rows) != 20:
        raise ValueError(f"Expected 20 frozen v2 held-out questions, found {len(rows)}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    tfidf, selected_bm25 = load_index(TFIDF), load_bm25_index(BM25)
    fixed_bm25 = build_bm25_index(CHUNKS, k1=1.5, b=0.75)
    graph = load_graph(GRAPH)
    alpha, beta = config["weights"]["alpha"], config["weights"]["beta"]
    denom = alpha + beta
    results, columns = [], {name: [] for name in ("TFIDF", "BM25_fixed", "selected")}
    for q in rows:
        query, source, page = q["question"], q["source_id"], int(q["relevant_pages"])
        tf_rows = retrieve_vector(query, tfidf, POOL)
        fixed_rows = retrieve_bm25(query, fixed_bm25, POOL)
        sel_rows = retrieve_bm25(query, selected_bm25, POOL)
        g_rows = retrieve_graph(query, graph, POOL)
        rankings = {
            "TFIDF": page_rank(tf_rows, "vector_score"),
            "BM25_fixed": page_rank(fixed_rows, "vector_score"),
            "selected": fused(sel_rows, g_rows, alpha / denom, beta / denom),
        }
        mets = {name: one_metric(rank, source, page) for name, rank in rankings.items()}
        for name in columns:
            columns[name].append(mets[name])
        results.append({"question_id": q["question_id"], "question": query, "gold_page": f"{source} p.{page}", **{f"{name}_{m}": v[m] for name, v in mets.items() for m in v}, **{f"{name}_top5": fmt(rank) for name, rank in rankings.items()}})
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0])); w.writeheader(); w.writerows(results)
    avg = {name: {m: mean(row[m] for row in vals) for m in ("P@5", "Recall@5", "MRR")} for name, vals in columns.items()}
    md = ["# Retrieval benchmark v2: held-out results", "", "This is the 20-question v2 test split. Its target pages do not overlap v1 qrels, v2 development pages, or the earlier 22-question development set. The v2 questions and pages were not used for parameter selection.", "", "## Results", "", "| Method | P@5 | Recall@5 | MRR |", "|---|---:|---:|---:|"]
    for name, label in (("TFIDF", "TF-IDF"), ("BM25_fixed", "BM25 (k1=1.5, b=0.75)"), ("selected", "Frozen development-selected BM25+G")):
        x = avg[name]; md.append(f"| {label} | {x['P@5']:.3f} | {x['Recall@5']:.3f} | {x['MRR']:.3f} |")
    md += ["", "Metrics rank distinct report pages by their best chunk score. Each question has one target page. `P@5` divides by five; `Recall@5` is hit/no-hit because each item has one target page; MRR is reciprocal rank of that page.", "", "## Limits", "", "Questions and target-page labels were AI-drafted from the fixed reports, not independently judged by human coaches. Other pages may also be relevant, so the single-page labels are incomplete. The set is page-disjoint from development and v1 but remains a small pilot; do not tune against it.", "", "Per-question results: `retrieval_v2_heldout_per_question.csv`.", ""]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"V2 held-out questions: {len(rows)}")
    for name, values in avg.items():
        print(name, " ".join(f"{m}={values[m]:.3f}" for m in ("P@5", "Recall@5", "MRR")))
    print(f"Reports: {OUT_MD.relative_to(ROOT)}, {OUT_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

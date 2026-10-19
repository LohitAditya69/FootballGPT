#!/usr/bin/env python3
"""Tune lexical retrieval and graph weight on the separate UEFA development set."""

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
from backend.retrieval.vector_retriever import build_bm25_index, load_index, retrieve_bm25, retrieve_vector

DEV = ROOT / "reports/retrieval_development_questions.csv"
V2_QUESTIONS = ROOT / "reports/retrieval_benchmark_v2_questions.csv"
LOCK = ROOT / "reports/evaluation_scope_lock.md"
CHUNKS = ROOT / "backend/data/uefa_evidence_chunks.jsonl"
TFIDF = ROOT / "backend/data/uefa_tfidf_index.json"
GRAPH = ROOT / "backend/data/retrieval_graph.json"
OUT = ROOT / "reports/retrieval_development_evaluation.md"
DETAILS = ROOT / "reports/retrieval_development_per_question.csv"
K = 5
POOL = 4 * K


def page_rank(rows: list[dict], score_field: str) -> list[tuple[str, int, float]]:
    scores: dict[tuple[str, int], float] = {}
    for row in rows:
        key = (row["source_id"], int(row["page"]))
        scores[key] = max(scores.get(key, float("-inf")), float(row[score_field]))
    return sorted(((src, page, score) for (src, page), score in scores.items()), key=lambda x: (-x[2], x[0], x[1]))


def fused_rank(v_rows: list[dict], g_rows: list[dict], graph_weight: float) -> list[tuple[str, int, float]]:
    v = normalize_channel(v_rows, "vector_score")
    g = normalize_channel(g_rows, "graph_score")
    docs = {r["evidence_id"]: r for r in v_rows + g_rows}
    pages: dict[tuple[str, int], float] = {}
    for evidence_id in set(v) | set(g):
        doc = docs[evidence_id]
        score = (1 - graph_weight) * v.get(evidence_id, 0.0) + graph_weight * g.get(evidence_id, 0.0)
        key = (doc["source_id"], int(doc["page"]))
        pages[key] = max(pages.get(key, float("-inf")), score)
    return sorted(((src, page, score) for (src, page), score in pages.items()), key=lambda x: (-x[2], x[0], x[1]))


def parse_qrels(q: dict) -> set[tuple[str, int]]:
    """Parse `source:p.12;source:p.13`; accept legacy integer labels too."""
    raw = (q.get("relevant_pages") or "").strip()
    refs: set[tuple[str, int]] = set()
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        if ":p." in item:
            source, page = item.rsplit(":p.", 1)
            refs.add((source.strip(), int(page)))
        else:
            refs.add((q["source_id"], int(item)))
    return refs


def score(ranked: list[tuple[str, int, float]], qrels: set[tuple[str, int]]) -> dict[str, float]:
    top = [(s, p) for s, p, _ in ranked[:K]]
    hits = [i for i, pair in enumerate(top, 1) if pair in qrels]
    return {"P@5": len(hits) / K, "Recall@5": len(hits) / len(qrels) if qrels else 0.0, "MRR": 1 / hits[0] if hits else 0.0}


def macro(rows: list[dict], prefix: str) -> dict[str, float]:
    return {m: mean(row[f"{prefix}_{m}"] for row in rows) for m in ("P@5", "Recall@5", "MRR")}


def main() -> int:
    questions = list(csv.DictReader(DEV.open(encoding="utf-8-sig", newline="")))
    with V2_QUESTIONS.open(encoding="utf-8-sig", newline="") as f:
        questions.extend({"dev_id": r["question_id"], "question": r["question"], "source_id": r["source_id"], "relevant_pages": r["relevant_pages"], "topic": r["topic"], "annotation_basis": r["annotation_basis"], "annotation_status": r.get("annotation_status", "") } for r in csv.DictReader(f) if r["split"] == "dev")
    if len(questions) < 20:
        raise ValueError("Development set must contain at least 20 labeled questions")
    if len({q["dev_id"] for q in questions}) != len(questions):
        raise ValueError("Development question IDs must be unique")

    # Guard against overlap with the locked evaluation pages.
    with (ROOT / "reports/evaluation_seed_questions.csv").open(encoding="utf-8-sig", newline="") as f:
        locked_rows = list(csv.DictReader(f))
    locked_refs = set()
    import re
    source_map = {"UCL": "uefa-ucl-2024-25", "UWCL": "uefa-uwcl-2024-25", "Women's EURO": "uefa-weuro-2025", "Women’s EURO": "uefa-weuro-2025"}
    pattern = re.compile(r"(UCL|UWCL|Women[’']s EURO)\s+pp?\.?\s*(\d+)(?:[-–](\d+))?", re.I)
    for row in locked_rows:
        for m in pattern.finditer(row.get("gold_qrel_pages", "")):
            label = m.group(1)
            src = source_map.get(label, source_map.get(label.upper()))
            if not src:
                continue
            start, end = int(m.group(2)), int(m.group(3) or m.group(2))
            locked_refs.update((src, p) for p in range(start, end + 1))
    for q in questions:
        overlap = parse_qrels(q) & locked_refs
        if overlap:
            raise ValueError(f"Development page overlaps locked evaluation: {q['dev_id']} {sorted(overlap)}")
    with V2_QUESTIONS.open(encoding="utf-8-sig", newline="") as f:
        v2_rows = list(csv.DictReader(f))
    dev_pages = set().union(*(parse_qrels(q) for q in questions))
    for q in v2_rows:
        if q["split"] == "test":
            overlap = parse_qrels(q) & (dev_pages | locked_refs)
            if overlap:
                raise ValueError(f"V2 held-out page overlaps development or v1 locked pages: {q['question_id']} {sorted(overlap)}")

    tfidf_index = load_index(TFIDF)
    graph = load_graph(GRAPH)
    candidate_params = [(k1, b) for k1 in (0.8, 1.2, 1.5, 2.0) for b in (0.25, 0.5, 0.75, 1.0)]
    graph_weights = (0.0, 0.1, 0.2, 0.3, 0.5)
    caches = []
    for q in questions:
        query = q["question"]
        caches.append({
            "q": q,
            "tfidf": retrieve_vector(query, tfidf_index, POOL),
            "graph": retrieve_graph(query, graph, POOL),
        })

    trials = []
    for k1, b in candidate_params:
        bm25_index = build_bm25_index(CHUNKS, k1=k1, b=b)
        bm25_rows = [retrieve_bm25(c["q"]["question"], bm25_index, POOL) for c in caches]
        for graph_weight in graph_weights:
            per_q = []
            for c, bm in zip(caches, bm25_rows):
                rank = fused_rank(bm, c["graph"], graph_weight)
                per_q.append(score(rank, parse_qrels(c["q"])))
            metrics = {m: mean(row[m] for row in per_q) for m in ("P@5", "Recall@5", "MRR")}
            trials.append({"k1": k1, "b": b, "graph_weight": graph_weight, **metrics})

    # Predeclared selection: maximize development MRR, then Recall@5, then P@5;
    # deterministic tie-break prefers the simpler BM25-only result.
    best = max(trials, key=lambda x: (x["MRR"], x["Recall@5"], x["P@5"], -x["graph_weight"], -abs(x["k1"] - 1.5), -abs(x["b"] - 0.75)))
    fixed_bm25 = build_bm25_index(CHUNKS, k1=1.5, b=0.75)
    details = []
    baselines = {name: [] for name in ("TFIDF", "BM25_fixed", "selected")}
    for c in caches:
        q = c["q"]
        fixed_rows = retrieve_bm25(q["question"], fixed_bm25, POOL)
        chosen_index = build_bm25_index(CHUNKS, k1=best["k1"], b=best["b"])
        chosen_rows = retrieve_bm25(q["question"], chosen_index, POOL)
        tf_rank = page_rank(c["tfidf"], "vector_score")
        fixed_rank = page_rank(fixed_rows, "vector_score")
        selected_rank = fused_rank(chosen_rows, c["graph"], best["graph_weight"])
        qrels = parse_qrels(q)
        values = [score(tf_rank, qrels), score(fixed_rank, qrels), score(selected_rank, qrels)]
        for key, val in zip(baselines, values):
            baselines[key].append(val)
        details.append({"dev_id": q["dev_id"], "question": q["question"], "relevant_pages": "; ".join(f"{s}:p.{p}" for s,p in sorted(qrels)), "annotation_status": q.get("annotation_status", "AI-assisted; incomplete"), **{f"{name}_{m}": v[m] for name, v in zip(baselines, values) for m in v}, "TFIDF_top5": "; ".join(f"{s} p.{p}" for s,p,_ in tf_rank[:K]), "BM25_top5": "; ".join(f"{s} p.{p}" for s,p,_ in fixed_rank[:K]), "selected_top5": "; ".join(f"{s} p.{p}" for s,p,_ in selected_rank[:K])})

    with DETAILS.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(details[0]))
        writer.writeheader(); writer.writerows(details)
    summary = {name: {m: mean(row[m] for row in rows) for m in ("P@5", "Recall@5", "MRR")} for name, rows in baselines.items()}
    md = ["# Retrieval development evaluation", "", f"Development set: {len(questions)} AI-drafted questions with source-qualified, multi-page qrels outside v1 and v2 held-out qrels. Labels are AI-assisted candidate-page judgments from the fixed report text; they are incomplete and not human coach judgments.", "", "P@5 counts relevant pages in the top five divided by five; Recall@5 counts retrieved relevant pages divided by all labeled relevant pages; MRR uses the first relevant page.", "", "## Baseline and selected development metrics", "", "| Method | P@5 | Recall@5 | MRR |", "|---|---:|---:|---:|"]
    for key, label in (("TFIDF", "TF-IDF"), ("BM25_fixed", "BM25 (k1=1.5, b=0.75)"), ("selected", "Selected BM25 + graph setting")):
        x=summary[key]; md.append(f"| {label} | {x['P@5']:.3f} | {x['Recall@5']:.3f} | {x['MRR']:.3f} |")
    md += ["", "## Selected parameters", "", f"- BM25 `k1={best['k1']}`, `b={best['b']}`; graph weight `β={best['graph_weight']:.1f}` with lexical weight `1−β`.", "- Selection criterion fixed before tuning: maximize development MRR, then Recall@5, then P@5; ties prefer less graph contribution and values nearer the conventional BM25 baseline.", f"- Grid searched {len(trials)} combinations over `k1={tuple(k for k in (0.8,1.2,1.5,2.0))}`, `b={tuple(b for b in (0.25,0.5,0.75,1.0))}`, and graph weights `{graph_weights}`.", "- This is development-only tuning. Neither v1's 12 questions nor the 20 v2 held-out questions were used to select parameters.", "", "## Limitations", "", "- Labels are AI-assisted candidate-page judgments, not exhaustive page-by-page adjudication and not coach review; omitted relevant pages remain possible.", "- The original target page remains relevant. Additional pages were included only when their report text directly addresses the question; retrieval rank alone is not a relevance judgment.", "- On the v2 held-out set, selected BM25+G has slightly higher MRR than fixed BM25 but lower P@5 and Recall@5; this is not a clear overall gain. Do not tune against v2 held-out questions.", "", "Per-question ranks and qrel provenance are in `retrieval_development_per_question.csv`.", "", "## Human review and semantic retrieval status", "", "The current multi-page qrels remain AI-assisted and incomplete. `retrieval_human_review_packet_v1.csv` contains 768 blinded development question-page candidates with full page text and blank judgment fields. It draws candidates from TF-IDF, fixed BM25, graph retrieval, and current labels, but is not exhaustive; reviewers should add relevant pages missed by the pool. See `retrieval_human_review_protocol.md` for rating, independent review, adjudication, and agreement instructions.", "", "Dense retrieval has not been evaluated. `all-MiniLM-L6-v2` files are cached locally, but neither project Python environment has an inference runtime. Installing `sentence-transformers` failed because the environment could not resolve `pypi.org`. No lexical proxy is reported as a dense result. The production configuration remains the baseline pending human qrels and a reproducible embedding runtime.", ""]
    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"Development questions: {len(questions)}; non-overlap guard: passed")
    print(f"Selected k1={best['k1']} b={best['b']} graph_weight={best['graph_weight']}")
    for name, values in summary.items():
        print(name, " ".join(f"{m}={values[m]:.3f}" for m in ("P@5", "Recall@5", "MRR")))
    print(f"Reports: {OUT.relative_to(ROOT)}, {DETAILS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

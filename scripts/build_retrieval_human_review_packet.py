#!/usr/bin/env python3
"""Build a blinded page-level review packet from development questions."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.retrieval.graph_retriever import load_graph, retrieve_graph
from backend.retrieval.vector_retriever import (
    build_bm25_index,
    load_index,
    retrieve_bm25,
    retrieve_vector,
)
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DEV = ROOT / "reports/retrieval_development_questions.csv"
V2_DEV = ROOT / "reports/retrieval_benchmark_v2_questions.csv"
CHUNKS = ROOT / "backend/data/uefa_evidence_chunks.jsonl"
TFIDF = ROOT / "backend/data/uefa_tfidf_index.json"
GRAPH = ROOT / "backend/data/retrieval_graph.json"
OUT = ROOT / "reports/retrieval_human_review_packet_v1.csv"
PAGES_PER_CHANNEL = 10
MODEL_REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"


def refs(raw: str, default_source: str) -> set[tuple[str, int]]:
    result = set()
    for token in raw.split(";"):
        token = token.strip()
        if not token:
            continue
        if ":p." in token:
            source, page = token.rsplit(":p.", 1)
            result.add((source, int(page)))
        else:
            result.add((default_source, int(token)))
    return result


def load_questions() -> list[dict[str, str]]:
    rows = list(csv.DictReader(BASE_DEV.open(encoding="utf-8-sig", newline="")))
    with V2_DEV.open(encoding="utf-8-sig", newline="") as stream:
        rows.extend(r for r in csv.DictReader(stream) if r["split"] == "dev")
    return rows


def page_rank(rows: list[dict], score_key: str) -> list[tuple[str, int]]:
    best: dict[tuple[str, int], float] = {}
    for row in rows:
        key = (row["source_id"], int(row["page"]))
        best[key] = max(best.get(key, float("-inf")), float(row.get(score_key, 0)))
    return [key for key, _ in sorted(best.items(), key=lambda item: (-item[1], item[0]))]


def stable_blind_order(qid: str, ref: tuple[str, int]) -> str:
    value = f"footballgpt-human-review-v1|{qid}|{ref[0]}|{ref[1]}"
    return hashlib.sha256(value.encode()).hexdigest()


def main() -> int:
    questions = load_questions()
    tfidf = load_index(TFIDF)
    graph = load_graph(GRAPH)
    bm25 = build_bm25_index(CHUNKS, k1=1.5, b=0.75)

    page_text: dict[tuple[str, int], list[str]] = defaultdict(list)
    for line in CHUNKS.open(encoding="utf-8"):
        row = json.loads(line)
        page_text[(row["source_id"], int(row["page"]))].append(row["text"])

    chunks = [json.loads(line) for line in CHUNKS.open(encoding="utf-8") if line.strip()]
    model_path = Path(os.environ.get(
        "FOOTBALLGPT_EMBEDDING_MODEL",
        Path.home() / ".cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / MODEL_REVISION,
    ))
    if not model_path.exists():
        raise FileNotFoundError(f"Cached model revision not found: {model_path}")
    model = SentenceTransformer(str(model_path), device=None)
    doc_embeddings = model.encode([row["text"] for row in chunks], batch_size=32, normalize_embeddings=True, show_progress_bar=False)

    packet = []
    for question in questions:
        qid, query = question.get("dev_id") or question["question_id"], question["question"]
        current_qrels = refs(question.get("relevant_pages", ""), question["source_id"])
        candidates = set(current_qrels)
        candidates.update(page_rank(retrieve_vector(query, tfidf, 50), "vector_score")[:PAGES_PER_CHANNEL])
        candidates.update(page_rank(retrieve_bm25(query, bm25, 50), "vector_score")[:PAGES_PER_CHANNEL])
        candidates.update(page_rank(retrieve_graph(query, graph, 50), "graph_score")[:PAGES_PER_CHANNEL])
        query_embedding = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
        dense_scores = np.asarray(doc_embeddings) @ np.asarray(query_embedding)
        dense_indices = np.argsort(-dense_scores, kind="stable")[:50]
        dense_rows = [{**chunks[i], "vector_score": float(dense_scores[i])} for i in dense_indices]
        candidates.update(page_rank(dense_rows, "vector_score")[:PAGES_PER_CHANNEL])

        for ref in sorted(candidates, key=lambda item: stable_blind_order(qid, item)):
            sections = page_text.get(ref, [])
            packet.append({
                "review_id": f"{qid}-{ref[0]}-p{ref[1]}",
                "question_id": qid,
                "question": query,
                "source_id": ref[0],
                "page": ref[1],
                "page_text": "\n\n".join(sections),
                "relevance_grade": "",
                "supporting_quote_or_section": "",
                "reason_or_caveat": "",
                "reviewer_id": "",
                "reviewer_background": "",
                "review_date": "",
                "adjudication_note": "",
            })

    fields = list(packet[0])
    with OUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(packet)
    print(f"Questions: {len(questions)}; candidate question-page pairs: {len(packet)}")
    print(f"Reviewer fields are blank. Packet: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

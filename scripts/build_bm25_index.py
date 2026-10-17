#!/usr/bin/env python3
"""Build the development-selected BM25 index over fixed UEFA chunks."""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.retrieval.vector_retriever import build_bm25_index, save_bm25_index

config = json.loads((ROOT / "backend/retrieval/ranking_config.json").read_text(encoding="utf-8"))
K1 = config["bm25"]["k1"]
B = config["bm25"]["b"]
result = build_bm25_index(ROOT / "backend/data/uefa_evidence_chunks.jsonl", k1=K1, b=B)
output = ROOT / "backend/data/uefa_bm25_index.json"
save_bm25_index(result, output)
print(f"Built BM25 index for {result['document_count']} UEFA chunks (k1={K1}, b={B}).")
print(f"Index: {output.relative_to(ROOT)}")

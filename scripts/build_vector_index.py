#!/usr/bin/env python3
"""Create the sparse vector index for the fixed UEFA text chunks."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.retrieval.vector_retriever import build_index

result = build_index(ROOT / "backend/data/uefa_evidence_chunks.jsonl", ROOT / "backend/data/uefa_tfidf_index.json")
print(f"Built sparse TF-IDF vectors for {result['document_count']} UEFA chunks.")
print("Note: this is a lexical vector baseline, not a dense neural embedding model.")

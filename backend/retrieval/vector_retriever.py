"""TF-IDF vector retrieval over page-cited UEFA chunks (sparse, lexical V)."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+(?:['’][a-z0-9]+)?", re.I)
STOPWORDS = frozenset("a an and are as at be been being by can could did do does for from had has have how i in into is it its may might of on or should than that the their them then there these this those to was were what when where which who will with would your".split())


def tokenize(text: str) -> list[str]:
    words = [w.casefold().replace("’", "'") for w in TOKEN_RE.findall(text)]
    words = [w for w in words if w not in STOPWORDS and len(w) > 1]
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


def build_index(evidence_jsonl: str | Path, output_json: str | Path) -> dict[str, Any]:
    docs = []
    df: Counter[str] = Counter()
    for line in Path(evidence_jsonl).open(encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        counts = Counter(tokenize(row["text"]))
        df.update(counts.keys())
        docs.append({"evidence_id": row["evidence_id"], "citation": row["citation"], "source_id": row["source_id"], "page": row["page"], "text": row["text"], "tf": counts})
    n = len(docs)
    idf = {term: math.log(1 + (n + 1) / (freq + 1)) for term, freq in df.items()}
    packed_docs = []
    inverted: dict[str, list[list[float | int]]] = {t: [] for t in idf}
    for doc_id, doc in enumerate(docs):
        raw = {t: (1 + math.log(count)) * idf[t] for t, count in doc["tf"].items()}
        norm = math.sqrt(sum(v * v for v in raw.values())) or 1.0
        sparse = {t: round(v / norm, 8) for t, v in raw.items()}
        for term, weight in sparse.items():
            inverted[term].append([doc_id, weight])
        packed_docs.append({k: doc[k] for k in ("evidence_id", "citation", "source_id", "page", "text")})
    payload = {
        "schema_version": "tfidf-v1",
        "method": "sublinear-TF, smoothed-IDF, L2-normalized unigram + adjacent-bigram sparse vectors",
        "document_count": n,
        "documents": packed_docs,
        "idf": idf,
        "vectors": inverted,
    }
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return payload


def load_index(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "tfidf-v1":
        raise ValueError("Unsupported vector index schema")
    return payload


def retrieve_vector(query: str, index: dict[str, Any], top_k: int = 5) -> list[dict[str, Any]]:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    qtf = Counter(tokenize(query))
    idf = index["idf"]
    qraw = {t: (1 + math.log(c)) * idf[t] for t, c in qtf.items() if t in idf}
    qnorm = math.sqrt(sum(v * v for v in qraw.values())) or 1.0
    qvec = {t: v / qnorm for t, v in qraw.items()}
    scores: Counter[int] = Counter()
    for term, qweight in qvec.items():
        for doc_id, dweight in index["vectors"].get(term, []):
            scores[doc_id] += qweight * dweight
    chosen = sorted(scores, key=lambda i: (-scores[i], index["documents"][i]["evidence_id"]))[:top_k]
    return [{**{k: index["documents"][i][k] for k in ("evidence_id", "citation", "source_id", "page", "text")}, "vector_score": round(min(1.0, max(0.0, scores[i])), 6)} for i in chosen]

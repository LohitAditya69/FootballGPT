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


def build_bm25_index(evidence_jsonl: str | Path, *, k1: float = 1.5, b: float = 0.75) -> dict[str, Any]:
    """Build a compact BM25 lexical index using the shared transparent tokenizer."""
    documents = []
    df: Counter[str] = Counter()
    for line in Path(evidence_jsonl).open(encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        tokens = tokenize(row["text"])
        tf = Counter(tokens)
        df.update(tf.keys())
        documents.append({**{k: row[k] for k in ("evidence_id", "citation", "source_id", "page", "text")}, "tf": tf, "length": len(tokens)})
    if k1 <= 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requires k1 > 0 and 0 <= b <= 1")
    return {"schema_version": "bm25-v1", "k1": k1, "b": b, "document_count": len(documents), "average_length": sum(d["length"] for d in documents) / max(1, len(documents)), "document_frequency": df, "documents": documents}


def save_bm25_index(index: dict[str, Any], output_json: str | Path) -> None:
    """Write a JSON-serializable BM25 index for reuse by the retrieval pipeline."""
    payload = {**index, "document_frequency": dict(index["document_frequency"]), "documents": [{**{k: d[k] for k in ("evidence_id", "citation", "source_id", "page", "text", "length")}, "tf": dict(d["tf"])} for d in index["documents"]]}
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def load_bm25_index(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "bm25-v1":
        raise ValueError("Unsupported BM25 index schema")
    return payload


def retrieve_bm25(query: str, index: dict[str, Any], top_k: int = 5) -> list[dict[str, Any]]:
    """Retrieve with conventional BM25 (k1=1.5, b=0.75), fixed in advance."""
    if index.get("schema_version") != "bm25-v1":
        raise ValueError("Unsupported BM25 index schema")
    if top_k < 1:
        raise ValueError("top_k must be positive")
    query_tf = Counter(tokenize(query))
    n = index["document_count"]
    avg_len = index["average_length"] or 1.0
    k1, b = index["k1"], index["b"]
    scores = []
    for doc in index["documents"]:
        score = 0.0
        for term, qfreq in query_tf.items():
            tf = doc["tf"].get(term, 0)
            if not tf:
                continue
            df = index["document_frequency"].get(term, 0)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            norm = tf + k1 * (1 - b + b * doc["length"] / avg_len)
            score += qfreq * idf * tf * (k1 + 1) / norm
        if score > 0:
            scores.append((score, doc))
    scores.sort(key=lambda pair: (-pair[0], pair[1]["evidence_id"]))
    return [{**{k: d[k] for k in ("evidence_id", "citation", "source_id", "page", "text")}, "vector_score": round(float(score), 6)} for score, d in scores[:top_k]]

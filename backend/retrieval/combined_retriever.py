"""Combine V, G and H candidate scores using a fixed weighted formula."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import networkx as nx

from backend.retrieval.graph_retriever import retrieve_graph
from backend.retrieval.historical_retriever import retrieve_historical
from backend.retrieval.vector_retriever import retrieve_bm25, retrieve_vector

CONFIG_PATH = Path(__file__).with_name("ranking_config.json")


def load_ranking_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config.get("schema_version") != "score-fusion-v1":
        raise ValueError("Unsupported ranking configuration schema")
    return config


def normalize_channel(rows: list[dict[str, Any]], field: str) -> dict[str, float]:
    """Deterministic per-query min-max normalization over returned candidates."""
    raw = {row["evidence_id"]: float(row[field]) for row in rows}
    if not raw:
        return {}
    low, high = min(raw.values()), max(raw.values())
    if high == low:
        return {key: 1.0 for key in raw}
    return {key: max(0.0, min(1.0, (score - low) / (high - low))) for key, score in raw.items()}


def retrieve_combined(
    query: str,
    *,
    graph: nx.MultiDiGraph,
    vector_index: dict[str, Any],
    historical_cases: Iterable[dict[str, Any]],
    query_event: dict[str, Any],
    exclude_match_id: str,
    top_k: int = 10,
    alpha: float | None = None,
    beta: float | None = None,
    gamma: float | None = None,
) -> list[dict[str, Any]]:
    """Retrieve mixed-source evidence and rank with S = αV + βG + γH.

    V and G candidates are cited UEFA chunks; H candidates are train-only
    historical event situations. Each channel is min-max normalized within its
    own returned top-4k pool before fusion. Missing channel results score zero.
    """
    if top_k < 1:
        raise ValueError("top_k must be positive")
    defaults = load_ranking_config()["weights"]
    weights = {
        "V": defaults["alpha"] if alpha is None else alpha,
        "G": defaults["beta"] if beta is None else beta,
        "H": defaults["gamma"] if gamma is None else gamma,
    }
    if any(not isinstance(v, (int, float)) or v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("α, β, and γ must be nonnegative and at least one must be positive")
    total = float(sum(weights.values()))
    weights = {k: float(v) / total for k, v in weights.items()}
    pool = max(4 * top_k, 20)
    if vector_index.get("schema_version") == "bm25-v1":
        v_rows = retrieve_bm25(query, vector_index, pool)
    else:
        v_rows = retrieve_vector(query, vector_index, pool)
    g_rows = retrieve_graph(query, graph, pool)
    h_rows = (
        retrieve_historical(query_event, historical_cases, exclude_match_id=exclude_match_id, top_k=pool)
        if weights["H"] > 0 else []
    )
    v_norm = normalize_channel(v_rows, "vector_score")
    g_norm = normalize_channel(g_rows, "graph_score")
    h_norm = normalize_channel(h_rows, "historical_score")
    v_raw = {r["evidence_id"]: r for r in v_rows}
    g_raw = {r["evidence_id"]: r for r in g_rows}
    h_raw = {r["evidence_id"]: r for r in h_rows}
    all_ids = set(v_norm) | set(g_norm) | set(h_norm)
    ranked = []
    for evidence_id in all_ids:
        scores = {"V": v_norm.get(evidence_id, 0.0), "G": g_norm.get(evidence_id, 0.0), "H": h_norm.get(evidence_id, 0.0)}
        score = sum(weights[k] * scores[k] for k in weights)
        row = v_raw.get(evidence_id) or g_raw.get(evidence_id) or h_raw[evidence_id]
        ranked.append({**row, "ranking_score": round(score, 6), "normalized_scores": {k: round(v, 6) for k, v in scores.items()}, "weights": weights})
    ranked.sort(key=lambda r: (-r["ranking_score"], r["evidence_id"]))
    return ranked[:top_k]

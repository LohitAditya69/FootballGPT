"""Small graph-only retrieval signal (G) over the frozen evidence graph."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import networkx as nx


def load_graph(path: str | Path) -> nx.MultiDiGraph:
    """Load the portable JSON graph produced by scripts/build_retrieval_graph.py."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "retrieval-graph-v2":
        raise ValueError("Unsupported retrieval graph schema")
    graph = nx.MultiDiGraph(schema_version=payload["schema_version"])
    for row in payload["nodes"]:
        node_id = row["id"]
        graph.add_node(node_id, **{k: v for k, v in row.items() if k != "id"})
    for row in payload["edges"]:
        graph.add_edge(row["source"], row["target"], key=row.get("key", 0), **{k: v for k, v in row.items() if k not in ("source", "target", "key")})
    return graph


def _matches(text: str, alias: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", text.casefold()) is not None


def retrieve_graph(query: str, graph: nx.MultiDiGraph, top_k: int = 5) -> list[dict[str, Any]]:
    """Return UEFA text chunks ranked by direct and one-hop concept-group links.

    Direct lexical concept matches score 1.0. Concepts in the same curated
    group contribute 0.25 as graph expansion. The score is normalized by the
    number of concepts matched in the query and clipped to [0, 1]. This is an
    interpretable G signal, not a standalone semantic retriever.
    """
    if top_k < 1:
        raise ValueError("top_k must be positive")
    qconcepts: set[str] = set()
    for node_id, attrs in graph.nodes(data=True):
        if attrs.get("node_type") != "tactical_concept":
            continue
        if any(_matches(query, alias) for alias in attrs.get("aliases", [])):
            qconcepts.add(node_id)
    if not qconcepts:
        return []

    # Build a one-hop concept expansion map through the curated concept groups.
    expanded: dict[str, float] = {concept: 1.0 for concept in qconcepts}
    for concept in qconcepts:
        for group in graph.successors(concept):
            if graph.nodes[group].get("node_type") != "concept_group":
                continue
            for neighbor in graph.predecessors(group):
                if neighbor != concept and graph.nodes[neighbor].get("node_type") == "tactical_concept":
                    expanded[neighbor] = max(expanded.get(neighbor, 0.0), 0.25)

    scores: dict[str, float] = {}
    matched_by_chunk: dict[str, list[str]] = {}
    for concept, weight in expanded.items():
        # Evidence points to concepts so provenance is read as source -> claim.
        # Retrieval walks this edge in reverse from concept to its evidence.
        for target in graph.predecessors(concept):
            if graph.nodes[target].get("node_type") == "uefa_text_chunk":
                scores[target] = scores.get(target, 0.0) + weight
                matched_by_chunk.setdefault(target, []).append(graph.nodes[concept]["label"])
    denominator = max(1, len(qconcepts))
    ranked = sorted(scores, key=lambda node: (-min(1.0, scores[node] / denominator), node))[:top_k]
    return [{
        "evidence_id": node,
        "citation": graph.nodes[node]["citation"],
        "source_id": graph.nodes[node]["source_id"],
        "page": graph.nodes[node]["page"],
        "graph_score": round(min(1.0, scores[node] / denominator), 6),
        "matched_concepts": sorted(set(matched_by_chunk[node])),
        "text": graph.nodes[node]["text"],
    } for node in ranked]

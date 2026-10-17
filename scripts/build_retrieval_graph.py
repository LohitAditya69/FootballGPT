#!/usr/bin/env python3
"""Build the bounded, provenance-preserving NetworkX graph used for G retrieval."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
UEFA_INPUT = ROOT / "backend/data/uefa_evidence_chunks.jsonl"
EVENT_INPUT = ROOT / "backend/data/question_event_evidence.jsonl"
TRAIN_INPUT = ROOT / "backend/data/historical_train_sample.jsonl.gz"
GRAPH_OUT = ROOT / "backend/data/retrieval_graph.json"
META_OUT = ROOT / "backend/data/retrieval_graph_manifest.json"
SCHEMA_VERSION = "retrieval-graph-v2"

# Curated vocabulary, used only to attach text/event evidence to broad tactical
# concepts. It is not an annotation of the locked questions or their answers.
CONCEPTS = {
    "attacking_transition": {"label": "Attacking transition", "aliases": ["attacking transition", "attacking transitions", "counter-attack", "counter attack", "counterattacking", "counterattack", "counterattacks", "fast attack", "quick attack", "transition to attack", "transition in attack"]},
    "defensive_transition": {"label": "Defensive transition", "aliases": ["defensive transition", "defensive transitions", "transition to defence", "transition to defense", "counter-press", "counterpress", "counter-pressing", "counterpressing", "reacting to loss of possession", "loss of possession"]},
    "build_up": {"label": "Build-up", "aliases": ["build-up", "build up", "build-up play", "playing out", "play out from the back", "progression", "progress the ball"]},
    "pressing": {"label": "Pressing", "aliases": ["pressing", "high press", "high pressing", "press", "pressing trigger", "pressing triggers", "pressing trap", "pressing traps", "pressure"]},
    "defensive_block": {"label": "Defensive block", "aliases": ["mid-block", "mid block", "low block", "high line", "defensive line", "compactness", "team compactness", "out of possession"]},
    "switching_play": {"label": "Switching play", "aliases": ["switch play", "switching play", "switch of play", "change the point of attack", "change of direction"]},
    "chance_creation": {"label": "Chance creation", "aliases": ["chance creation", "create chances", "cut-back", "cutback", "cut-backs", "cutbacks", "cross", "crosses", "through ball", "through-ball", "final third"]},
    "finishing": {"label": "Finishing", "aliases": ["finishing", "shot", "shots", "shooting", "shot selection", "shot choice", "goal scoring", "goal-scoring"]},
    "support_and_cover": {"label": "Support and cover", "aliases": ["cover", "covering", "cover shadow", "support", "supporting players", "supporting runs", "overload", "overloads", "balance"]},
    "possession_security": {"label": "Possession security", "aliases": ["secure possession", "retain possession", "ball retention", "keep the ball", "possession"]},
}
CONCEPT_GROUP = {
    "attacking_transition": "transition_play", "defensive_transition": "transition_play",
    "build_up": "possession_play", "switching_play": "possession_play",
    "possession_security": "possession_play", "pressing": "out_of_possession",
    "defensive_block": "out_of_possession", "support_and_cover": "team_structure",
    "chance_creation": "attacking_play", "finishing": "attacking_play",
}
EVENT_CONCEPT = {
    "Interception": ("defensive_transition",),
    "Ball Recovery": ("defensive_transition",),
    "Pressure": ("pressing",),
    "Shot": ("finishing",),
    "Pass": ("build_up",),
    "Carry": ("build_up",),
    "Dribble": ("chance_creation",),
    "Clearance": ("defensive_block",),
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def add_evidence_node(graph: nx.MultiDiGraph, node_id: str, **attrs: object) -> None:
    graph.add_node(node_id, **attrs)


def concept_links(graph: nx.MultiDiGraph, evidence_id: str, text: str, evidence_kind: str) -> None:
    text_folded = text.casefold()
    for concept_id, spec in CONCEPTS.items():
        matched = [alias for alias in spec["aliases"] if re.search(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", text_folded)]
        if matched:
            graph.add_edge(evidence_id, f"concept:{concept_id}", relation="mentions_concept", evidence_kind=evidence_kind, matched_aliases=sorted(set(matched)))


def main() -> int:
    try:
        if not UEFA_INPUT.is_file() or not EVENT_INPUT.is_file() or not TRAIN_INPUT.is_file():
            raise FileNotFoundError("Run scripts/prepare_evidence.py and scripts/sample_train_situations.py first.")
        uefa_rows, event_rows = read_jsonl(UEFA_INPUT), read_jsonl(EVENT_INPUT)
        graph = nx.MultiDiGraph(schema_version=SCHEMA_VERSION, graph_role="bounded evidence provenance graph for tactical retrieval")

        for concept_id, spec in CONCEPTS.items():
            node_id = f"concept:{concept_id}"
            graph.add_node(node_id, node_type="tactical_concept", concept_id=concept_id, label=spec["label"], aliases=spec["aliases"], extraction="curated_alias_lexicon")
            group = CONCEPT_GROUP[concept_id]
            group_id = f"concept_group:{group}"
            graph.add_node(group_id, node_type="concept_group", label=group.replace("_", " ").title())
            graph.add_edge(node_id, group_id, relation="belongs_to_group")

        source_ids = {}
        page_ids = {}
        for record in uefa_rows:
            source_id = record["source_id"]
            source_node = f"source:{source_id}"
            if source_id not in source_ids:
                graph.add_node(source_node, node_type="uefa_report", source_id=source_id, title=record["source_title"], file=record["source_file"], sha256=record["source_sha256"], authority="locked_uefa_reference")
                source_ids[source_id] = source_node
            page_key = (source_id, record["page"])
            if page_key not in page_ids:
                page_node = f"page:{source_id}:{record['page']}"
                graph.add_node(page_node, node_type="report_page", source_id=source_id, page=record["page"], citation=record["citation"])
                graph.add_edge(source_node, page_node, relation="has_page")
                page_ids[page_key] = page_node
            evidence_id = record["evidence_id"]
            add_evidence_node(graph, evidence_id, node_type="uefa_text_chunk", source_id=source_id, page=record["page"], citation=record["citation"], chunk_index=record["chunk_index"], text=record["text"], source_sha256=record["source_sha256"])
            graph.add_edge(page_ids[page_key], evidence_id, relation="has_chunk")
            concept_links(graph, evidence_id, record["text"], "uefa_text")

        # The event graph is limited to the pre-extracted, raw-source windows for
        # the pilot cases. It includes no question text, gold answers, qrels, or
        # annotations. Teams/players are linked only as recorded in StatsBomb.
        event_ids_seen = set()
        for record in event_rows:
            case_id = record["case_id"]
            match_node = f"match:{record['match_id']}"
            case_node = f"event_window:{case_id}"
            graph.add_node(match_node, node_type="statsbomb_match", match_id=record["match_id"], source_file=record["source_file"])
            graph.add_node(case_node, node_type="statsbomb_event_window", match_id=record["match_id"], source_evidence_id=record["evidence_id"], trigger_event_id=record["trigger_event_id"], trigger_timestamp=record["trigger_timestamp"], source_file=record["source_file"])
            graph.add_edge(case_node, match_node, relation="from_match")
            for event in record["events"]:
                raw_id = event.get("id")
                event_node = f"event:{record['match_id']}:{raw_id or event.get('index')}"
                if event_node not in event_ids_seen:
                    graph.add_node(event_node, node_type="statsbomb_event", match_id=record["match_id"], raw_event_id=raw_id, event_index=event.get("index"), period=event.get("period"), timestamp=event.get("timestamp"), event_type=event.get("type"), team=event.get("team"), player=event.get("player"), location=event.get("location"), window_offset=event.get("window_offset"), trigger=(raw_id == record["trigger_event_id"]), raw_fields=json.dumps({k: event[k] for k in ("pass", "shot", "carry", "pressure", "interception", "ball_recovery", "play_pattern", "under_pressure") if k in event}, ensure_ascii=False, separators=(",", ":")))
                    event_ids_seen.add(event_node)
                graph.add_edge(case_node, event_node, relation="contains_event", window_offset=event.get("window_offset"))
                if event.get("team"):
                    team_id = f"team:{event['team']}"
                    graph.add_node(team_id, node_type="team", name=event["team"], entity_source="StatsBomb event record")
                    graph.add_edge(event_node, team_id, relation="recorded_for_team")
                if event.get("player"):
                    player_id = f"player:{record['match_id']}:{event['player']}"
                    graph.add_node(player_id, node_type="player", name=event["player"], match_id=record["match_id"], entity_source="StatsBomb event record")
                    graph.add_edge(event_node, player_id, relation="recorded_for_player")
                for concept_id in EVENT_CONCEPT.get(event.get("type"), ()):
                    graph.add_edge(event_node, f"concept:{concept_id}", relation="event_type_indicates_concept", evidence_kind="event_type_label")

        # Generalize G using a small deterministic sample from train only. No
        # test questions, gold answers, qrels, or labels enter these nodes.
        with gzip.open(TRAIN_INPUT, "rt", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                match_id = str(row["match_id"])
                match_node = f"match:{match_id}"
                graph.add_node(match_node, node_type="statsbomb_match", match_id=match_id, source_split="train")
                case_node = f"train_case:{row['case_id']}"
                graph.add_node(case_node, node_type="train_situation", case_id=row["case_id"], match_id=match_id, source_split="train", timestamp=row.get("timestamp"), period=row.get("period"), location=row.get("location"), score_diff=row.get("score_diff"), formation=row.get("formation"), event_type=row.get("event_type"), play_pattern=row.get("play_pattern"), event_outcome=row.get("event_outcome"), under_pressure=row.get("under_pressure"), counterpress=row.get("counterpress"), feature_provenance=row.get("provenance"))
                graph.add_edge(case_node, match_node, relation="from_train_match", source_split="train")
                event_node = f"train_event:{match_id}:{row.get('event_id') or row['case_id']}"
                graph.add_node(event_node, node_type="train_event", match_id=match_id, raw_event_id=row.get("event_id"), event_type=row.get("event_type"), play_pattern=row.get("play_pattern"), location=row.get("location"), period=row.get("period"), source_split="train", source_provenance=row.get("provenance"))
                graph.add_edge(case_node, event_node, relation="triggered_by_train_event", source_split="train")
                for label, node_type, edge_type in ((row.get("team"), "team", "recorded_for_team"), (row.get("opponent"), "team", "opposed_by_team")):
                    if label:
                        entity_node = f"team:{label}"
                        graph.add_node(entity_node, node_type=node_type, name=label, entity_source="StatsBomb-derived train case")
                        graph.add_edge(case_node, entity_node, relation=edge_type, source_split="train")
                formation = row.get("formation")
                if formation:
                    formation_node = f"formation:{formation}"
                    graph.add_node(formation_node, node_type="formation", name=str(formation), entity_source="train case tactical_state; availability is sparse")
                    graph.add_edge(case_node, formation_node, relation="has_recorded_formation", source_split="train")
                for concept_id in EVENT_CONCEPT.get(row.get("event_type"), ()):
                    graph.add_edge(event_node, f"concept:{concept_id}", relation="event_type_indicates_concept", evidence_kind="StatsBomb event type", source_split="train")

        # Stable, inspectable JSON graph format (rather than pickle).
        nodes = [{"id": node_id, **attrs} for node_id, attrs in sorted(graph.nodes(data=True), key=lambda item: item[0])]
        edges = [{"source": u, "target": v, "key": key, **attrs} for u, v, key, attrs in sorted(graph.edges(keys=True, data=True), key=lambda item: (item[0], item[1], item[2]))]
        GRAPH_OUT.parent.mkdir(parents=True, exist_ok=True)
        GRAPH_OUT.write_text(json.dumps({"schema_version": SCHEMA_VERSION, "directed": True, "multigraph": True, "nodes": nodes, "edges": edges}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        node_types = Counter(d.get("node_type", "unknown") for _, d in graph.nodes(data=True))
        edge_types = Counter(d.get("relation", "unknown") for _, _, d in graph.edges(data=True))
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "builder": "scripts/build_retrieval_graph.py",
            "networkx_version": nx.__version__,
            "graph_file": str(GRAPH_OUT.relative_to(ROOT)),
            "graph_sha256": digest(GRAPH_OUT),
            "inputs": {str(p.relative_to(ROOT)): digest(p) for p in (UEFA_INPUT, EVENT_INPUT, TRAIN_INPUT)},
            "bounds": {"uefa_chunks": len(uefa_rows), "event_windows": len(event_rows), "event_records_deduplicated": len(event_ids_seen), "train_situation_sample_cap": "3 per train match", "concepts": len(CONCEPTS)},
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "node_types": dict(sorted(node_types.items())),
            "edge_types": dict(sorted(edge_types.items())),
            "method": "Page-bounded UEFA chunks linked by a curated alias lexicon; pilot event windows linked to recorded entities; deterministic train-only situation sample linked to recorded teams, sparse formations, events, and broad event-type concepts. No question text, gold answers, qrels, or evaluation annotations are graph nodes or edges.",
            "limitations": ["Concept links are lexical/curated and may miss paraphrases or contain false positives.", "Event-type-to-concept links are broad indexes, not tactical judgments.", "The graph contains the 12 locked pilot event windows and is not a general all-match graph."],
        }
        META_OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, ImportError, json.JSONDecodeError) as exc:
        print(f"Graph build failed: {exc}", file=sys.stderr)
        return 1
    print(f"Built {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges using NetworkX {nx.__version__}.")
    print(f"Graph: {GRAPH_OUT.relative_to(ROOT)}")
    print(f"Manifest: {META_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

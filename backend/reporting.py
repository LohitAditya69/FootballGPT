"""Build citation-preserving, extractive answers from retrieved football evidence."""

from __future__ import annotations

import re
from typing import Any


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", cleaned) if part.strip()]


def build_grounded_report(
    *, question: str, support_status: str, ranked_evidence: list[dict[str, Any]],
    event_window: dict[str, Any], max_passages: int = 3,
) -> dict[str, Any]:
    """Return extractive cited passages, a bounded event record, and a RGG trace.

    This deliberately does not paraphrase source material or turn the event feed
    into unseen tactical context. The resulting report is a grounded evidence
    brief, not a generative coaching recommendation.
    """
    if max_passages < 1:
        raise ValueError("max_passages must be positive")
    abstain = support_status == "not_covered"
    tactical = [] if abstain else [
        row for row in ranked_evidence if row.get("source_id") and row.get("citation")
    ]
    passages = []
    for row in tactical:
        sentences = _sentences(str(row.get("text", "")))
        if not sentences:
            continue
        # Keep one verbatim sentence so every displayed tactical claim has a
        # direct, page-level citation and cannot accidentally be synthesized.
        passages.append({
            "evidence_id": row["evidence_id"], "citation": row["citation"],
            "text": sentences[0], "ranking_score": row.get("ranking_score"),
            "normalized_scores": row.get("normalized_scores", {}),
            "matched_concepts": row.get("matched_concepts", []),
        })
        if len(passages) == max_passages:
            break

    report_text = (
        "The frozen UEFA reference set marks this question as not covered. "
        "No tactical answer is provided from these reports."
        if abstain else (
            "No page-cited passage was retrieved; abstain pending source review."
            if not passages else "Retrieved source passages are shown verbatim below. "
            "They support review of the question but do not establish missing match context."
        )
    )
    qid = str(event_window["case_id"])
    question_node = f"question:{qid}"
    evidence_nodes = []
    edges = []
    for i, passage in enumerate(passages):
        node_id = passage["evidence_id"]
        evidence_nodes.append({"id": node_id, "node_type": "uefa_text_chunk", **passage})
        edges.append({"source": question_node, "target": node_id, "relation": "retrieved_support", "rank": i + 1})
    event_node = event_window["evidence_id"]
    edges.append({"source": question_node, "target": event_node, "relation": "recorded_match_context"})
    provenance = {
        "schema_version": "rgg-provenance-v1", "question_id": qid,
        "nodes": [{"id": question_node, "node_type": "question", "text": question},
                  *evidence_nodes,
                  {"id": event_node, "node_type": "statsbomb_event_window",
                   "match_id": event_window["match_id"],
                   "trigger_event_id": event_window["trigger_event_id"],
                   "source_file": event_window["source_file"],
                   "window_rule": event_window["window_rule"]}],
        "edges": edges,
    }
    return {
        "schema_version": "grounded-report-v1", "question_id": qid,
        "question": question, "support_status": support_status,
        "answer_mode": "abstain" if abstain or not passages else "extractive_evidence_brief",
        "answer": report_text, "tactical_passages": passages,
        "event_evidence": {
            "evidence_id": event_window["evidence_id"], "match_id": event_window["match_id"],
            "trigger_event_id": event_window["trigger_event_id"],
            "trigger_event_type": event_window["trigger_event_type"],
            "trigger_timestamp": event_window["trigger_timestamp"],
            "source_file": event_window["source_file"], "window_rule": event_window["window_rule"],
            "events": event_window["events"],
        },
        "provenance": provenance,
        "limitations": [
            "Passages are copied verbatim from page-cited UEFA chunks; no language model generated or checked a paraphrase.",
            "StatsBomb event records do not establish off-ball runs, team shape, or unseen video context.",
            "This artifact does not claim human-judged factuality or coach review.",
        ],
    }

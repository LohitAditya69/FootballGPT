"""Tests for Lap 6A question-only similar match situation retrieval and parser."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.config import settings
from backend.api.service import TacticalService
from backend.retrieval.historical_retriever import (
    load_historical_index,
    parse_question_to_event_query,
    retrieve_historical,
)


@pytest.fixture(scope="session")
def service() -> TacticalService:
    svc = TacticalService(settings)
    svc.initialize()
    return svc


@pytest.fixture
def client(service: TacticalService) -> TestClient:
    app = create_app(service.cfg, service=service)
    return TestClient(app)


def test_parser_detects_interception_turnovers() -> None:
    q = "How should a team respond after winning the ball in midfield?"
    features, reason = parse_question_to_event_query(q)
    assert features is not None
    assert features["event_type"] == "Interception"
    # A region word is not a precise StatsBomb coordinate; keep it unknown.
    assert features["location"] is None
    assert reason is None


def test_parser_detects_counterattacks_and_defensive_third() -> None:
    q = "What options exist on a counterattack after recovering the ball deep in our own half?"
    features, reason = parse_question_to_event_query(q)
    assert features is not None
    assert features["event_type"] == "Interception"
    assert features["play_pattern"] == "From Counter"
    # Team-relative phrasing does not establish a field direction or point.
    assert features["location"] is None


def test_parser_rejects_unrepresentable_off_ball_concepts() -> None:
    q = "How can full-backs help a team create space when opponents press them tightly in build-up?"
    features, reason = parse_question_to_event_query(q)
    assert features is None
    assert reason is not None
    assert "off-ball movement" in reason.lower() or "not recorded" in reason.lower()


def test_parser_rejects_unrepresentable_defensive_block() -> None:
    q = "How should a team organize its defensive block against wide crosses?"
    features, reason = parse_question_to_event_query(q)
    assert features is None
    assert reason is not None
    assert "team shape" in reason.lower() or "structural" in reason.lower() or "not recorded" in reason.lower()


def test_question_only_retrieval_success(client: TestClient) -> None:
    """Requirement 1 & 4: Question-only request retrieves relevant train situations."""
    payload = {
        "question": "How should a team respond after winning the ball in midfield?",
        "context": None,
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "answered"
    # Exact event_evidence MUST remain null (Requirement 5)
    assert data["event_evidence"] is None

    # historical_examples must be populated with similar train records
    examples = data["historical_examples"]
    assert len(examples) > 0
    assert len(examples) <= 3

    for ex in examples:
        assert ex["source_split"] == "train"
        assert "similar recorded situation" in ex["label"]
        assert ex["historical_score"] >= 0.40
        assert "event_type" in ex["similarity_breakdown"]
        assert ex["event_type"] == "Interception"

    # Provenance must link examples with historical_similarity relation (Requirement 9)
    prov = data["provenance"]
    assert prov is not None
    h_nodes = [n for n in prov["nodes"] if n["node_type"] == "historical_situation"]
    assert len(h_nodes) == len(examples)
    h_edges = [e for e in prov["edges"] if e["relation"] == "historical_similarity"]
    assert len(h_edges) == len(examples)

    # Truthful limitation must be recorded
    assert any("Historical examples are similar recorded event situations" in lim for lim in data["limitations"])


def test_unrepresentable_tactical_query_returns_no_examples(client: TestClient) -> None:
    """Requirement 7: Do not infer unrecorded concepts from on-ball metadata."""
    payload = {
        "question": "How can full-backs help a team create space when opponents press them tightly in build-up?",
        "context": None,
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "answered"
    assert data["event_evidence"] is None
    # No misleading or fabricated event examples
    assert data["historical_examples"] == []
    # Explanatory limitation present
    assert any("off-ball movement" in lim.lower() or "not recorded" in lim.lower() for lim in data["limitations"])


def test_channel_separation_in_question_only_answer(client: TestClient) -> None:
    """Requirement 6: Historical examples illustrate patterns, not coaching guidance."""
    payload = {
        "question": "How should a team respond after winning the ball in midfield?",
        "context": None,
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    answer = data["answer"]
    # All citations in answer must be UEFA technical reports, NOT match IDs
    assert not any(f"match {ex['match_id']}" in answer for ex in data["historical_examples"])
    assert "uefa-" in answer


def test_exact_context_same_match_exclusion_preserved(client: TestClient) -> None:
    """Requirement 8: Same-match exclusion remains strictly enforced for exact-context queries."""
    query_match = "69289"
    payload = {
        "question": "What options exist after an interception?",
        "context": {
            "match_id": query_match,
            "trigger_event_id": "a8741e2f-3aff-4a73-aacb-1ae683e6a2a1",
        },
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["event_evidence"] is not None
    assert str(data["event_evidence"]["match_id"]) == query_match

    # Ensure query_match is NEVER leaked into historical_examples
    assert len(data["historical_examples"]) > 0
    for ex in data["historical_examples"]:
        assert str(ex["match_id"]) != query_match

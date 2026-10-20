from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from backend.api.answer_composer import count_sentences, validate_grounded_answer
from backend.api.app import create_app
from backend.api.config import settings
from backend.api.schemas import TacticalPassage
from backend.api.service import TacticalService


@pytest.fixture(scope="session")
def service() -> TacticalService:
    svc = TacticalService(settings)
    svc.initialize()
    return svc


@pytest.fixture(scope="session")
def client(service: TacticalService) -> TestClient:
    app = create_app(settings, service=service)
    return TestClient(app)


def test_api_retrieval_matches_checked_in_ranking_config(service: TacticalService) -> None:
    ranking = service.ranking_config
    expected_total = ranking["weights"]["alpha"] + ranking["weights"]["beta"]
    assert service.tactical_weights == {
        "V": ranking["weights"]["alpha"] / expected_total,
        "G": ranking["weights"]["beta"] / expected_total,
    }
    assert service.bm25_index["k1"] == ranking["bm25"]["k1"]
    assert service.bm25_index["b"] == ranking["bm25"]["b"]


def test_health_endpoints(client: TestClient) -> None:
    for path in ("/health", "/api/v1/health"):
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert data == {"status": "ok", "version": "1.0.0"}


def test_validation_missing_question(client: TestClient) -> None:
    res = client.post("/api/v1/ask", json={})
    assert res.status_code == 400
    data = res.json()
    assert data["schema_version"] == "footballgpt-error-v1"
    assert data["error"]["code"] == "invalid_request"
    assert "Question must contain 1–2000 characters" in data["error"]["message"]
    assert "request_id" in data
    assert "Traceback" not in res.text


def test_validation_whitespace_question(client: TestClient) -> None:
    res = client.post("/api/v1/ask", json={"question": "   \n\t  "})
    assert res.status_code == 400
    data = res.json()
    assert data["schema_version"] == "footballgpt-error-v1"
    assert data["error"]["code"] == "invalid_request"
    assert "Question must contain 1–2000 characters" in data["error"]["message"]


def test_validation_question_too_long(client: TestClient) -> None:
    res = client.post("/api/v1/ask", json={"question": "A" * 2001})
    assert res.status_code == 400
    data = res.json()
    assert data["schema_version"] == "footballgpt-error-v1"
    assert data["error"]["code"] == "invalid_request"
    assert "Question must contain 1–2000 characters" in data["error"]["message"]


def test_validation_disallowed_extra_field(client: TestClient) -> None:
    res = client.post("/api/v1/ask", json={"question": "Valid tactical query?", "extra_field": "forbidden"})
    assert res.status_code == 400
    data = res.json()
    assert data["schema_version"] == "footballgpt-error-v1"
    assert data["error"]["code"] == "invalid_request"


def test_validation_malformed_json(client: TestClient) -> None:
    res = client.post(
        "/api/v1/ask",
        content="not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 400
    data = res.json()
    assert data["schema_version"] == "footballgpt-error-v1"
    assert data["error"]["code"] == "invalid_request"


def test_supported_question_response_contract(client: TestClient, service: TacticalService) -> None:
    payload = {
        "question": "How should a team respond after winning the ball?",
        "context": None,
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Exact contract keys
    assert data["schema_version"] == "footballgpt-response-v1"
    assert "request_id" in data
    assert data["status"] == "answered"
    assert data["support_status"] == "conditional"
    assert data["answer_mode"] == "extractive_evidence_brief"
    assert isinstance(data["answer"], str) and len(data["answer"]) > 0
    assert "Retrieved source passages are shown verbatim below" not in data["answer"]
    assert 2 <= count_sentences(data["answer"]) <= 5
    is_valid, msg = validate_grounded_answer(
        data["answer"],
        [TacticalPassage(**p) for p in data["tactical_passages"]],
    )
    assert is_valid, msg

    assert isinstance(data["tactical_passages"], list)
    assert len(data["tactical_passages"]) > 0

    # Validate against fixed chunk index
    for passage in data["tactical_passages"]:
        assert "evidence_id" in passage
        assert "source_id" in passage
        assert "source_title" in passage
        assert "page" in passage
        assert "citation" in passage
        assert "excerpt" in passage
        assert "score" in passage
        assert isinstance(passage["score"], float)

        # Check against service.fixed_chunks
        eid = passage["evidence_id"]
        assert eid in service.fixed_chunks
        fixed = service.fixed_chunks[eid]
        assert passage["source_id"] == fixed["source_id"]
        assert int(passage["page"]) == int(fixed["page"])
        assert passage["citation"] == fixed["citation"]

    # No event context provided -> event_evidence is null, historical_examples empty
    assert data["event_evidence"] is None
    assert data["historical_examples"] == []

    # Provenance
    assert data["provenance"]["schema_version"] == "rgg-provenance-v1"
    assert len(data["provenance"]["nodes"]) >= 1
    assert any(n["node_type"] == "question" for n in data["provenance"]["nodes"])

    # Limitations
    assert isinstance(data["limitations"], list)
    assert any("Passages are copied verbatim" in l for l in data["limitations"])


def test_event_specific_question_abstains_without_supported_passage(client: TestClient) -> None:
    # Retrieval abstention does not depend on benchmark labels.
    payload = {
        "question": "Arsenal’s pass from Eduardo toward Fredrik Ljungberg is recorded after a blocked shot and goalkeeper action, and the pass outcome is marked incomplete. What should a coach verify about the possession/restart before judging the pass choice? Given the actual setup, what safer or more progressive option was available?",
        "context": {
            "match_id": "3749448",
            "trigger_event_id": "6cfd4b03-ddc9-4e64-8af3-d743540aea3f",
        },
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["schema_version"] == "footballgpt-response-v1"
    assert data["status"] == "abstained"
    assert data["support_status"] == "unknown"
    assert data["answer_mode"] == "abstain"
    assert data["tactical_passages"] == []
    assert "no adequately supported" in data["answer"].lower()


def test_weak_evidence_abstention(client: TestClient) -> None:
    # Off-topic / arbitrary nonsense query that should not return arbitrary tactical support
    payload = {
        "question": "quantum electrodynamics perturbation theory and string landscape in astrophysics",
        "context": None,
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "abstained"
    assert data["answer_mode"] == "abstain"
    assert data["tactical_passages"] == []
    assert data["support_status"] == "unknown"


def test_event_evidence_and_same_match_exclusion(client: TestClient) -> None:
    # Seed 69289:case:214
    query_match = "69289"
    trigger_uuid = "a8741e2f-3aff-4a73-aacb-1ae683e6a2a1"

    payload = {
        "question": "Sevilla intercepted Barcelona’s incomplete pass and then played to Diego Perotti. Should the first action prioritize securing possession or countering forward? What teammate, opponent, and space cues would you need to choose?",
        "context": {
            "match_id": query_match,
            "trigger_event_id": trigger_uuid,
        },
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Event evidence should be resolved
    assert data["event_evidence"] is not None
    assert data["event_evidence"]["match_id"] == query_match
    assert data["event_evidence"]["trigger_event_id"] == trigger_uuid
    assert data["event_evidence"]["trigger_event_type"] == "Interception"
    assert len(data["event_evidence"]["events"]) > 0

    # Historical examples must be populated and must strictly exclude query_match!
    assert len(data["historical_examples"]) > 0
    for h in data["historical_examples"]:
        assert str(h["match_id"]) != query_match, f"Found leaked match_id {h['match_id']}"
        assert "label" in h
        assert "train split" in h["label"]

    # Provenance trace should have question, tactical passages, event window, and historical nodes
    prov = data["provenance"]
    assert prov is not None
    node_types = {n["node_type"] for n in prov["nodes"]}
    assert "question" in node_types
    assert "statsbomb_event_window" in node_types
    assert "historical_situation" in node_types


def test_unresolved_event_context(client: TestClient) -> None:
    payload = {
        "question": "How should a team organize its defensive block against wide crosses?",
        "context": {
            "match_id": "nonexistent_match_99999",
            "trigger_event_id": "nonexistent_trigger_uuid_00000",
        },
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["event_evidence"] is None
    assert data["historical_examples"] == []
    assert any("could not be resolved" in lim for lim in data["limitations"])


def test_internal_service_error_handling(service: TacticalService) -> None:
    # Simulate an unexpected internal failure in the service
    app = create_app(settings, service=service)
    err_client = TestClient(app, raise_server_exceptions=False)
    with patch("backend.api.service.TacticalService.ask", side_effect=RuntimeError("Secret database disk failed")):
        res = err_client.post("/api/v1/ask", json={"question": "Any question?"})
        assert res.status_code == 500
        data = res.json()
        assert data["schema_version"] == "footballgpt-error-v1"
        assert data["error"]["code"] == "service_error"
        assert data["error"]["message"] == "An internal service error occurred."
        assert "Secret" not in res.text
        assert "Traceback" not in res.text
        assert "disk failed" not in res.text


def test_lap4_answer_grounded_sentence_count_and_citations(client: TestClient) -> None:
    payload = {
        "question": "How can full-backs help a team create space when opponents press them tightly in build-up?",
        "context": None,
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "answered"
    answer = data["answer"]
    assert 2 <= count_sentences(answer) <= 5

    # Check grounding against returned passages
    passages = [TacticalPassage(**p) for p in data["tactical_passages"]]
    is_valid, msg = validate_grounded_answer(answer, passages)
    assert is_valid, msg


def test_lap4_unresolved_event_context_contains_no_invented_facts(client: TestClient) -> None:
    payload = {
        "question": "How should a team organize its defensive block against wide crosses?",
        "context": {
            "match_id": "nonexistent_match_88888",
            "trigger_event_id": "nonexistent_uuid_77777",
        },
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Must state limitation and not invent match facts
    assert data["event_evidence"] is None
    assert "specific match context could not be resolved" in data["answer"].lower()
    assert 2 <= count_sentences(data["answer"]) <= 5


def test_lap4_distinct_evidence_channels_in_answered_query(client: TestClient) -> None:
    # Query with valid event context
    payload = {
        "question": "Should a team counterattack immediately after winning the ball?",
        "context": {
            "match_id": "69289",
            "trigger_event_id": "a8741e2f-3aff-4a73-aacb-1ae683e6a2a1",
        },
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "answered"
    answer = data["answer"]
    # Check that event evidence is mentioned distinctly as recorded data
    assert "Recorded match event evidence" in answer
    # Check that UEFA guidance is also present and cited
    assert not answer.lower().startswith("according to uefa technical analysis")
    assert re.search(r"\(uefa-[a-z0-9\-]+\s+p\.\d+\)", answer)
    assert 2 <= count_sentences(answer) <= 5


def test_api_llm_mock_generation_path(service: TacticalService) -> None:
    # Test end-to-end API response when LLM provider is active
    app = create_app(service.cfg, service=service)
    client = TestClient(app)

    with patch.object(service.llm_client, "is_configured", return_value=True), patch.object(
        service.llm_client, "provider", "mock"
    ):
        res = client.post(
            "/api/v1/ask",
            json={"question": "How should a team respond after winning the ball?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "answered"
        assert 2 <= count_sentences(data["answer"]) <= 5
        assert any("Answer generated by server-side LLM" in lim for lim in data["limitations"])


def test_api_llm_failure_falls_back_safely(service: TacticalService) -> None:
    # Test that LLM provider failure triggers safe deterministic fallback without failing request
    app = create_app(service.cfg, service=service)
    client = TestClient(app)

    with patch.object(service.llm_client, "is_configured", return_value=True), patch.object(
        service.llm_client, "generate_answer", side_effect=RuntimeError("Provider timed out")
    ):
        res = client.post(
            "/api/v1/ask",
            json={"question": "How should a team respond after winning the ball?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "answered"
        assert len(data["answer"]) > 0
        assert 2 <= count_sentences(data["answer"]) <= 5
        # Citations are still present from fallback
        assert any("uefa-" in data["answer"] for _ in [1])


def test_screenshot_regression_winning_ball_in_midfield(service: TacticalService) -> None:
    """Regression test for user screenshot query:
    'How should a team respond after winning the ball in midfield?'
    Verifies:
    1. Returns status 'answered' with valid grounded answer (2-5 sentences).
    2. Excludes Tottenham goal recaps (Spurs, Johnson, etc.) and training drill fragments (20 players, oranges, etc.).
    3. Starts directly with a tactical coaching principle without boilerplate prefixes.
    4. Cites substantive transition passages (e.g. uefa-weuro-2025 p.68 or uefa-uwcl-2024-25 p.69).
    """
    app = create_app(service.cfg, service=service)
    client = TestClient(app)

    payload = {
        "question": "How should a team respond after winning the ball in midfield?"
    }
    res = client.post("/api/v1/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "answered"
    assert data["answer_mode"] == "extractive_evidence_brief"
    answer = data["answer"]

    # Verify no Spurs / Johnson goal recap fragment
    assert "Spurs" not in answer
    assert "Johnson" not in answer
    for p in data["tactical_passages"]:
        assert "Spurs" not in p["excerpt"]
        assert "Johnson" not in p["excerpt"]

    # Verify no training drill fragment
    assert "20 players" not in answer
    assert "drill" not in answer.lower()
    for p in data["tactical_passages"]:
        assert "20 players" not in p["excerpt"]
        assert "goalkeepers" not in p["excerpt"]

    # Verify direct answering without boilerplate prefixes
    assert not answer.lower().startswith("according to uefa technical analysis")
    assert not answer.lower().startswith("evidence review")
    assert not answer.lower().startswith("evidence brief")

    # Verify citations resolve to valid UEFA passages
    citations = re.findall(r"\((uefa-[a-z0-9\-]+\s+p\.\d+)\)", answer)
    assert len(citations) >= 1
    returned_cits = {p["citation"] for p in data["tactical_passages"]}
    for c in citations:
        assert c in returned_cits

    assert 2 <= count_sentences(answer) <= 5

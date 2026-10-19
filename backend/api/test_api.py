from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.config import settings
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


def test_not_covered_question_abstention(client: TestClient) -> None:
    # Known not-covered seed question
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
    assert data["support_status"] == "not_covered"
    assert data["answer_mode"] == "abstain"
    assert data["tactical_passages"] == []
    assert "not covered" in data["answer"].lower()


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
    assert data["support_status"] in ("not_covered", "unknown")


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


def test_all_frozen_seed_questions(service: TacticalService, client: TestClient) -> None:
    import csv
    if not settings.evaluation_seeds_path.exists():
        pytest.skip("evaluation_seed_questions.csv not available")

    with open(settings.evaluation_seeds_path, encoding="utf-8-sig") as f:
        seeds = [r for r in csv.DictReader(f) if r.get("split") == "test"]

    assert len(seeds) == 12
    for seed in seeds:
        case_id = seed["case_id"]
        gold_status = seed["gold_support_status"]
        q = seed.get("revised_question_seed") or seed["question_seed"]
        payload = {
            "question": q,
            "context": {
                "match_id": seed["match_id"],
                "trigger_event_id": seed["trigger_event_id"],
            },
        }
        res = client.post("/api/v1/ask", json=payload)
        assert res.status_code == 200, f"Failed for {case_id}: {res.text}"
        data = res.json()
        expected_status = "abstained" if gold_status == "not_covered" else "answered"
        assert data["status"] == expected_status, f"{case_id}: expected {expected_status}, got {data['status']}"
        assert data["support_status"] == gold_status, f"{case_id}: expected {gold_status}, got {data['support_status']}"
        if expected_status == "abstained":
            assert data["tactical_passages"] == []
        else:
            assert len(data["tactical_passages"]) > 0
            for p in data["tactical_passages"]:
                assert p["evidence_id"] in service.fixed_chunks


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

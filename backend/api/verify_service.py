import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.config import settings
from backend.api.service import TacticalService


def run_verification() -> bool:
    print("=" * 60)
    print("FootballGPT Backend Service — Local Verification")
    print("=" * 60)

    service = TacticalService(settings)
    service.initialize()
    app = create_app(settings, service=service)
    client = TestClient(app)

    # 1. Health check
    print("\n[1] Checking Health Endpoint (/health)...")
    res = client.get("/health")
    print(f"Status: {res.status_code}")
    print(f"Response: {res.json()}")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # 2. Supported tactical question
    print("\n[2] Checking Supported Question (/api/v1/ask)...")
    payload_supported = {
        "question": "How should a team respond after winning the ball?",
        "context": None,
    }
    res = client.post("/api/v1/ask", json=payload_supported)
    print(f"Status: {res.status_code}")
    data = res.json()
    print(f"Status field: {data.get('status')}")
    print(f"Support status: {data.get('support_status')}")
    print(f"Answer mode: {data.get('answer_mode')}")
    print(f"Tactical passages: {len(data.get('tactical_passages', []))} returned")
    for i, p in enumerate(data.get("tactical_passages", [])):
        print(f"  Passage {i+1}: {p['citation']} ({p['evidence_id']}) score={p['score']}")
        print(f"    Excerpt: {p['excerpt']}")
    assert res.status_code == 200
    assert data["status"] == "answered"
    assert data["support_status"] == "conditional"
    assert len(data["tactical_passages"]) > 0

    # 3. Grounded match context and historical same-match exclusion
    print("\n[3] Checking Match Grounding & Same-Match Exclusion (/api/v1/ask)...")
    payload_grounded = {
        "question": "Sevilla intercepted Barcelona’s incomplete pass and then played to Diego Perotti. Should the first action prioritize securing possession or countering forward?",
        "context": {
            "match_id": "69289",
            "trigger_event_id": "a8741e2f-3aff-4a73-aacb-1ae683e6a2a1",
        },
    }
    res = client.post("/api/v1/ask", json=payload_grounded)
    print(f"Status: {res.status_code}")
    data = res.json()
    assert res.status_code == 200
    assert data["event_evidence"] is not None
    print(f"Event evidence: match_id={data['event_evidence']['match_id']}, trigger={data['event_evidence']['trigger_event_type']}")
    print(f"Historical examples: {len(data['historical_examples'])} situations returned")
    for h in data["historical_examples"]:
        assert str(h["match_id"]) != "69289", "LEAK DETECTED"
        print(f"  Situation {h['evidence_id']}: match={h['match_id']}, score={h['historical_score']}")
    print("Match 69289 strictly excluded from all historical results.")

    # 4. Not-covered question (explicit abstention)
    print("\n[4] Checking Not-Covered Abstention (/api/v1/ask)...")
    payload_not_covered = {
        "question": "Arsenal’s pass from Eduardo toward Fredrik Ljungberg is recorded after a blocked shot and goalkeeper action, and the pass outcome is marked incomplete. What should a coach verify about the possession/restart before judging the pass choice? Given the actual setup, what safer or more progressive option was available?",
        "context": {
            "match_id": "3749448",
            "trigger_event_id": "6cfd4b03-ddc9-4e64-8af3-d743540aea3f",
        },
    }
    res = client.post("/api/v1/ask", json=payload_not_covered)
    print(f"Status: {res.status_code}")
    data = res.json()
    print(f"Status field: {data.get('status')}")
    print(f"Support status: {data.get('support_status')}")
    print(f"Answer mode: {data.get('answer_mode')}")
    print(f"Tactical passages: {data.get('tactical_passages')}")
    assert res.status_code == 200
    assert data["status"] == "abstained"
    assert data["support_status"] == "not_covered"
    assert data["answer_mode"] == "abstain"
    assert data["tactical_passages"] == []

    # 5. Invalid input (HTTP 400 with footballgpt-error-v1)
    print("\n[5] Checking Invalid Request Handling (HTTP 400)...")
    res = client.post("/api/v1/ask", json={"question": "   "})
    print(f"Status: {res.status_code}")
    err_data = res.json()
    print(f"Error response: {err_data}")
    assert res.status_code == 400
    assert err_data["schema_version"] == "footballgpt-error-v1"
    assert err_data["error"]["code"] == "invalid_request"
    assert "request_id" in err_data

    # 6. Service failure (HTTP 500 with footballgpt-error-v1, no stack trace)
    print("\n[6] Checking Unexpected Service Failure Handling (HTTP 500)...")
    err_client = TestClient(app, raise_server_exceptions=False)
    with patch("backend.api.service.TacticalService.ask", side_effect=RuntimeError("Internal test explosion")):
        res = err_client.post("/api/v1/ask", json={"question": "Trigger failure?"})
        print(f"Status: {res.status_code}")
        err_data = res.json()
        print(f"Error response: {err_data}")
        assert res.status_code == 500
        assert err_data["schema_version"] == "footballgpt-error-v1"
        assert err_data["error"]["code"] == "service_error"
        assert "Internal test explosion" not in res.text
        assert "Traceback" not in res.text

    print("\n" + "=" * 60)
    print("ALL LOCAL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    run_verification()

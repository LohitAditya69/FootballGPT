from __future__ import annotations

from unittest.mock import patch

from backend.api.answer_composer import GENERIC_ABSTENTION_NOTICE
from backend.api.config import settings
from backend.api.schemas import AskRequest, AskResponse
from backend.api.service import TacticalService


def _service() -> TacticalService:
    service = TacticalService(settings)
    service.initialize()
    return service


def test_service_returns_natural_paraphrase_with_existing_response_contract() -> None:
    service = _service()
    request = AskRequest(question="How should a team respond after winning the ball in midfield?")
    with patch.object(service.llm_client, "is_configured", return_value=True), patch.object(
        service.llm_client, "provider", "mock"
    ):
        response = service.ask(request)

    payload = response.model_dump()
    assert set(payload) == set(AskResponse.model_fields)
    assert response.status == "answered"
    assert "When you regain the ball" in response.answer
    assert "If you recover possession" in response.answer
    assert response.answer.count("(uefa-uwcl-2024-25 p.69)") == 2
    assert response.tactical_passages
    assert "mid-block" in response.tactical_passages[0].excerpt
    assert "StatsBomb" not in response.answer


def test_invalid_provider_output_returns_same_deterministic_answer() -> None:
    service = _service()
    request = AskRequest(question="How should a team respond after winning the ball?")
    with patch.object(service.llm_client, "is_configured", return_value=False):
        expected = service.ask(request)

    with patch.object(service.llm_client, "is_configured", return_value=True), patch.object(
        service.llm_client, "provider", "openai"
    ), patch.object(
        service.llm_client, "_generate_http_completion", return_value="not valid JSON"
    ):
        actual = service.ask(request)

    assert actual.status == expected.status == "answered"
    assert actual.answer == expected.answer
    assert [p.citation for p in actual.tactical_passages] == [p.citation for p in expected.tactical_passages]
    assert any("deterministic Lap 11 answer was used" in item for item in actual.limitations)


def test_no_approved_evidence_abstains_without_calling_provider() -> None:
    service = _service()
    request = AskRequest(question="What is the history of the moon?")
    with patch.object(service.llm_client, "is_configured", return_value=True), patch.object(
        service.llm_client, "generate_answer", side_effect=AssertionError("provider must not receive unsupported query")
    ):
        response = service.ask(request)

    assert response.status == "abstained"
    assert response.tactical_passages == []
    assert response.answer == GENERIC_ABSTENTION_NOTICE

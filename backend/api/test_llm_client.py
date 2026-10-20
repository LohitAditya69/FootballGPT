from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx
import pytest

from backend.api.config import Settings
from backend.api.llm_client import (
    LLMClient,
    build_evidence_prompt,
    count_sentences,
    validate_llm_output,
)
from backend.api.schemas import EventEvidence, HistoricalExample, TacticalPassage


@pytest.fixture
def sample_passages() -> list[TacticalPassage]:
    return [
        TacticalPassage(
            evidence_id="uefa-ucl-2024-25:p23:c1",
            source_id="uefa-ucl-2024-25",
            source_title="UEFA Champions League 2024/25 Technical Report",
            page=23,
            citation="uefa-ucl-2024-25 p.23",
            excerpt="A full-back should not overlook the importance of space in build-up.",
            score=0.85,
        ),
        TacticalPassage(
            evidence_id="uefa-uwcl-2024-25:p63:c1",
            source_id="uefa-uwcl-2024-25",
            source_title="UEFA Women's Champions League 2024/25 Technical Report",
            page=63,
            citation="uefa-uwcl-2024-25 p.63",
            excerpt="Arsenal forced opponents wide to recover the ball in the middle third.",
            score=0.72,
        ),
    ]


def test_llm_client_unconfigured_signals_fallback(sample_passages: list[TacticalPassage]) -> None:
    cfg = Settings(llm_provider="none")
    client = LLMClient(cfg)
    assert not client.is_configured()

    res = client.generate_answer("How to press wide?", sample_passages)
    assert not res.success
    assert res.fallback_used
    assert "not configured" in (res.error or "").lower()


def test_llm_client_mock_provider_success(sample_passages: list[TacticalPassage]) -> None:
    cfg = Settings(llm_provider="mock", llm_model="mock-gpt")
    client = LLMClient(cfg)
    assert client.is_configured()

    res = client.generate_answer(
        question="How should a team structure build-up?",
        passages=sample_passages,
    )
    assert res.success
    assert res.text is not None
    assert 2 <= count_sentences(res.text) <= 5
    assert "uefa-ucl-2024-25 p.23" in res.text


def test_llm_client_validates_exact_citations(sample_passages: list[TacticalPassage]) -> None:
    valid_text = (
        "Positional spacing creates options for advancing teammates "
        "(uefa-ucl-2024-25 p.23). In wide areas, defensive pressure can force opponents into congested channels "
        "(uefa-uwcl-2024-25 p.63)."
    )
    is_valid, msg = validate_llm_output(valid_text, sample_passages)
    assert is_valid, msg


def test_llm_client_rejects_boilerplate_prefixes(sample_passages: list[TacticalPassage]) -> None:
    bad_prefix_text = (
        "According to UEFA technical analysis, positional spacing creates options for advancing teammates "
        "(uefa-ucl-2024-25 p.23). In wide areas, defensive pressure can force opponents into congested channels "
        "(uefa-uwcl-2024-25 p.63)."
    )
    is_valid, msg = validate_llm_output(bad_prefix_text, sample_passages)
    assert not is_valid
    assert "starts with forbidden boilerplate prefix" in msg


def test_llm_client_rejects_hallucinated_citations(sample_passages: list[TacticalPassage]) -> None:
    hallucinated_text = (
        "Wide space must be exploited to break deep lines (uefa-fake-source p.99). "
        "Teams must maintain aggressive pressure in transition (uefa-ucl-2024-25 p.23)."
    )
    is_valid, msg = validate_llm_output(hallucinated_text, sample_passages)
    assert not is_valid
    assert "Invalid or fabricated citation" in msg


def test_llm_client_rejects_out_of_bound_sentence_counts(sample_passages: list[TacticalPassage]) -> None:
    single_sentence = "Teams must open wide corridors to create space (uefa-ucl-2024-25 p.23)."
    is_valid, msg = validate_llm_output(single_sentence, sample_passages)
    assert not is_valid
    assert "Sentence count out of bounds" in msg

    six_sentences = (
        "First tactical sentence (uefa-ucl-2024-25 p.23). Second tactical sentence. "
        "Third tactical sentence. Fourth tactical sentence. "
        "Fifth tactical sentence. Sixth sentence."
    )
    is_valid_6, msg_6 = validate_llm_output(six_sentences, sample_passages)
    assert not is_valid_6
    assert "Sentence count out of bounds" in msg_6


def test_llm_client_handles_timeout_safely(sample_passages: list[TacticalPassage]) -> None:
    cfg = Settings(llm_provider="openai", llm_api_key="sk-test", llm_base_url="https://api.test.com/v1")
    client = LLMClient(cfg)

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Network timed out")):
        res = client.generate_answer("How to counter?", sample_passages)
        assert not res.success
        assert res.fallback_used
        assert "timed out" in (res.error or "").lower()


def test_llm_client_handles_connection_error_safely(sample_passages: list[TacticalPassage]) -> None:
    cfg = Settings(llm_provider="openai", llm_api_key="sk-test", llm_base_url="https://api.test.com/v1")
    client = LLMClient(cfg)

    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        res = client.generate_answer("How to counter?", sample_passages)
        assert not res.success
        assert res.fallback_used
        assert "failed" in (res.error or "").lower()


def test_build_evidence_prompt_formatting(sample_passages: list[TacticalPassage]) -> None:
    event_model = EventEvidence(
        evidence_id="statsbomb:match1:event1",
        match_id="69289",
        trigger_event_id="uuid-1234",
        trigger_event_type="Interception",
        trigger_timestamp="00:03:16.834",
        window_rule="Adjacent recorded events window",
        events=[],
    )

    prompt = build_evidence_prompt(
        question="How to react after an interception?",
        passages=sample_passages,
        event_evidence=event_model,
    )

    assert "USER QUESTION: How to react after an interception?" in prompt
    assert "uefa-ucl-2024-25 p.23" in prompt
    assert "Interception at 00:03:16.834" in prompt
    assert "RECORDED ON-BALL EVENT CONTEXT" in prompt


def test_channel_separation_in_mock_generation(sample_passages: list[TacticalPassage]) -> None:
    cfg = Settings(llm_provider="mock")
    client = LLMClient(cfg)

    event_model = EventEvidence(
        evidence_id="statsbomb:match1:event1",
        match_id="69289",
        trigger_event_id="uuid-1234",
        trigger_event_type="Interception",
        trigger_timestamp="00:03:16.834",
        window_rule="Adjacent recorded events window",
        events=[],
    )

    res = client.generate_answer(
        question="How to react after an interception?",
        passages=sample_passages,
        event_evidence=event_model,
    )
    assert res.success
    assert res.text is not None
    assert not res.text.lower().startswith("according to uefa technical analysis")
    assert "Players must maintain disciplined positional awareness" in res.text
    assert "Recorded match event evidence registers an on-ball Interception" in res.text

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from backend.api.answer_composer import compose_grounded_answer
from backend.api.config import Settings
from backend.api.llm_client import LLMClient, build_evidence_prompt, count_sentences, validate_llm_output
from backend.api.schemas import EventEvidence, HistoricalExample, TacticalPassage


def _passage() -> TacticalPassage:
    return TacticalPassage(
        evidence_id="uefa-uwcl-2024-25:p69:c4",
        source_id="uefa-uwcl-2024-25",
        source_title="UEFA Women's Champions League 2024/25 Technical Report",
        page=69,
        citation="uefa-uwcl-2024-25 p.69",
        excerpt="After winning the ball in their own half, the first pass was usually played directly deep or diagonally.",
        score=0.8,
    )


def test_output_requires_exact_source_sentence_even_with_valid_citation() -> None:
    source = _passage()
    unsupported = "The team should counter immediately into space (uefa-uwcl-2024-25 p.69)."
    assert not validate_llm_output(unsupported, [source], "How should a team respond after winning the ball?")[0]
    exact = f"{source.excerpt} ({source.citation})"
    assert validate_llm_output(exact, [source], "How should a team respond after winning the ball?")[0]


def test_prompt_excludes_historical_and_event_channels() -> None:
    event = EventEvidence(
        evidence_id="statsbomb:1:2", match_id="1", trigger_event_id="2",
        trigger_event_type="Interception", trigger_timestamp="00:03:16.834",
        window_rule="adjacent", events=[],
    )
    historical = HistoricalExample(
        evidence_id="hist:1", match_id="3", historical_score=0.4,
        label="similar recorded situation",
    )
    prompt = build_evidence_prompt(
        "How should a team respond after winning the ball?", [_passage()], event, [historical]
    )
    assert "StatsBomb" not in prompt
    assert "historical" not in prompt.casefold()
    assert "00:03:16.834" not in prompt


def test_mock_provider_returns_exact_grounded_sentence() -> None:
    client = LLMClient(Settings(llm_provider="mock"))
    result = client.generate_answer("How should a team respond after winning the ball?", [_passage()])
    assert result.success
    assert result.text == compose_grounded_answer(
        "How should a team respond after winning the ball?", [_passage()]
    )
    assert count_sentences(result.text or "") == 1


def test_provider_failure_is_sanitized_and_fallback_is_safe() -> None:
    cfg = Settings(llm_provider="openai", llm_api_key="test", llm_base_url="https://example.invalid")
    client = LLMClient(cfg)
    with patch.object(client, "_generate_http_completion", side_effect=httpx.TimeoutException("private detail")):
        result = client.generate_answer("How should a team respond after winning the ball?", [_passage()])
    assert not result.success
    assert result.fallback_used
    assert result.error == "Provider request timed out"

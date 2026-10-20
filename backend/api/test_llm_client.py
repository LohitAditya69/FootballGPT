from __future__ import annotations

import json
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

QUESTION = "How should a team respond after winning the ball?"
OWN_FORWARD = (
    "When the ball was regained in their own half they were willing to play forward early into their "
    "highest attacking player or into the space beyond the back line."
)
OWN_DIRECT = (
    "After winning the ball in their own half, the first pass was usually played directly deep or diagonally "
    "to the outside attacking players."
)
MID_BLOCK = (
    "There was also a different approach when the ball was regained in the mid-block where they tended to "
    "play for possession and ball protection."
)
OWN_PARAPHRASE = (
    "When you win the ball in your own half, look to play forward quickly with a straight or diagonal pass "
    "toward an advanced player or into space behind the back line."
)
MID_PARAPHRASE = "If you regain possession in a mid-block, focus on keeping the ball secure and protected."


def _passage(
    citation: str = "uefa-uwcl-2024-25 p.69",
    evidence_id: str = "uefa-uwcl-2024-25:p69:c4",
    excerpt: str | None = None,
    score: float = 0.8,
) -> TacticalPassage:
    return TacticalPassage(
        evidence_id=evidence_id,
        source_id=citation.rsplit(" p.", 1)[0],
        source_title="UEFA Women's Champions League 2024/25 Technical Report",
        page=int(citation.rsplit("p.", 1)[1]),
        citation=citation,
        excerpt=excerpt if excerpt is not None else f"{OWN_FORWARD} {OWN_DIRECT} {MID_BLOCK}",
        score=score,
    )


def _structured(*rows: tuple[str, str, str]) -> str:
    return json.dumps({
        "sentences": [
            {"claim_id": claim_id, "citation": citation, "text": text}
            for claim_id, citation, text in rows
        ]
    })


def test_valid_paraphrase_is_natural_and_claim_grounded() -> None:
    passage = _passage(excerpt=f"{OWN_FORWARD} {OWN_DIRECT}")
    output = _structured(("C1", passage.citation, OWN_PARAPHRASE))
    valid, reason = validate_llm_output(output, [passage], QUESTION)
    assert valid, reason
    assert "When you win the ball" in output
    assert "After a regain in your own half" not in output


def test_winning_ball_can_express_both_claims_only_when_both_are_approved() -> None:
    passage = _passage()
    both = _structured(
        ("C1", passage.citation, OWN_PARAPHRASE),
        ("C2", passage.citation, MID_PARAPHRASE),
    )
    assert validate_llm_output(both, [passage], QUESTION)[0]

    own_only = _passage(excerpt=f"{OWN_FORWARD} {OWN_DIRECT}")
    assert not validate_llm_output(both, [own_only], QUESTION)[0]


def test_direct_only_claim_does_not_gain_an_unsupported_timing_claim() -> None:
    passage = _passage(excerpt=OWN_DIRECT)
    paraphrase = "After you win the ball in your own half, look for a direct or diagonal first pass to an advanced player."
    assert validate_llm_output(_structured(("C1", passage.citation, paraphrase)), [passage], QUESTION)[0]
    with_early_timing = "After you win the ball in your own half, quickly play a direct or diagonal first pass to an advanced player."
    assert not validate_llm_output(_structured(("C1", passage.citation, with_early_timing)), [passage], QUESTION)[0]


def test_valid_citation_does_not_authorize_unsupported_paraphrase() -> None:
    passage = _passage(excerpt=f"{OWN_FORWARD} {OWN_DIRECT}")
    unsupported = _structured((
        "C1", passage.citation,
        "Tell the fullbacks to overlap immediately and counter through the right channel.",
    ))
    assert not validate_llm_output(unsupported, [passage], QUESTION)[0]


def test_added_tactical_detail_and_changed_condition_are_rejected() -> None:
    passage = _passage(excerpt=f"{OWN_FORWARD} {OWN_DIRECT}")
    added_detail = _structured((
        "C1", passage.citation,
        "When you win the ball in your own half, play forward quickly with a diagonal pass to an advanced player and overlap down the right flank.",
    ))
    changed_condition = _structured((
        "C1", passage.citation,
        "When you win the ball in the final third, play forward quickly with a diagonal pass to an advanced player.",
    ))
    assert not validate_llm_output(added_detail, [passage], QUESTION)[0]
    assert not validate_llm_output(changed_condition, [passage], QUESTION)[0]


def test_invented_or_missing_citations_and_extra_sentences_are_rejected() -> None:
    passage = _passage(excerpt=f"{OWN_FORWARD} {OWN_DIRECT}")
    invented = _structured(("C1", "uefa-ucl-2099-00 p.999", OWN_PARAPHRASE))
    missing = json.dumps({"sentences": [{"claim_id": "C1", "text": OWN_PARAPHRASE}]})
    extra = _structured(
        ("C1", passage.citation, OWN_PARAPHRASE),
        ("C2", passage.citation, "The right winger should sprint into the channel."),
    )
    assert not validate_llm_output(invented, [passage], QUESTION)[0]
    assert not validate_llm_output(missing, [passage], QUESTION)[0]
    assert not validate_llm_output(extra, [passage], QUESTION)[0]


def test_event_or_historical_advice_is_not_approved_claim_material() -> None:
    passage = _passage(excerpt=f"{OWN_FORWARD} {OWN_DIRECT}")
    event = EventEvidence(
        evidence_id="statsbomb:1:2", match_id="1", trigger_event_id="2",
        trigger_event_type="Interception", trigger_timestamp="00:03:16.834",
        window_rule="adjacent", events=[],
    )
    historical = HistoricalExample(
        evidence_id="hist:1", match_id="3", historical_score=0.4,
        label="similar recorded situation",
    )
    prompt = build_evidence_prompt(QUESTION, [passage], event, [historical])
    parsed = json.loads(prompt)
    assert set(parsed) == {"question", "approved_claims"}
    assert "StatsBomb" not in prompt
    assert "historical" not in prompt.casefold()
    assert "00:03:16.834" not in prompt

    historical_advice = _structured((
        "C1", passage.citation,
        "In the last match, use overlapping runs after winning the ball in your own half, then play forward quickly with a diagonal pass to an advanced player.",
    ))
    assert not validate_llm_output(historical_advice, [passage], QUESTION)[0]


def test_claim_cannot_borrow_a_citation_from_another_returned_passage() -> None:
    own = _passage(excerpt=f"{OWN_FORWARD} {OWN_DIRECT}", score=1.0)
    other = _passage(
        citation="uefa-ucl-2024-25 p.70",
        evidence_id="uefa-ucl-2024-25:p70:c1",
        excerpt="Unrelated report sentence about pressing.",
        score=0.1,
    )
    borrowed = _structured(("C1", other.citation, OWN_PARAPHRASE))
    assert not validate_llm_output(borrowed, [own, other], QUESTION)[0]


def test_contradictory_source_statements_produce_no_approved_claim() -> None:
    conflicting = _passage(excerpt=(
        "After winning the ball in their own half, the first pass was usually played directly deep or diagonally. "
        "After winning the ball in their own half, the first pass was not usually played directly deep or diagonally."
    ))
    output = _structured(("C1", conflicting.citation, OWN_PARAPHRASE))
    valid, reason = validate_llm_output(output, [conflicting], QUESTION)
    assert not valid
    assert "No approved claim" in reason


def test_mock_provider_returns_checked_natural_paraphrases() -> None:
    passage = _passage()
    client = LLMClient(Settings(llm_provider="mock"))
    result = client.generate_answer(QUESTION, [passage])
    assert result.success
    assert result.text
    assert "When you regain the ball" in result.text
    assert "If you recover possession" in result.text
    assert result.text != compose_grounded_answer(QUESTION, [passage])
    assert count_sentences(result.text) == 2
    assert result.text.count(f"({passage.citation})") == 2


def test_provider_failure_and_malformed_output_are_sanitized() -> None:
    passage = _passage()
    cfg = Settings(llm_provider="openai", llm_api_key="test-secret", llm_base_url="https://example.invalid")
    client = LLMClient(cfg)
    with patch.object(client, "_generate_http_completion", side_effect=httpx.TimeoutException("private detail")):
        timed_out = client.generate_answer(QUESTION, [passage])
    assert not timed_out.success and timed_out.fallback_used
    assert timed_out.error == "Provider request timed out"
    assert "private detail" not in (timed_out.error or "")

    with patch.object(client, "_generate_http_completion", return_value="not json"):
        malformed = client.generate_answer(QUESTION, [passage])
    assert not malformed.success and malformed.fallback_used
    assert malformed.error == "Output validation failed"


def test_connection_failure_and_rate_limit_are_sanitized() -> None:
    passage = _passage()
    cfg = Settings(llm_provider="openai", llm_api_key="test-secret", llm_base_url="https://example.invalid")
    client = LLMClient(cfg)
    request = httpx.Request("POST", "https://example.invalid/chat/completions")
    with patch.object(client, "_generate_http_completion", side_effect=httpx.ConnectError("private endpoint", request=request)):
        connection = client.generate_answer(QUESTION, [passage])
    assert not connection.success and connection.fallback_used
    assert connection.error == "Provider connection failed"
    assert "private endpoint" not in (connection.error or "")

    response = httpx.Response(429, request=request)
    rate_error = httpx.HTTPStatusError("private response", request=request, response=response)
    with patch.object(client, "_generate_http_completion", side_effect=rate_error):
        limited = client.generate_answer(QUESTION, [passage])
    assert not limited.success and limited.fallback_used
    assert limited.error == "Provider rate limited"
    assert "private response" not in (limited.error or "")


def test_no_approved_evidence_fails_closed() -> None:
    passage = _passage(excerpt="A noisy fragment about training drills and sessions.")
    client = LLMClient(Settings(llm_provider="mock"))
    result = client.generate_answer(QUESTION, [passage])
    assert not result.success
    assert result.fallback_used
    assert result.text is None

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from backend.api.answer_composer import (
    GENERIC_ABSTENTION_NOTICE,
    clean_coaching_clause,
    clean_text_artifacts,
    compose_grounded_answer,
    count_sentences,
    is_clean_tactical_sentence,
    validate_grounded_answer,
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
            excerpt="Indeed, adds Van Bronckhorst, a full-back should not overlook the importance of space.",
            score=0.85,
        ),
        TacticalPassage(
            evidence_id="uefa-uwcl-2024-25:p63:c1",
            source_id="uefa-uwcl-2024-25",
            source_title="UEFA Women's Champions League 2024/25 Technical Report",
            page=63,
            citation="uefa-uwcl-2024-25 p.63",
            excerpt="Arsenal adopted a different approach when attempting to recover the ball in the middle third of the pitch.",
            score=0.72,
        ),
    ]


@pytest.fixture
def sample_chunks() -> dict[str, dict]:
    return {
        "uefa-ucl-2024-25:p23:c1": {
            "evidence_id": "uefa-ucl-2024-25:p23:c1",
            "source_id": "uefa-ucl-2024-25",
            "page": 23,
            "text": (
                "Indeed, adds Van Bronckhorst, a full-back should not overlook the importance of space. "
                "The position they have on the pitch can be important to give more space to other players. "
                "Once I told a player 'Today your role is to open up spaces for your team-mates' so that is "
                "part of the understanding players should have."
            ),
        },
        "uefa-uwcl-2024-25:p63:c1": {
            "evidence_id": "uefa-uwcl-2024-25:p63:c1",
            "source_id": "uefa-uwcl-2024-25",
            "page": 63,
            "text": (
                "Arsenal adopted a different approach when attempting to recover the ball in the middle third of the pitch. "
                "The two highest attacking players were very good in their collaboration to press and cover the space behind them."
            ),
        },
    }


def test_abstention_output() -> None:
    ans = compose_grounded_answer("Any unsupported question", [])
    assert ans == GENERIC_ABSTENTION_NOTICE
    is_valid, msg = validate_grounded_answer(ans, [], is_abstained=True)
    assert is_valid
    assert "Valid abstention" in msg


def test_grounded_answer_structure_and_sentence_count(
    sample_passages: list[TacticalPassage],
    sample_chunks: dict[str, dict],
) -> None:
    question = "How can full-backs help a team create space when opponents press them tightly in build-up?"
    ans = compose_grounded_answer(
        question=question,
        tactical_passages=sample_passages,
        fixed_chunks=sample_chunks,
    )

    # Must be 2-5 sentences
    s_count = count_sentences(ans)
    assert 2 <= s_count <= 5, f"Unexpected sentence count: {s_count}"

    # Must contain citations resolving to the provided passages
    valid, msg = validate_grounded_answer(ans, sample_passages)
    assert valid, msg

    # No generic boilerplate notice
    assert "Retrieved source passages are shown verbatim below" not in ans
    assert "According to UEFA technical analysis" in ans


def test_citation_linkage(
    sample_passages: list[TacticalPassage],
    sample_chunks: dict[str, dict],
) -> None:
    question = "How should a team organize build-up play?"
    ans = compose_grounded_answer(
        question=question,
        tactical_passages=sample_passages,
        fixed_chunks=sample_chunks,
    )

    found_citations = re.findall(r"\((uefa-[a-z0-9\-]+\s+p\.\d+)\)", ans)
    assert len(found_citations) >= 1
    valid_cits = {p.citation for p in sample_passages}
    for cit in found_citations:
        assert cit in valid_cits


def test_unresolved_event_context_notice(
    sample_passages: list[TacticalPassage],
    sample_chunks: dict[str, dict],
) -> None:
    question = "Arsenal's pass from Eduardo toward Ljungberg failed. What safer option was available?"
    ans = compose_grounded_answer(
        question=question,
        tactical_passages=sample_passages,
        fixed_chunks=sample_chunks,
        unresolved_event_context=True,
    )

    # Must explicitly state limitation rather than inventing match facts
    assert "specific match context could not be resolved" in ans.lower()
    assert 2 <= count_sentences(ans) <= 5


def test_resolved_event_evidence_channel_separation(
    sample_passages: list[TacticalPassage],
    sample_chunks: dict[str, dict],
) -> None:
    event_model = EventEvidence(
        evidence_id="statsbomb:69289:a874",
        match_id="69289",
        trigger_event_id="a8741e2f-3aff-4a73-aacb-1ae683e6a2a1",
        trigger_event_type="Interception",
        trigger_timestamp="00:03:16.834",
        window_rule="Adjacent recorded events window",
        events=[],
    )

    ans = compose_grounded_answer(
        question="Should the team counter forward after winning the ball?",
        tactical_passages=sample_passages,
        event_evidence=event_model,
        fixed_chunks=sample_chunks,
    )

    # Must describe recorded match events distinctly from UEFA principles
    assert "Recorded match event evidence registers an on-ball Interception" in ans
    assert "00:03:16.834" in ans
    assert "match 69289" in ans


def test_historical_channel_separation(
    sample_passages: list[TacticalPassage],
    sample_chunks: dict[str, dict],
) -> None:
    historical = [
        HistoricalExample(
            evidence_id="hist:case1",
            match_id="3749448",
            historical_score=0.91,
            label="historical event example (train split, not UEFA coaching principle)",
        )
    ]

    ans = compose_grounded_answer(
        question="What patterns apply to this turnover?",
        tactical_passages=sample_passages,
        historical_examples=historical,
        fixed_chunks=sample_chunks,
    )

    assert "Historical event examples illustrate similar recorded sequences" in ans
    assert "not constitute coaching recommendations" in ans


def test_clean_coaching_clause_and_filtering() -> None:
    raw_with_attribution = '"It was crucial that players immediately looked to play forward into space," Fuhrmann continued.'
    cleaned = clean_coaching_clause(raw_with_attribution)
    assert cleaned == "It was crucial that players immediately looked to play forward into space"

    raw_with_speaker_prefix = "Indeed, adds Van Bronckhorst, a full-back should not overlook the importance of space."
    cleaned_prefix = clean_coaching_clause(raw_with_speaker_prefix)
    assert cleaned_prefix == "A full-back should not overlook the importance of space"

    # Test filtering of drills and tables
    drill_line = "20 players + 2 goalkeepers • Force outside • no passes through"
    assert not is_clean_tactical_sentence(drill_line)

    valid_line = "The position they have on the pitch can be important to give more space to other players."
    assert is_clean_tactical_sentence(valid_line)


def test_validation_grounding_rejects_hallucinated_citations(
    sample_passages: list[TacticalPassage],
) -> None:
    bad_answer = (
        "According to UEFA technical analysis, space must be preserved (uefa-invented-2099 p.99). "
        "Tactical guidance stresses team shape."
    )
    valid, msg = validate_grounded_answer(bad_answer, sample_passages)
    assert not valid
    assert "does not resolve to returned tactical passages" in msg


def test_validation_grounding_rejects_generic_boilerplate(
    sample_passages: list[TacticalPassage],
) -> None:
    boilerplate_answer = (
        "Retrieved source passages are shown verbatim below. "
        "They support review of the question but do not establish missing match context or coaching ground truth. (uefa-ucl-2024-25 p.23)"
    )
    valid, msg = validate_grounded_answer(boilerplate_answer, sample_passages)
    assert not valid
    assert "forbidden generic boilerplate" in msg

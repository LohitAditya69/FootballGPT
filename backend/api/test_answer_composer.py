from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.answer_composer import (
    GENERIC_ABSTENTION_NOTICE,
    compose_grounded_answer,
    count_sentences,
    select_direct_passages,
    validate_grounded_answer,
)
from backend.api.schemas import TacticalPassage


def _passage(citation: str, excerpt: str, score: float = 0.8) -> TacticalPassage:
    source_id, page = citation.split(" p.")
    return TacticalPassage(
        evidence_id=f"{source_id}:p{page}:c1", source_id=source_id,
        source_title="UEFA Technical Report", page=int(page), citation=citation,
        excerpt=excerpt, score=score,
    )


def test_answer_synthesizes_supported_own_half_and_mid_block_claims() -> None:
    relevant = _passage(
        "uefa-uwcl-2024-25 p.69",
        "When the ball was regained in their own half they were willing to play forward early into their highest attacking player or into the space beyond the back line. "
        "After winning the ball in their own half, the first pass was usually played directly deep or diagonally to the outside attacking players. "
        "There was also a different approach when the ball was regained in the mid-block where they tended to play for possession and ball protection.",
    )
    irrelevant_top = _passage(
        "uefa-uel-2024-25 p.69",
        "The Scottish team had the highest percentage of shots attributable to defensive actions.", 1.0,
    )
    question = "How should a team respond after winning the ball?"
    selected = select_direct_passages([irrelevant_top, relevant], question)
    answer = compose_grounded_answer(question, selected)
    assert selected == [relevant]
    assert "After a regain in your own half" in answer
    assert "direct or diagonal pass" in answer
    assert "If possession is regained in a mid-block" in answer
    assert answer.count(f"({relevant.citation})") == 2
    assert count_sentences(answer) == 2
    assert validate_grounded_answer(answer, selected)[0]


def test_nonresponsive_or_noisy_evidence_abstains() -> None:
    question = "How should a team respond after winning the ball?"
    irrelevant = _passage(
        "uefa-uel-2024-25 p.69",
        "The Scottish team had the highest percentage of shots attributable to defensive actions.",
    )
    noisy = _passage(
        "uefa-ucl-2024-25 p.40",
        "After winning the ball, 41% of actions were followed by a goal.\ufffd",
    )
    assert compose_grounded_answer(question, [irrelevant, noisy]) == GENERIC_ABSTENTION_NOTICE


def test_citation_membership_does_not_allow_unsupported_claim() -> None:
    passage = _passage(
        "uefa-ucl-2024-25 p.23",
        "A full-back should not overlook the importance of space in build-up.",
    )
    answer = "Full-backs should sprint forward immediately to exploit the space (uefa-ucl-2024-25 p.23)."
    valid, reason = validate_grounded_answer(answer, [passage])
    assert not valid
    assert "not supported by a recognized" in reason


def test_every_claim_requires_an_adjacent_valid_citation() -> None:
    passage = _passage(
        "uefa-ucl-2024-25 p.23",
        "A full-back should not overlook the importance of space in build-up.",
    )
    answer = "A full-back should not overlook the importance of space in build-up."
    assert not validate_grounded_answer(answer, [passage])[0]

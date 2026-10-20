from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.answer_composer import (
    GENERIC_ABSTENTION_NOTICE,
    compose_grounded_answer,
    select_direct_passages,
    validate_grounded_answer,
)
from backend.api.config import Settings
from backend.api.llm_client import LLMClient, build_evidence_prompt, validate_llm_output
from backend.api.schemas import AskRequest, EventEvidence, HistoricalExample, TacticalPassage


def passage(evidence_id: str, citation: str, excerpt: str, score: float) -> TacticalPassage:
    source_id, page = citation.split(" p.")
    return TacticalPassage(
        evidence_id=evidence_id,
        source_id=source_id,
        source_title="UEFA Technical Report",
        page=int(page),
        citation=citation,
        excerpt=excerpt,
        score=score,
    )


class Lap10DirectAnswerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.regain = passage(
            "uefa-uwcl-2024-25:p69:c4",
            "uefa-uwcl-2024-25 p.69",
            "After winning the ball in their own half, the first pass was usually played directly deep or diagonally to the outside attacking players.",
            0.4,
        )
        self.irrelevant_top = passage(
            "uefa-uel-2024-25:p69:c1",
            "uefa-uel-2024-25 p.69",
            "The Scottish team had the highest percentage of shots attributable to defensive actions in the opposition half.",
            1.0,
        )

    def test_winning_ball_uses_one_direct_source_sentence(self) -> None:
        question = "How should a team respond after winning the ball?"
        selected = select_direct_passages([self.irrelevant_top, self.regain], question)
        self.assertEqual([p.citation for p in selected], [self.regain.citation])
        answer = compose_grounded_answer(question, selected)
        self.assertEqual(answer, f"{self.regain.excerpt} ({self.regain.citation})")
        self.assertTrue(validate_grounded_answer(answer, selected)[0])

    def test_nonresponsive_top_rank_does_not_answer(self) -> None:
        question = "How should a team respond after winning the ball?"
        self.assertEqual(select_direct_passages([self.irrelevant_top], question), [])
        self.assertEqual(compose_grounded_answer(question, [self.irrelevant_top]), GENERIC_ABSTENTION_NOTICE)

    def test_noisy_or_contradictory_sentence_is_not_rewritten_into_support(self) -> None:
        noisy = passage(
            "uefa-ucl-2024-25:p40:c2",
            "uefa-ucl-2024-25 p.40",
            "After winning the ball, 41% of actions were followed by a goal.\ufffd",
            0.9,
        )
        self.assertEqual(select_direct_passages([noisy], "How should a team respond after winning the ball?"), [])

        forward = passage(
            "uefa-ucl-2024-25:p68:c1", "uefa-ucl-2024-25 p.68",
            "After winning the ball, players should play forward quickly into space.", 0.8,
        )
        retain = passage(
            "uefa-uwcl-2024-25:p70:c1", "uefa-uwcl-2024-25 p.70",
            "After winning the ball, players should not play forward quickly into space.", 0.7,
        )
        self.assertEqual(select_direct_passages([forward, retain], "How should a team respond after winning the ball?"), [])

    def test_exact_citation_does_not_validate_unsupported_paraphrase(self) -> None:
        valid = passage(
            "uefa-ucl-2024-25:p23:c1",
            "uefa-ucl-2024-25 p.23",
            "A full-back should not overlook the importance of space in build-up.",
            0.8,
        )
        hallucination = "Full-backs should sprint forward immediately to exploit the space (uefa-ucl-2024-25 p.23)."
        self.assertFalse(validate_llm_output(hallucination, [valid], "How should full-backs use space in build-up?")[0])

    def test_historical_and_exact_event_context_are_not_answer_material(self) -> None:
        event = EventEvidence(
            evidence_id="statsbomb:1:2", match_id="1", trigger_event_id="2",
            trigger_event_type="Interception", trigger_timestamp="00:03:16.834",
            window_rule="adjacent", events=[],
        )
        history = HistoricalExample(
            evidence_id="hist:1", match_id="3", historical_score=0.4,
            label="similar recorded situation",
        )
        prompt = build_evidence_prompt("How should a team respond after winning the ball?", [self.regain], event, [history])
        self.assertNotIn("StatsBomb", prompt)
        self.assertNotIn("historical", prompt.casefold())
        answer = compose_grounded_answer(
            "How should a team respond after winning the ball?", [self.regain], event, [history]
        )
        self.assertNotIn("training split", answer)
        self.assertNotIn("Interception", answer)

    def test_provider_failure_uses_same_direct_grounded_fallback(self) -> None:
        client = LLMClient(Settings(llm_provider="openai", llm_api_key="test", llm_base_url="https://example.invalid"))
        with patch.object(client, "_generate_http_completion", side_effect=RuntimeError("provider unavailable")):
            result = client.generate_answer("How should a team respond after winning the ball?", [self.regain])
        self.assertFalse(result.success)
        fallback = compose_grounded_answer("How should a team respond after winning the ball?", [self.regain])
        self.assertTrue(validate_grounded_answer(fallback, [self.regain])[0])
        self.assertNotIn("Furthermore", fallback)

    def test_local_service_answer_and_off_topic_abstention(self) -> None:
        from backend.api.config import settings
        from backend.api.service import TacticalService

        service = TacticalService(settings)
        service.initialize()
        response = service.ask(AskRequest(question="How should a team respond after winning the ball?"))
        self.assertEqual(response.status, "answered")
        self.assertEqual(len(response.tactical_passages), 1)
        self.assertEqual(response.tactical_passages[0].citation, "uefa-uwcl-2024-25 p.69")
        self.assertTrue(validate_grounded_answer(response.answer, response.tactical_passages)[0])
        self.assertNotIn("training split", response.answer.casefold())

        off_topic = service.ask(AskRequest(question="quantum electrodynamics in astrophysics"))
        self.assertEqual(off_topic.status, "abstained")
        self.assertEqual(off_topic.tactical_passages, [])


if __name__ == "__main__":
    unittest.main()

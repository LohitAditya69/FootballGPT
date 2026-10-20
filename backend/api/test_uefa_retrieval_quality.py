"""Focused regressions for page-local UEFA chunks and passage selection."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.api.schemas import AskRequest
from backend.api.service import TacticalService, _deduplicate_ranked_passages, _extract_excerpt
from backend.retrieval.vector_retriever import build_bm25_index, retrieve_bm25, tokenize
from scripts.prepare_evidence import chunk_page_text, normalize_retrieval_text


class PageChunkingTests(unittest.TestCase):
    def test_chunks_are_bounded_page_local_sentence_groups(self) -> None:
        page = (
            "First paragraph starts here and describes the first transition. "
            "It then gives one more coaching detail.\n\n"
            "Second paragraph remains a separate source block. It has its own conclusion."
        )

        chunks = chunk_page_text(page, max_words=8)

        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(len(chunk.split()) <= 8 for chunk in chunks))
        self.assertTrue(all(chunk in page for chunk in chunks))
        self.assertFalse(any("detail.\n\nSecond" in chunk for chunk in chunks))
        self.assertEqual(chunks, chunk_page_text(page, max_words=8))

    def test_layout_columns_are_not_joined_into_hybrid_sentences(self) -> None:
        page = (
            "Barcelona regain the ball and play forward."
            + " " * 42
            + "Lyon counterattack from deep.\n"
            + "The first pass finds a forward."
            + " " * 48
            + "The wide players run beyond the defence."
        )

        chunks = chunk_page_text(page)

        self.assertEqual(len(chunks), 2)
        self.assertIn("Barcelona regain", chunks[0])
        self.assertIn("The first pass", chunks[0])
        self.assertIn("Lyon counterattack", chunks[1])
        self.assertIn("wide players", chunks[1])
        self.assertFalse(any("Barcelona" in c and "Lyon" in c for c in chunks))

    def test_retrieval_normalization_does_not_replace_source_text(self) -> None:
        source_text = "A direct pass\ninto space after recovery."
        record = {
            "evidence_id": "uefa-test:p1:c1",
            "citation": "uefa-test p.1",
            "source_id": "uefa-test",
            "page": 1,
            "text": source_text,
            "retrieval_text": normalize_retrieval_text(source_text),
        }
        with tempfile.TemporaryDirectory() as directory:
            chunk_path = Path(directory) / "chunks.jsonl"
            chunk_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            index = build_bm25_index(chunk_path)

        rows = retrieve_bm25("direct pass space recovery", index)
        self.assertEqual(rows[0]["text"], source_text)
        self.assertEqual(
            index["documents"][0]["length"],
            len(tokenize(normalize_retrieval_text(source_text))),
        )


class PassageSelectionTests(unittest.TestCase):
    def test_excerpt_is_an_unmodified_source_substring(self) -> None:
        source = "A direct pass\ninto space creates a chance. A second sentence follows."
        excerpt = _extract_excerpt(source)
        self.assertIn(excerpt, source)
        self.assertEqual(excerpt, "A direct pass\ninto space creates a chance.")

    def test_excerpt_prefers_the_query_relevant_verbatim_sentence(self) -> None:
        source = (
            "The team stayed compact. After winning the ball, the players looked forward."
        )
        excerpt = _extract_excerpt(source, "What to do after winning the ball?")

        self.assertEqual(excerpt, "After winning the ball, the players looked forward.")
        self.assertIn(excerpt, source)

    def test_ranked_candidates_keep_one_per_page_and_drop_near_duplicates(self) -> None:
        repeated = (
            "coordinated movement creates space behind the defensive line with timed forward runs "
            "while supporting midfielders preserve balance and provide clear passing options"
        )
        candidates = [
            (0.9, {"source_id": "uefa-a", "page": 68, "excerpt": repeated, "evidence_id": "a:p68:c1"}),
            (0.8, {"source_id": "uefa-a", "page": 68, "excerpt": "Different passage on the same cited page.", "evidence_id": "a:p68:c2"}),
            (0.7, {"source_id": "uefa-b", "page": 69, "excerpt": repeated + " after recovery", "evidence_id": "b:p69:c1"}),
            (0.6, {"source_id": "uefa-b", "page": 70, "excerpt": "A distinct passage about a defensive transition and controlled possession.", "evidence_id": "b:p70:c1"}),
        ]

        selected = _deduplicate_ranked_passages(candidates, 3)

        self.assertEqual([row["evidence_id"] for row in selected], ["a:p68:c1", "b:p70:c1"])

    def test_live_winning_ball_result_is_distinct_and_page_traceable(self) -> None:
        service = TacticalService()
        response = service.ask(AskRequest(question="How should a team respond after winning the ball in midfield?"))

        self.assertEqual(response.status, "answered")
        citation_pages = [(passage.source_id, passage.page) for passage in response.tactical_passages]
        self.assertEqual(len(citation_pages), len(set(citation_pages)))
        self.assertIn(("uefa-uwcl-2024-25", 69), citation_pages)
        winning_ball = next(
            passage for passage in response.tactical_passages
            if passage.source_id == "uefa-uwcl-2024-25" and passage.page == 69
        )
        self.assertEqual(winning_ball.evidence_id, "uefa-uwcl-2024-25:p69:c4")
        self.assertIn("After winning the ball in their own half", winning_ball.excerpt)
        for passage in response.tactical_passages:
            fixed = service.fixed_chunks[passage.evidence_id]
            self.assertEqual(passage.source_id, fixed["source_id"])
            self.assertEqual(passage.page, fixed["page"])
            self.assertIn(passage.excerpt, fixed["text"])

    def test_irrelevant_and_ambiguous_questions_remain_abstentions(self) -> None:
        service = TacticalService()
        for question in ("How do I bake sourdough bread?", "What should happen next?"):
            with self.subTest(question=question):
                response = service.ask(AskRequest(question=question))
                self.assertEqual(response.status, "abstained")
                self.assertEqual(response.tactical_passages, [])


if __name__ == "__main__":
    unittest.main()

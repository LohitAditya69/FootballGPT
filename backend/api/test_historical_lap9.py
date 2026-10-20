"""Focused Lap 9 tests for honest historical feature matching."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from backend.api.schemas import HistoricalExample
from backend.retrieval.historical_retriever import (
    historical_similarity,
    parse_question_to_event_query,
    retrieve_historical,
)


class HistoricalQuestionParsingTests(unittest.TestCase):
    def test_regain_query_without_location_leaves_location_unknown(self) -> None:
        features, warning = parse_question_to_event_query("How should a team respond after winning the ball?")
        self.assertIsNone(warning)
        self.assertEqual(features["event_type"], "Interception")
        self.assertEqual(features["event_type_scope"], "regain_proxy")
        self.assertIsNone(features["location"])
        self.assertIsNone(features["location_region"])

    def test_regain_query_uses_a_region_not_a_guessed_point(self) -> None:
        features, warning = parse_question_to_event_query("How should a team respond after winning the ball in midfield?")
        self.assertIsNone(warning)
        self.assertEqual(features["event_type"], "Interception")
        self.assertEqual(features["location_region"], "middle_third")
        self.assertIsNone(features["location"])

    def test_turnover_word_does_not_guess_a_pass_outcome(self) -> None:
        features, _ = parse_question_to_event_query("What should a team do after a turnover?")
        self.assertEqual(features["event_type"], "Interception")
        self.assertIsNone(features["event_outcome"])
        self.assertIsNone(features["play_pattern"])

    def test_team_relative_zone_is_unknown_without_direction(self) -> None:
        features, warning = parse_question_to_event_query("What options exist after an interception deep in our own half?")
        self.assertEqual(features["event_type"], "Interception")
        self.assertIsNone(features["location"])
        self.assertIsNone(features["location_region"])
        self.assertIn("left unknown", warning)

    def test_unsupported_off_ball_concepts_are_not_retrieved(self) -> None:
        features, warning = parse_question_to_event_query(
            "How can a full-back create space with an off-ball run after the press?"
        )
        self.assertIsNone(features)
        self.assertTrue(warning)


class HistoricalSimilarityTests(unittest.TestCase):
    def test_one_feature_match_is_not_a_perfect_score(self) -> None:
        score, breakdown = historical_similarity(
            {"event_type": "Interception"},
            {"event_type": "Interception", "play_pattern": "Regular Play", "location": [55, 40]},
        )
        self.assertEqual(score, 0.4)
        self.assertEqual(breakdown["event_type"], 1.0)
        self.assertEqual(breakdown["available_weight"], 0.4)
        self.assertEqual(breakdown["compared_feature_count"], 1.0)
        self.assertEqual(breakdown["query_feature_count"], 1.0)

    def test_missing_query_dimensions_are_not_counted_as_matches(self) -> None:
        score, breakdown = historical_similarity(
            {"event_type": "Interception"},
            {"event_type": "Interception", "play_pattern": "Regular Play", "location": [60, 40]},
        )
        self.assertEqual(score, 0.4)
        self.assertNotIn("play_pattern", breakdown)
        self.assertNotIn("location", breakdown)

    def test_middle_third_is_compared_as_region_and_location_difference_matters(self) -> None:
        query = {"event_type": "Interception", "location_region": "middle_third"}
        middle_score, middle = historical_similarity(query, {"event_type": "Interception", "location": [60, 40]})
        wide_score, wide = historical_similarity(query, {"event_type": "Interception", "location": [100, 40]})
        self.assertEqual(middle["location"], 1.0)
        self.assertEqual(middle_score, 0.65)
        self.assertEqual(wide["location"], 0.0)
        self.assertEqual(wide_score, 0.4)

    def test_lossy_false_flags_in_compact_candidates_are_unknown(self) -> None:
        score, breakdown = historical_similarity(
            {"event_type": "Interception", "under_pressure": False},
            {
                "event_type": "Interception",
                "under_pressure": False,
                "counterpress": False,
                "provenance": "StatsBomb-derived train case; phase and field-zone omitted",
            },
        )
        self.assertEqual(score, 0.4)
        self.assertNotIn("under_pressure", breakdown)
        self.assertNotIn("counterpress", breakdown)
        self.assertEqual(breakdown["compared_feature_count"], 1.0)

    def test_retrieved_records_remain_train_only_and_schema_stays_flat(self) -> None:
        rows = retrieve_historical(
            {"event_type": "Interception"},
            [{"case_id": "train-case", "match_id": "123", "event_type": "Interception"}],
            top_k=1,
            min_score_threshold=0.4,
        )
        self.assertEqual(rows[0]["source_split"], "train")
        self.assertEqual(rows[0]["historical_score"], 0.4)
        self.assertNotIn("event_sequence", rows[0])
        self.assertNotIn("events", rows[0])

    def test_contract_sequence_field_is_nullable_and_validates_order(self) -> None:
        fields = {
            "evidence_id": "historical:case-1",
            "case_id": "case-1",
            "match_id": "123",
            "historical_score": 0.4,
        }
        empty = HistoricalExample(**fields)
        self.assertIsNone(empty.recorded_event_sequence)
        self.assertIsNone(empty.model_dump(mode="json")["recorded_event_sequence"])

        ordered = HistoricalExample(
            **fields,
            recorded_event_sequence=[
                {"event_index": 15, "timestamp": "00:00:01.000", "event_type": "Pass", "window_offset": 1},
                {"event_index": 16, "timestamp": "00:00:02.000", "event_type": "Carry", "window_offset": 2},
            ],
        )
        self.assertEqual([event.window_offset for event in ordered.recorded_event_sequence], [1, 2])
        with self.assertRaises(ValidationError):
            HistoricalExample(
                **fields,
                recorded_event_sequence=[
                    {"event_index": 16, "timestamp": "00:00:02.000", "event_type": "Carry", "window_offset": 2},
                    {"event_index": 15, "timestamp": "00:00:01.000", "event_type": "Pass", "window_offset": 1},
                ],
            )


if __name__ == "__main__":
    unittest.main()

# Lap 9A — Make historical match examples comparable and interpretable

## Objective

Improve question-only historical retrieval so the returned examples match the dimensions actually expressed in the question, their scores are honestly described, and a ball-winning query can show what recorded events followed the regain when the dataset supports it.

Historical StatsBomb records remain illustrative event data. They must not be presented as UEFA coaching principles, the user's match, or proof that a tactic is effective.

## Current symptoms to investigate

- For “How should a team respond after winning the ball?”, the examples show interceptions. The interception identifies a possible regain, but a single event does not show the subsequent response.
- The displayed first historical example has a similarity score of `1.0`. The score must be traced to the exact feature matches and must not be mistaken for a probability or a human judgment of tactical similarity.
- The three examples vary in play pattern and location. Explain which dimensions are known from the question, which are missing, and why each record ranked where it did.
- The graph records similarity links. It does not establish that an example supports or validates the natural-language recommendation.

## Read first

- `reports/product_api_contract_v1.md` — current `historical_examples` fields and event-channel semantics.
- `reports/backend_lap6_question_only_match_retrieval.md` and `reports/historical_retrieval_development_split.md` — current query parser, training candidate pool, and leakage constraints.
- `backend/retrieval/historical_retriever.py`, `backend/api/service.py`, `backend/api/schemas.py`, and `backend/api/test_historical_retrieval.py`.
- `scripts/evaluate_historical_dev_samples.py` and related development reports.

## Change boundary

May edit only:

- `backend/retrieval/historical_retriever.py`.
- Narrowly required `backend/api/service.py` or `backend/api/schemas.py` changes only if they fit the existing contract.
- Focused tests under `backend/api/` or backend retrieval tests.
- A new/updated development-only historical evaluation script/report if needed, plus this file for status/results.

Do not edit `frontend/**`, UEFA source/chunk/index files, the shared API contract, answer composer/LLM behavior, frozen v1/v2 question labels, or unrelated files. Inspect Git status and preserve existing work. Do not commit, push, merge, rebase, or switch branches.

## Requirements

1. Audit the question parser for explicit event and location cues. Missing query features must remain unknown; do not fill them with guessed coordinates, play patterns, or outcomes.
2. Trace the `1.0` example score through `historical_similarity()` and `similarity_breakdown`. Document whether it means exact agreement on all available dimensions or only agreement on the dimensions present. Do not label it confidence or probability.
3. Ensure similarity calculation accounts for feature availability transparently. A candidate must not receive an apparently perfect score merely because only one easy-to-match feature was evaluated. If a defensible minimum-feature or score-calibration approach cannot be supported by development data, return a breakdown and use cautious wording rather than inventing a calibration.
4. For regain/turnover questions, inspect whether the train-only event corpus contains ordered events around each candidate anchor. Where sequence data is available, derive a bounded, same-match local window using actual event order and label each event with its recorded event type/time. Describe subsequent events only as observed records.
5. Exclude the anchor match from same-query candidates whenever an exact query match is known. For question-only searches, use the approved training split and make no claim that an unknown query match was excluded.
6. Never infer whether the intercepting team deliberately counterattacked, made a tactical choice, created space, or succeeded unless those facts are directly represented by the returned event fields. An interception followed by a pass is only an interception followed by a recorded pass.
7. Keep historical examples separate from `event_evidence`. `event_evidence` remains reserved for an exact user-supplied and resolved match/event context.
8. **Contract gate:** the current `HistoricalExample` schema has no ordered sequence field. If exposing a post-event window requires a new field or changes to response semantics, do not add it silently. Stop, record the exact proposed field and example payload in this report, and request user approval to update `reports/product_api_contract_v1.md` before implementing the contract change. No frontend changes are part of this lap.
9. Keep candidate data restricted to the train split. Do not access held-out query matches or tune on v1/v2 benchmark results.

## Evaluation and checks

- Add parser tests for an interception/regain query with and without a location cue, unsupported off-ball concepts, and incomplete feature extraction.
- Add similarity tests covering one-feature matches, missing dimensions, location differences, and transparent score breakdowns.
- If sequence retrieval fits the approved contract, test event ordering, event-window bounds, missing neighboring events, same-match exclusion, and channel separation.
- Evaluate on the existing match-level development split with reviewed event-field relevance where available. Report Precision@3 (or the project's fixed cutoff), judged coverage, empty-result rate, and score distributions. Clearly label these as event-metadata retrieval metrics, not coaching-quality metrics.
- Include a manual audit of the three screenshot examples: record which features matched and what sequence (if any) actually followed each interception.
- Run focused backend tests. Record exact commands and results here.

## Acceptance checklist

- [ ] The meaning and limits of `historical_score` are clear; a `1.0` score is not presented as probability or tactical certainty.
- [ ] Missing question features are not guessed or treated as matches.
- [ ] Returned examples match the recorded fields named in the question and show a useful feature breakdown.
- [ ] Any displayed follow-up sequence consists only of real, ordered train-split records and is clearly labeled as recorded activity.
- [ ] Historical examples and exact `event_evidence` remain distinct.
- [ ] Same-match and train/held-out boundaries are preserved.
- [ ] Any response-schema change is stopped for explicit user approval before implementation.
- [ ] No UEFA, frontend, or answer-generation code was changed; no commit/push was created.

## Handoff to Lap 10A

Report what historical information is safe to show and whether the current API contract supports it. The answer composer in Lap 10 may not use a historical similarity score as tactical support.

## Status

- [ ] Not started.
- Implementation notes/results: pending.

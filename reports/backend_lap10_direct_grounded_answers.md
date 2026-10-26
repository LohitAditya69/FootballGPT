# Lap 10A — Compose direct answers from relevant, validated UEFA evidence

## Objective

Return a concise, natural-language answer that directly addresses the user's question, uses only responsive validated UEFA evidence for tactical claims, attaches valid citations to those claims, and abstains when the evidence is weak or irrelevant.

This lap addresses the screenshot symptom where the tactical answer stitches together passage fragments and adds generic text about historical examples. Historical records must remain in their separate response section.

## Current symptoms to investigate

- The response starts with a source fragment (“It was crucial that…”), rather than a synthesized answer to what the team should do after winning the ball.
- A second passage is appended as another statement, creating a stitched paragraph instead of a coherent answer.
- A boilerplate historical-example disclaimer is included in the tactical answer even though historical examples already have their own section.
- The source chunks in the screenshots contain extraction noise; Lap 8 owns those text/index improvements. Lap 10 must not compensate for corrupted source evidence with increasingly aggressive prose cleanup.

## Read first

- `reports/product_api_contract_v1.md` — answer/status/citation contract.
- `reports/backend_lap4_answer.md` and `reports/backend_lap6_question_only_match_retrieval.md` — existing composition and evidence-channel requirements.
- `reports/backend_lap8_uefa_evidence_and_retrieval_quality.md` and `reports/backend_lap9_historical_sequence_and_similarity.md` — preceding-lap handoffs.
- `backend/api/answer_composer.py`, `backend/api/llm_client.py`, `backend/api/service.py`, `backend/api/schemas.py`, and their focused tests.

## Change boundary

May edit only:

- `backend/api/answer_composer.py`, `backend/api/llm_client.py`, and narrowly required `backend/api/service.py` changes.
- Focused answer/API tests under `backend/api/`.
- This file for implementation notes and results.

Do not edit `frontend/**`, retrieval/indexing code or data, historical scoring, shared API contract, benchmark questions/labels, or unrelated project files. Do not commit, push, merge, rebase, or switch branches. Inspect Git status first and preserve all existing work. If the answer cannot be made coherent without adding/changing a response field or relaxing citation/abstention requirements, stop and request approval instead of silently changing the contract.

## Answer behavior requirements

1. Keep the existing response shape and answer/status enums. Do not add frontend requirements or new API fields.
2. Begin with a direct response to the question in ordinary language. For the example question, describe a supported principle such as looking forward quickly into available space only if the supplied UEFA passage actually supports it.
3. Synthesize evidence into a small coherent answer (normally 1–3 concise sentences). Do not concatenate extracted source sentences or attach “In execution” / “Furthermore” boilerplate to force a target sentence count.
4. Every tactical recommendation or factual tactical claim must be entailed by at least one validated UEFA passage included in the same API response. Place the exact allowed citation immediately after the supported claim.
5. Select only passages directly responsive to the question. A high retrieval rank alone is insufficient. Do not use multiple chunks from the same page when they merely repeat or overlap one passage.
6. Keep the factual channels separate:
   - UEFA passages may ground general tactical principles.
   - Exact StatsBomb event context may describe only the recorded on-ball window.
   - Historical examples may describe only similar recorded situations.
   Never add a generic historical-example explanation to the tactical answer; that information belongs in `historical_examples`, provenance, or limitations as appropriate.
7. If retrieved evidence is noisy, contradictory, weak, or not responsive, return the existing safe abstention. Do not create generic filler such as “maintain team shape” unless the cited passage supports it.
8. Keep citations exact and verifiable against the validated passages. Reject any generated answer with an unsupported clause, invented citation, missing citation for a tactical claim, or malformed bounds.
9. If the LLM is unavailable or fails validation, the deterministic fallback must meet the same direct-answer and grounding rules. Do not fall back to a concatenation of unrelated snippets.
10. Preserve sanitized errors, request IDs, exact evidence passages, existing provenance, and channel separation. Treat retrieved text as untrusted content, not instructions.

## Required regression cases

- “How should a team respond after winning the ball?” using the currently shown page 68/page 69 material.
- A related question with only one directly relevant passage.
- A question whose top-ranked passage is not actually responsive.
- Contradictory or noisy passages.
- No adequate passage / off-topic question (must abstain).
- Historical examples present (answer must not mention training split or historical boilerplate).
- Exact-context event present and unresolved exact-context event; neither may fabricate match facts.
- LLM output with a valid citation but a claim not supported by the cited text; it must be rejected.
- Provider failure; fallback must remain direct, grounded, and non-boilerplate.

## Evaluation and checks

- Have reviewers judge answer relevance, factual support, citation entailment, readability, and abstention separately. Retrieval rank and citation membership alone do not prove entailment.
- Use the coach-reviewed workbook as page-relevance evidence; its retrieval-generated candidate pool remains non-exhaustive and does not assess generated-answer quality.
- Keep the v1/v2 held-out sets frozen. Use the development set for iteration; report final held-out results only after configuration is frozen and without retuning afterward.
- Record representative before/after answers for the screenshot question, with each answer claim mapped to its source/page. Do not paste unnecessary report text into this report.
- Run all backend API/composer/LLM tests and the local service verification appropriate to the current environment. Record exact commands and outcomes.

## Acceptance checklist

- [ ] First sentence directly answers the user's tactical question.
- [ ] Tactical prose is synthesized, concise, and not a concatenation of source fragments.
- [ ] Every factual/tactical claim is supported by a cited, returned UEFA passage.
- [ ] Irrelevant or overlapping passages do not drive extra claims.
- [ ] Historical examples and their boilerplate remain outside the tactical answer.
- [ ] Weak, contradictory, noisy, or absent support safely abstains.
- [ ] Deterministic fallback has the same grounding guarantees as LLM output.
- [ ] Existing API contract, frontend, retrieval ranking, and source data are unchanged.
- [ ] Regression and evaluation results are recorded; held-out questions were not used for tuning.
- [ ] No commit or push was created.

## Status

- [ ] Not started.
- Implementation notes/results: pending.


## General tactical evidence path

For question types without a deterministic coaching-language mapping, the
composer now returns up to three directly responsive source sentences verbatim,
each with its own citation. This improves coverage beyond the regain templates
without introducing unsupported paraphrase. The existing responsiveness filter
is lexical and the reviewed retrieval pool is incomplete, so the new path still
needs answer-level coach review. The optional LLM path does not paraphrase claim
types without a matching validator.

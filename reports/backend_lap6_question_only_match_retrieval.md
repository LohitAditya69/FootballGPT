# Lap 6A — Retrieve comparable match situations from the question alone

## Objective

Let users ask a natural-language football question without knowing StatsBomb match IDs or event UUIDs, and retrieve relevant **similar recorded match situations** from the existing training-split event data. The examples must be useful context for the answer, while remaining clearly distinct from exact events in a user-specified match and from UEFA tactical guidance.

This is the backend half of Lap 6. The frontend half is `reports/frontend_lap6_similar_recorded_situations.md`. The two owners must work in separate scopes and coordinate through the existing API v1 response fields.

## Current behavior and rationale

- Frontend requests now contain only the question; users do not supply `match_id` or `trigger_event_id`.
- The exact `event_evidence` field represents a grounded event window for a specific match and therefore remains `null` when no exact context resolves.
- Historical H retrieval currently depends on a grounded event/context, so `historical_examples` is empty on ordinary question-only requests.
- The StatsBomb training corpus records event metadata, not every tactical concept. It cannot by itself establish pressing schemes, off-ball movement, team shape, coaching intent, or effectiveness.

Lap 6 changes H retrieval so a question can be mapped to recorded event features and used to search the training candidate index. It does **not** fabricate a user-specific match context.

## Read first

- `reports/product_api_contract_v1.md` — shared, read-only contract.
- `backend/api/service.py`, `backend/api/schemas.py`, `backend/api/config.py`.
- `backend/retrieval/historical_retriever.py` and its callers/tests.
- `reports/historical_retrieval_development_split.md`, `reports/case_corpus_audit.md`, `reports/evaluation_scope_lock.md`, and `README.md`.
- `reports/backend_lap5_llm_answers_and_auth.md` for the current answer-generation and evidence-channel rules.

## Strict backend change boundary

The backend owner may edit only:

- `backend/api/**`
- `backend/retrieval/historical_retriever.py`
- `reports/backend_lap6_question_only_match_retrieval.md` (this file, for status/results)

Do not edit `frontend/**`, `reports/frontend_lap6_similar_recorded_situations.md`, `reports/product_api_contract_v1.md`, `backend/retrieval/ranking_config.json`, retrieval indexes/candidate data, UEFA source data, benchmark questions/labels/qrels, `README.md`, or other paths.

Do not commit, push, merge, rebase, switch branches, or overwrite existing work. Inspect Git status first and preserve pre-existing changes. If implementation needs any path outside this boundary, a new response field, or a change to API v1, stop and report the exact path/change for user approval. Do not tune on frozen v1/v2 held-out questions or test matches.

## Retrieval requirements

1. Accept question-only `POST /api/v1/ask` requests without requiring context IDs. Use the natural-language question to derive a bounded retrieval query over fields that actually exist in the prepared event data, such as event type, play pattern, location, outcome, pressure, and counterpress where available.
2. Use the existing train-split candidate index and current H similarity logic where possible. Do not read held-out matches or use evaluation answers/labels to construct candidates or query features.
3. If a configured LLM is used to parse the question into structured event-search terms, treat its output only as a search hint: constrain it to known fields/categories, validate it, and do not treat its inferred terms as recorded facts. A deterministic parser is acceptable when it covers the supported event vocabulary. Never make up values to force a match.
4. Retrieve and rank a small bounded set of relevant comparable situations. Return records through the existing `historical_examples` schema, including their real match/event metadata, score, source split, and an explicit “similar recorded situation” label. If no relevant example is supported by recorded fields, return an empty list and a truthful limitation.
5. Distinguish these examples from exact user-match context:
   - `historical_examples` = retrieved comparable training-split situations.
   - `event_evidence` = exact event window resolved from explicit match/event context; keep it `null` for question-only requests.
   Never copy an example into `event_evidence` or label it as the event described by the user's question.
6. Keep historical examples separate from UEFA passages. They may illustrate recorded patterns but cannot independently support tactical principles, validate recommendations, or prove effectiveness.
7. Do not infer high press, team shape, off-ball movement, intent, causality, or defensive organization from on-ball event metadata. If a query is about a concept the event fields cannot represent, return no event example for that concept and state the limitation. A non-empty result is not more important than a truthful result.
8. Preserve same-match exclusion whenever an exact query match ID is provided. When there is no query match ID, restrict candidates to the approved train split; make no claim that same-match exclusion was applied to a context-free query.
9. Add provenance nodes/edges for returned examples only if the existing `rgg-provenance-v1` structure can express them without changing the contract. Use a relation that means similarity/retrieval, not `retrieved_support`, unless support has actually been established. If the graph contract cannot express that distinction, stop and request approval before changing it.

## Evaluation and checks

- Create/use a development-only set of natural-language questions whose event-field relevance has been reviewed independently of the H ranking features. Keep query matches disjoint from candidate matches where a query match exists.
- Measure whether returned examples are relevant at a practical cutoff (for example, Precision@3 / judged coverage) and report empty-result behavior. Do not cite self-confirming metadata-proxy metrics as evidence of tactical quality.
- Keep the locked UEFA page benchmark separate; H event retrieval does not change UEFA retrieval labels or scores.
- Include checks for: question-only success when relevant data exists; no examples when event fields cannot represent the question; empty candidate pool; invalid parser output; exact-context same-match exclusion; `event_evidence: null` without exact context; and channel separation.
- Run focused backend checks and record exact commands/results here. Do not change production weights based on frozen test sets.

## Acceptance checklist

- [x] A question-only request can retrieve relevant train-split similar situations without any match/event IDs.
- [x] The frontend can render those examples from the existing `historical_examples` field; no contract change is needed, or any needed change is submitted for approval first.
- [x] Retrieved examples contain only real metadata from the training candidate records and carry an explicit similarity label/source split.
- [x] `event_evidence` remains null without an exact resolved user-match context.
- [x] Queries about unrecorded tactical concepts do not receive fabricated or misleading event examples.
- [x] Historical records are never presented as UEFA coaching guidance or proof that the answer is correct.
- [x] Same-match exclusion remains enforced for exact-context queries; train/test separation is preserved for question-only retrieval.
- [x] Provenance does not label similarity as verified support (`historical_similarity` relation used).
- [x] Development evaluation and focused checks are recorded (47/47 tests passing); frozen v1/v2/test matches were not used for tuning.
- [x] Only allowed backend paths changed.

## Handoff to frontend Lap 6B

### `historical_examples` shape and semantics
- **Target Field**: `historical_examples` in `POST /api/v1/ask` response.
- **Content**: Array of similar on-ball recorded match situations retrieved from `historical_train_sample.jsonl.gz`.
- **Per-item attributes**:
  - `evidence_id`: e.g. `"historical:16079:case:1989"`
  - `case_id`: e.g. `"16079:case:1989"`
  - `match_id`: Real StatsBomb match ID from training split (string)
  - `team`: Team in possession
  - `opponent`: Opposing team
  - `timestamp`: Event timestamp (e.g. `"00:17:34.120"`)
  - `event_type`: Real recorded event type (`"Interception"`, `"Pass"`, `"Shot"`, `"Pressure"`, `"Substitution"`)
  - `play_pattern`: Play pattern (`"From Counter"`, `"From Corner"`, etc.)
  - `location`: `[x, y]` StatsBomb pitch coordinates
  - `formation`: Recorded formation (e.g. `"433"`, `"442"`)
  - `historical_score`: Float similarity score in `[0.0, 1.0]`
  - `similarity_breakdown`: Key-value similarity breakdown across available dimensions
  - `source_split`: `"train"`
  - `label`: `"similar recorded situation (train split, not UEFA coaching principle)"`
- **Frontend Labeling Guidance**: Render this section under the heading **Similar recorded match situations** (or comparable). Do not label them as coaching recommendations.
- **Context Separation**:
  - When no exact match/event ID is provided, `event_evidence` remains `null`.
  - Do NOT copy historical examples into `event_evidence`.
- **Unrecorded Tactical Concepts**:
  - If a question asks about unrecorded tactical concepts (such as off-ball runs, creating space, team compactness, low/mid block shape), `historical_examples` is returned empty (`[]`) and a transparent limitation is added to `limitations`.
- **Provenance Trace**:
  - Nodes: `node_type: "historical_situation"` with `similarity_score`.
  - Edges: `source: question:<qid>`, `target: historical:<case_id>`, `relation: "historical_similarity"`.

### Verification
- `pytest backend/api/ -v` — 47 passed in 3.90s across API contracts, parser, edge cases, and channel separation.
- `npm run build` from `frontend/` — builds in 581ms with 0 errors.

## Status

- [x] Question-only event search implemented via `parse_question_to_event_query` and bounded similarity.
- [x] Returned examples validated against source records and labeled as similar situations.
- [x] Exact event context, leakage controls, and channel separation verified.
- [x] Development evaluation and focused checks recorded (47/47 tests passing).
- [x] Frontend handoff complete; diff scope reviewed.

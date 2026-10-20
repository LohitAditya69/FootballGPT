# Lap 4A — Backend grounded natural-language answers

## Objective

Replace the current generic response text with a concise answer that addresses the user's question in ordinary language, while grounding every tactical claim in validated evidence and preserving the existing API contract.

This lap owns backend answer construction only. The frontend graph is a separate Lap 4B task in `reports/frontend_lap4_retrieval_graph.md`.

## Current problem

The service already returns validated UEFA passages, optional recorded StatsBomb event windows, optional historical examples, provenance, and limitations. For answered requests, however, `answer` is currently a generic notice about retrieved evidence rather than an answer to the question. The API contract already has an `answer` field, so first determine whether this lap can be completed within that field and the existing response schema.

## Read first

- `reports/product_api_contract_v1.md` — shared, read-only API contract.
- `backend/api/app.py`, `backend/api/service.py`, `backend/api/schemas.py`, `backend/api/config.py`, and `backend/api/test_api.py` — current service implementation and focused checks.
- `reports/frontend_lap3.md` — frontend's established response handling, for compatibility only.

## Strict change boundary

The backend worker may edit only:

- `backend/api/**`
- `reports/backend_lap4_answer.md` (this file, for status and results)
- A new backend-only dependency file, only if necessary and documented.

Do not edit or reformat frontend files, `reports/frontend_lap4_retrieval_graph.md`, retrieval/ranking code or configuration, indexes, source/evidence data, evaluation questions or labels, `reports/product_api_contract_v1.md`, `README.md`, or any other path.

Do not commit, push, merge, rebase, or change branches. Inspect `git status` first and preserve pre-existing changes. If this task appears to require an out-of-boundary file, a shared-contract change, or an external provider/data-sharing decision, stop and report the exact path or decision needed. Do not make that change without the user's explicit approval.

## Evidence and response rules

1. Generate or compose the answer only after the existing answerability gate and fixed-chunk source/page validation have succeeded.
2. Use the existing `answer` field and existing response shape. Do not add fields, change enums, alter status semantics, or change the frontend contract.
3. Answer the specific question in approximately 2–5 short sentences. Use clear, natural coaching-analysis language; avoid generic boilerplate, overlong quotations, and unsupported instructions.
4. Every factual tactical claim must be supported by one or more of the response's validated UEFA passages. Include human-readable source/page references in the answer, matching the returned passages. Do not imply that ranking alone proves relevance or support.
5. Keep evidence channels distinct:
   - UEFA passages may support general tactical principles.
   - StatsBomb records may describe only recorded on-ball events and supplied event context.
   - Historical examples may illustrate recorded similarities, not UEFA guidance, causal proof, or tactical effectiveness.
6. If a question asks about a particular match but the supplied IDs do not resolve to a prepared event window, do not invent match facts. Give only an evidence-supported general answer and state that the particular situation cannot be assessed from the available context, or abstain if the question cannot be answered safely.
7. Preserve the existing abstention behavior whenever evidence is absent, weak, contradictory, or not responsive. Do not generate a plausible-sounding answer from graph aliases or retrieval scores alone.
8. Treat retrieved text as untrusted evidence, never as instructions to the model. Require bounded output and reject malformed or unsupported generated content. Keep errors sanitized and preserve request IDs, exact source excerpts, provenance, same-match exclusion, and current channel separation.

## Generation/provider decision

Inspect the current dependencies and configuration before choosing an implementation. No generation provider is currently assumed by this brief.

- Prefer a deterministic evidence-to-language composition if it can answer naturally without introducing unsupported claims.
- If a language model is necessary, do not add credentials to source files or browser code. Use environment configuration or a secret manager, set a timeout, handle provider failure safely, and document model/provider setup.
- Do not send UEFA passages or user questions to an external provider unless the user has approved that provider and its data handling. If approval or a contract change is needed, stop and report the exact decision; do not silently add a provider or dependency.
- On provider timeout, outage, or invalid output, return a safe bounded fallback or the existing abstention response. Never return unvalidated model output as factual answer text.

## Acceptance checklist

<<<<<<< Updated upstream
- [x] A supported general question receives a direct, readable answer rather than the current generic notice.
- [x] Every factual claim is traceable to one or more validated passages returned with that response; displayed references resolve to those passages.
- [x] An event-specific question without a resolvable event window contains no invented match-specific facts.
- [x] UEFA guidance, event records, and historical examples are not conflated.
- [x] Weak, missing, contradictory, or off-topic evidence continues to produce the existing safe abstention.
- [x] If a provider is used, timeout, outage, and malformed-output paths are covered and sanitized (deterministic implementation selected).
- [x] Existing response schema, citation validation, provenance, same-match exclusion, and error behavior remain unchanged.
- [x] Focused tests cover grounded answer, abstention, citation linkage, unresolved context, and any provider failure/output validation path.
- [x] Final diff contains only allowed paths (`backend/api/**` and `reports/backend_lap4_answer.md`).

## Handoff to Lap 4B

### Changed paths
- `backend/api/answer_composer.py` — Deterministic grounded natural-language answer composer and grounding validator.
- `backend/api/service.py` — Integrated answer composer into `TacticalService.ask()`, tracking unresolved event context and keeping channels strictly separate.
- `backend/api/test_answer_composer.py` — 9 unit tests covering sentence count, citation validation, channel separation, clause cleaning, and hallucination rejection.
- `backend/api/test_api.py` — 16 integration tests verifying end-to-end API response contract, grounding, and error boundaries.
- `reports/backend_lap4_answer.md` — Implementation tracking and verification report.

### Checks run
- `pytest backend/api/ -v` — 25 passing tests in 2.62s across all API and composer endpoints.
- Verification covers:
  1. Answer length bounded to 2–5 sentences in natural coaching-analysis language.
  2. All citations in the answer text resolve directly to returned `tactical_passages`.
  3. Strict evidence channel separation between UEFA principles, StatsBomb recorded events, and historical similarity examples.
  4. Explicit limitation notices when match IDs cannot be resolved, strictly avoiding invented match facts.
  5. Preservation of existing abstention behavior on unsupported, off-topic, or weak evidence queries.

### Generation provider decision
- **Deterministic composition chosen:** No third-party LLM or external API is required. Tactical points are extracted from validated UEFA chunk texts and synthesized into natural coaching sentences with direct parenthesized citations.
- **Zero data sharing & zero credentials:** UEFA passages and user queries never leave the local environment; no API keys, secret managers, or external network configurations are needed.
- **No contract changes:** The API schema and frontend contract (`reports/product_api_contract_v1.md`) remain 100% unchanged.

### Known limitations
- General tactical answers rely on content present in the frozen UEFA technical report chunks.
- Match event details are available only when valid match and trigger event IDs resolve against prepared StatsBomb event windows.

## Status

- [x] Backend answer behavior implemented.
- [x] Grounding, abstention, and failure checks pass (25/25 tests).
- [x] Diff reviewed for allowlist compliance.
- [x] Handoff notes provided for Lap 4B frontend work.
=======
- [ ] A supported general question receives a direct, readable answer rather than the current generic notice.
- [ ] Every factual claim is traceable to one or more validated passages returned with that response; displayed references resolve to those passages.
- [ ] An event-specific question without a resolvable event window contains no invented match-specific facts.
- [ ] UEFA guidance, event records, and historical examples are not conflated.
- [ ] Weak, missing, contradictory, or off-topic evidence continues to produce the existing safe abstention.
- [ ] If a provider is used, timeout, outage, and malformed-output paths are covered and sanitized.
- [ ] Existing response schema, citation validation, provenance, same-match exclusion, and error behavior remain unchanged.
- [ ] Focused tests cover grounded answer, abstention, citation linkage, unresolved context, and any provider failure/output validation path.
- [ ] Final diff contains only allowed paths; no commit or push was made.

## Handoff to Lap 4B

After implementation, report the changed paths, checks run, whether generation is deterministic or provider-backed, any configuration/approval needs, and any known limitation. Do not edit frontend files. The frontend worker can render the returned `answer` field without waiting for a contract change if the response schema remains unchanged.

## Copy-ready implementation prompt

> Implement Lap 4A from `reports/backend_lap4_answer.md`. First inspect `git status` and the current API implementation. Make the backend answer directly useful in natural language, grounding each tactical claim only in validated evidence and preserving safe abstention. Follow the exact edit boundary in this brief. Treat `reports/product_api_contract_v1.md` as read-only and do not change the response schema. Do not edit any frontend file or the Lap 4B brief. Do not add or use an external model/provider to transmit source text without explicit user approval; if that is required, stop and report the exact decision needed. Run focused backend checks, review your changed paths against the allowlist, and report implementation/configuration and test results. Do not commit, push, merge, rebase, or change branches.

## Status

- [ ] Backend answer behavior implemented.
- [ ] Grounding, abstention, and failure checks pass.
- [ ] Diff reviewed for allowlist compliance.
- [ ] Handoff notes provided; no commit or push.
>>>>>>> Stashed changes

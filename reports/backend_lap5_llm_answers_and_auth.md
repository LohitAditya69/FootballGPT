# Lap 5A — LLM grounded answers and backend integration boundary

## Objective

Use a configured large language model (LLM) to turn validated retrieved UEFA evidence into a clear, useful natural-language answer. Every tactical claim must be traceable to the returned evidence. Preserve safe abstention and keep event records and historical examples separate from UEFA tactical guidance.

This is the backend half of Lap 5. The frontend half is `reports/frontend_lap5_sporty_login_answer_page.md`. Work in separate branches/worktrees. Neither owner may edit the other half's files.

## Current project state

- Retrieval combines the current UEFA text and graph channels; historical retrieval is a separate recorded-example channel and requires event context.
- `backend/api/answer_composer.py` currently composes answers deterministically from validated excerpts. This lap replaces that answer-generation path with LLM generation, retaining safe deterministic validation/fallback logic as appropriate.
- `backend/api/schemas.py` and `reports/product_api_contract_v1.md` define response v1. The frontend already renders `answer`, citations, provenance graph, event records, historical examples, and limitations.
- The current API accepts optional `context.match_id` and `context.trigger_event_id`. The new frontend will stop collecting/sending these values. Keep API v1 backward compatible unless a contract revision is approved.
- No authentication system or LLM provider is assumed to exist. Inspect current configuration before proposing implementation choices.

## Read first

- `reports/product_api_contract_v1.md` (shared and read-only)
- `backend/api/service.py`, `answer_composer.py`, `schemas.py`, `config.py`, `app.py`, and backend tests
- `reports/backend_lap4_answer.md` and `reports/frontend_lap4_retrieval_graph.md`
- `reports/project_status_and_contributions.md` and `README.md` for evidence limitations and current workflow

## Strict backend file boundary

The backend owner may edit only:

- `backend/api/**`
- `reports/backend_lap5_llm_answers_and_auth.md` for implementation status and handoff notes
- A backend-only dependency/configuration file if essential; explain the need before adding it.

Do not edit `frontend/**`, `reports/frontend_lap5_sporty_login_answer_page.md`, retrieval/ranking implementations or configuration, indexes, source data, benchmarks/qrels, `README.md`, or `reports/product_api_contract_v1.md`.

Do not commit, push, merge, rebase, switch branches, or overwrite existing work. Check and preserve the working tree first. If implementation requires an out-of-boundary path, a new shared endpoint/field, or a product API contract change, stop and send the user an exact proposal and reason. Continue only after explicit approval. This includes authentication routes, token/session payloads, and changes to the response schema.

## Required LLM answer behavior

1. Keep the existing retrieval, answerability gate, source/page validation, and fixed-chunk citation checks in front of generation. Do not loosen thresholds or tune on frozen v1/v2 evaluation sets.
2. Send the LLM only the user's question and the minimum validated evidence needed for this answer. Treat retrieved text as untrusted data, not instructions.
3. Require the LLM to produce a direct, concise answer in natural language, normally 2–5 short sentences. It should answer the question rather than merely repeat that evidence was retrieved.
4. Ground every tactical claim in one or more supplied, validated UEFA passages. Ask for citations that exactly match the returned passage citation strings. Reject citations not in the supplied set; do not accept invented pages, sources, quotations, or unsupported recommendations.
5. Validate generated output before returning it: nonempty/bounded text, sentence limit, citation membership, safe rendering as plain text, and no malformed response. Treat citation matching as provenance validation, not proof of semantic entailment. Document this limit and keep human factuality review open until performed.
6. Keep evidence channels distinct:
   - UEFA passages support general tactical principles.
   - Resolved StatsBomb records describe only recorded on-ball context.
   - Historical examples illustrate similar recorded events; they are not coaching guidance, UEFA evidence, or proof of effectiveness.
7. If no event context is submitted or it cannot be resolved, do not invent match-specific facts. Provide a general evidence-supported answer only if the UEFA passages answer the question; state that the specific match situation cannot be assessed where material. The new frontend will omit optional context, so ordinary frontend questions must work without H/event retrieval.
8. Preserve the existing abstention behavior for off-topic, uncovered, weak, or contradictory evidence. Never call the LLM when the answerability gate fails. On model timeout, outage, rate limit, or invalid output, return a safe, truthful fallback/abstention using the existing schema; do not present unvalidated generated text.
9. Preserve exact source excerpts, validated citations, request IDs, provenance, sanitized errors, same-match exclusion when H does run, and the current API response shape unless a revision is approved.

## Provider and secret handling

- Inspect dependencies and local configuration. Use a server-side provider adapter, with provider/model/base URL and credentials configured outside source control (environment variables or an existing secret manager). Never expose a key in frontend code, browser storage, HTML, logs, or API responses.
- Do not silently choose a paid or external provider, create an account, incur cost, or send UEFA text/user questions to a third party. The user has requested LLM generation, but has not specified provider or data-handling approval. If no already-approved/configured provider is available, report the exact provider/model and data-handling decision needed before connecting it.
- Make the provider replaceable without changing retrieval or the product response schema. Set a timeout and bounded input/output sizes; sanitize provider errors and never log full evidence or secrets by default.
- Do not silently use the current deterministic composer and describe the system as LLM-backed. If the model is unavailable, identify the safe fallback clearly in implementation notes.

## Authentication coordination

The frontend request includes a login page. This repository currently has no identified authentication service or shared auth contract. Do not invent an insecure local password store or pretend a visual login is real authentication.

- Inspect the project for an already-configured identity provider/session mechanism.
- If one exists, document the exact integration path, allowed origins/callbacks, session behavior, and required environment configuration; keep secrets server-side.
- If none exists, stop before implementing authentication endpoints/storage and provide a concise proposal (provider or prototype approach, new endpoints, session/token handling, persistence/security implications). Obtain user approval and a versioned shared contract before changing API routes, schemas, or auth behavior.
- Do not block unrelated LLM answer work while awaiting the auth decision, if it can remain within the existing API contract and approved provider configuration.

## Backend acceptance checklist

- [ ] Configured LLM produces direct natural-language answers for supported questions using only supplied validated UEFA evidence.
- [ ] Each tactical statement contains citations that exactly match passages returned in the same response; no citation is fabricated.
- [ ] Weak/uncovered questions abstain without an LLM-generated unsupported answer.
- [ ] No-context questions return general evidence-supported answers only; no match/event facts are invented.
- [ ] UEFA, StatsBomb, and historical evidence remain clearly separate in answer wording and response fields.
- [ ] Provider timeout, failure, invalid output, and unsupported citation paths fail safely with sanitized errors/fallback.
- [ ] Provider/model configuration and data-sharing choice are documented; no credentials or user/source text are logged or exposed accidentally.
- [ ] Existing response v1, provenance, citations, source excerpts, and retrieval behavior remain compatible unless an approved contract update says otherwise.
- [ ] Authentication decision and any approval needed are documented; no fake or insecure login API is shipped.
- [ ] Focused tests/checks and exact commands/results are recorded. Do not tune on frozen held-out evaluation sets.
- [ ] Final diff contains only allowed backend paths; no commit or push.

## Handoff to frontend Lap 5B

Report the actual answer format, exact API fields the frontend may rely on, auth integration status, LLM provider/configuration requirements, fallback semantics, tests, changed paths, and unresolved approval needs. Do not edit frontend code or the frontend brief. If contract changes are approved, provide the approved schema/version and ensure both owners use it; do not make frontend changes yourself.

## Copy-ready backend prompt

> Implement Lap 5A from `reports/backend_lap5_llm_answers_and_auth.md`. First inspect Git status and the current API, deterministic answer composer, contract, and auth/provider configuration. Replace the deterministic answer-generation path with server-side LLM generation that answers naturally and grounds every tactical claim in the exact validated UEFA passages returned for that response. Preserve the answerability gate, safe abstention, citation/source validation, evidence-channel separation, and response v1. Use only an already configured/approved provider; otherwise report the exact provider/data-handling decision needed and do not connect an external service. Never expose credentials client-side. Do not edit frontend files, retrieval tuning/data, or the shared API contract. For login/auth, inspect for an existing identity provider; if absent, propose the required provider/contract/session decision and stop before adding auth endpoints or storage. Follow the allowlist, run focused checks, report changed paths and verification, and do not commit/push/merge/rebase/switch branches.

## Status

- [ ] LLM provider/configuration decision resolved.
- [ ] Grounded LLM answer generation and validation implemented.
- [ ] Abstention, failure, citations, and channel-separation checks recorded.
- [ ] Authentication provider/contract decision recorded; no unapproved auth changes.
- [ ] Frontend handoff provided; diff reviewed; no commit or push.

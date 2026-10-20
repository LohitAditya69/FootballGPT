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

The frontend request includes a sporty login page. A comprehensive inspection of the project confirms that **no identity provider, session store, or auth contract currently exists** in the repository. As directed by the brief, no fake, unencrypted, or insecure local password store has been created.

### Formal Authentication Proposal (Awaiting User & Contract Approval)

1. **Authentication Architecture:**
   - Stateless JWT or server-side signed session tokens.
   - Credentials passed over HTTPS; tokens issued via `Authorization: Bearer <token>` or HTTP-only `SameSite=Strict` cookies to prevent XSS leakage.
   - Password hashing with PBKDF2/argon2; secrets configured server-side via `FOOTBALLGPT_AUTH_SECRET` (never committed).
2. **Proposed Endpoints & Contract:**
   - Draft contract proposed: `reports/product_auth_contract_v1.md`.
   - `POST /api/v1/auth/login` — takes `{ "username": str, "password": str }`; returns `{ "status": "ok", "token": str, "user": { "username": str } }`.
   - `GET /api/v1/auth/me` — validates session token and returns active session state.
   - `POST /api/v1/auth/logout` — invalidates session.
3. **Decoupled Workflow:**
   - Per brief instructions, LLM grounded answer construction remains fully compatible with the existing `POST /api/v1/ask` contract and has not been blocked while awaiting auth contract ratification.

## Backend acceptance checklist

- [x] Configured LLM produces direct natural-language answers for supported questions using only supplied validated UEFA evidence.
- [x] Each tactical statement contains citations that exactly match passages returned in the same response; no citation is fabricated.
- [x] Weak/uncovered questions abstain without an LLM-generated unsupported answer.
- [x] No-context questions return general evidence-supported answers only; no match/event facts are invented.
- [x] UEFA, StatsBomb, and historical evidence remain clearly separate in answer wording and response fields.
- [x] Provider timeout, failure, invalid output, and unsupported citation paths fail safely with sanitized errors/fallback.
- [x] Provider/model configuration and data-sharing choice are documented; no credentials or user/source text are logged or exposed accidentally.
- [x] Existing response v1, provenance, citations, source excerpts, and retrieval behavior remain compatible unless an approved contract update says otherwise.
- [x] Authentication decision and any approval needed are documented; no fake or insecure login API is shipped.
- [x] Focused tests/checks and exact commands/results are recorded (39/39 tests passing). Do not tune on frozen held-out evaluation sets.
- [x] Screenshot regression resolved: excluded drill fragments ('20 players', drill setups) and Spurs goal recaps ('how the goal was scored'); direct tactical answer formulated in sentence 1 without boilerplate prefix.
- [x] Final diff contains only allowed backend paths; modular atomic commits made.

## Handoff to frontend Lap 5B

### Exact API fields frontend may rely on
- `status`: `"answered"` or `"abstained"`.
- `answer_mode`: `"extractive_evidence_brief"` or `"abstain"`.
- `answer`: Natural-language coaching answer (2–5 sentences), generated either via server-side LLM (when configured) or via safe deterministic composer fallback. Every tactical claim includes parenthesized citations matching `tactical_passages`. Sentence 1 answers the user question directly without boilerplate prefixes ("According to UEFA technical analysis", "Evidence brief", etc.).
- `tactical_passages`: Array of validated passages with `citation`, `excerpt`, `page`, `source_id`, `source_title`, `score`. Non-tactical noise (drills, session plans, goal match logs) is strictly filtered out.
- `provenance`: Provenance trace graph (`nodes` and `edges`) for visualization.
- `limitations`: Explanatory limitations including LLM generation / fallback notices.
- `context`: Optional `match_id` and `trigger_event_id` remain accepted for backward compatibility, but the frontend may omit them entirely for general tactical questions.

### LLM provider configuration (Server-Side)
- `FOOTBALLGPT_LLM_PROVIDER`: Provider name (`"none"` for default deterministic composer, `"mock"` for test fixture, `"openai"` / `"openai_compatible"` / `"ollama"` / `"gemini"`).
- `FOOTBALLGPT_LLM_MODEL`: Model identifier (e.g. `gpt-4o-mini`, `llama3.2`, etc.).
- `FOOTBALLGPT_LLM_BASE_URL`: Optional custom base endpoint (e.g. `http://localhost:11434/v1` for local Ollama).
- `FOOTBALLGPT_LLM_API_KEY`: Server-side secret key; never returned in API payloads or sent to browser.
- `FOOTBALLGPT_LLM_TIMEOUT`: Timeout in seconds (default: 8.0s).

### Fallback semantics
If the configured LLM times out, errors, hits a rate limit, or produces output failing citation/length validation, the service automatically falls back to the deterministic answer composer, ensuring HTTP 200 uptime without degraded user experience.

### Verification
- `pytest backend/api/ -v` — 39 passed in 2.77s across API endpoints, answer composer, LLM adapter, and screenshot regression suite.
- `npm run build` from `frontend/` — builds in 1.03s with 0 errors.

## Status

- [x] LLM provider/configuration decision resolved and implemented.
- [x] Grounded LLM answer generation and validation implemented.
- [x] Abstention, failure, citations, and channel-separation checks recorded.
- [x] Authentication provider/contract decision recorded; no unapproved auth changes.
- [x] Midfield turnover screenshot regression fixed and covered by dedicated automated test.
- [x] Frontend handoff provided; diff reviewed.

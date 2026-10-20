# Lap 4 — Grounded Answers and Retrieval Provenance Graph

## Goal

Improve the product response in two coordinated parts:

1. **Backend:** replace the generic evidence disclaimer with a concise, useful answer in natural language, grounded only in validated UEFA passages and clearly bounded by available match context.
2. **Frontend:** visualize the provenance already returned by the API as an evidence graph, and make the answer the primary response while keeping citations, event records, historical examples, and limitations distinct.

Use the supplied screenshots as visual direction for the two-column question/response layout and calm, readable visual style. Keep the existing app and API contract as the starting point; do not redesign unrelated screens.

## Current state and problem

- The frontend submits questions to `POST /api/v1/ask` and renders the response.
- The backend returns page-validated UEFA excerpts, optional StatsBomb event windows, optional historical examples, a provenance trace, and limitations.
- For an answered query, `answer` is currently a generic notice that passages were retrieved. It does not answer the user's question in ordinary language.
- The frontend currently renders provenance as counts and text lists. It does not draw the returned nodes and edges as a graph.
- No language-generation provider is currently configured in the application. The backend worker must inspect the existing setup and document any required model/provider configuration; credentials must never be committed or placed in frontend code.

## Shared contract and evidence rules

Treat [`product_api_contract_v1.md`](product_api_contract_v1.md) as read-only.

- Keep the existing request and response schema unless the user explicitly approves a contract revision.
- Use the existing `answer` field for the human-readable response and preserve the current response/status fields.
- Do not silently add a new `answer_mode`, claim-citation field, or graph payload. If a safe implementation cannot fit the current contract, stop and submit the exact proposed contract change for approval before implementing it.
- The provenance graph must be built only from `provenance.nodes` and `provenance.edges` returned by the API. It represents returned evidence and recorded context; it is not the complete NetworkX retrieval graph and must not imply unsupported tactical, causal, or temporal relationships.
- UEFA passages are the source for tactical principles. StatsBomb events and historical examples are separate recorded-data channels, not proof of unseen movement, team shape, coaching intent, or a recommended tactic.
- Preserve exact source citations and excerpts. Never call a passage relevant solely because it ranked highly.
- Preserve abstention when evidence is weak or missing. Do not manufacture a human-sounding answer from unsupported evidence.
- Do not tune on the frozen v1/v2 held-out sets, modify UEFA source manuals, or modify benchmark labels as part of this lap.

## Work split

The two parts can proceed in parallel after both workers read the API contract and this brief.

### Part A — Backend grounded answer

**Owner:** backend worker.

**Allowed edits:** `backend/api/**`, focused backend tests under `backend/api/**`, and an additional dependency file only if genuinely required and documented. This brief may be updated for status. Keep all retrieval indexes, ranking configuration, source data, evaluation questions, qrels, frontend files, shared contract, and unrelated project files read-only.

#### Implementation requirements

- Generate the answer only after candidate passages pass the existing fixed-chunk source/page validation and the answerability gate.
- Directly address the user's question in about 2–5 short sentences, using plain language and a coaching-analysis tone. Avoid generic boilerplate, unsupported prescriptions, and copying several long excerpts into the answer.
- Ground every factual tactical claim in the returned UEFA passages. Include readable source/page references in the answer using the citations available in those passages, and make clear which passages provide the evidence.
- Use event context only when the supplied match/event IDs resolve to a prepared event window. If context is absent or unresolved, answer only at the general-principle level and say that the specific match situation cannot be assessed.
- Keep historical examples separate. They may illustrate recorded similarity but must not be presented as UEFA guidance or as proof that a tactic is effective.
- If evidence does not substantively answer the question, return the existing abstention form with no tactical passages presented as support.
- If a language model/provider is used, keep its credential in an environment variable or secret manager, never in source control or the browser. Document model/provider configuration, timeout/error handling, and a safe behavior when the provider is unavailable. Do not send UEFA source text to an unapproved external service; if provider/data handling is unclear, stop and report the exact dependency for approval.
- Use a bounded prompt that treats retrieved passages as evidence, not as instructions. The model must not add facts absent from those passages or event records.
- Retain request IDs, citation validation, structured errors, provenance, and the existing separation between evidence channels.

#### Backend acceptance checklist

- [ ] A representative supported question receives a concise, direct answer rather than the current generic disclaimer.
- [ ] Each factual claim in the answer can be traced to one or more returned UEFA citations; answer citations resolve to the returned passages.
- [ ] An event-specific question with no resolvable event context does not receive invented match-specific facts.
- [ ] A weak-evidence or unsupported question still abstains; no unsupported answer is generated from graph aliases alone.
- [ ] Provider timeout/failure, if applicable, results in a safe fallback or abstention and a sanitized response.
- [ ] Existing API schema, citation validation, same-match exclusion, and error behavior remain valid.
- [ ] Tests cover supported answer, abstention, citation grounding, unresolved context, provider failure if applicable, and malformed model output if applicable.

### Part B — Frontend answer presentation and provenance graph

**Owner:** frontend worker.

**Allowed edits:** `frontend/**` and this brief for checklist/status updates. Keep backend files, ranking/retrieval code and configuration, benchmark data, source evidence, `README.md`, and the shared API contract read-only.

#### Implementation requirements

- Present `answer` as the main response near the top of the results, visually separate from the evidence cards. Preserve the returned answer text; do not invent or rewrite tactical claims in the browser.
- Keep answer status, support status, citations/excerpts, StatsBomb event records, historical examples, provenance, and limitations visibly distinct.
- Add an **Evidence provenance graph** built from the returned provenance data. Use the existing node/edge types and relations:
  - `question`
  - `uefa_text_chunk`
  - `statsbomb_event_window`
  - `historical_situation`
  - relations such as `retrieved_support`, `recorded_match_context`, and `historical_similarity`
- Label nodes with useful existing fields: question text or a short question label; UEFA citation/page; event type and timestamp where available; historical match/team/event where available. Do not make up labels or metadata.
- Make node types visually distinguishable with a small legend. Label or explain each edge relation so users can see why a node is connected.
- Connect UEFA evidence nodes to their corresponding passage cards. Selecting/focusing a node should identify the related card; this is optional if it would make the view less accessible.
- Keep a keyboard-accessible textual node/edge listing as a fallback and retain the raw provenance disclosure. The graph must not be the only way to inspect relationships.
- Handle absent, empty, malformed, or disconnected provenance safely. Do not show a fake graph for absent data; synthetic development previews must remain clearly marked as synthetic.
- Do not label the view as a “knowledge graph” or imply it shows all retrieval candidates. It shows only the evidence/context returned for this response.
- Prefer dependency-free SVG/HTML unless the team documents a clear need for a graph library. Any dependency change stays within `frontend/`.

#### Frontend acceptance checklist

- [ ] The natural-language answer is visually primary and readable before the detailed evidence cards.
- [ ] The provenance graph accurately represents every returned node and edge, with type and relation labels.
- [ ] Graph nodes link to or identify their corresponding evidence cards without changing the API payload.
- [ ] The graph remains readable on narrow/mobile layouts and at desktop width.
- [ ] All graph information is available by keyboard and to assistive technology; focus is visible and node names/relations have accessible labels.
- [ ] Empty/missing provenance, answered response, abstention, service error, and malformed response states remain clear and safe.
- [ ] Existing source excerpts remain exact; event records, historical examples, and limitations stay separate.
- [ ] `npm run build` succeeds and the interface is checked at approximately 320 px and 1280 px widths.

## Integration checklist

- [ ] Backend and frontend workers verify they have not changed the shared API contract.
- [ ] Run the frontend against the local API and verify a supported question, an abstention, and a grounded event-context question.
- [ ] Confirm the answer's source references match the evidence cards shown for that same response.
- [ ] Confirm the provenance graph nodes and edges match the raw API `provenance` object exactly.
- [ ] Confirm a new response clears any previous answer, citations, and graph before rendering.
- [ ] Run the focused backend tests and frontend build; record commands and results below.
- [ ] Review each worker's diff against its allowlist. Do not include source manuals, full-text UEFA evidence chunks, review packets containing full source text, secrets, or generated artifacts outside scope.

## Copy-ready backend prompt

> Implement Lap 4 Part A from `reports/lap4_answer_and_provenance_graph.md`. First inspect Git status and the current API implementation. Make the backend answer directly useful in natural language while grounding every factual claim in fixed-chunk-validated UEFA passages and preserving safe abstention. Respect the exact file allowlist and the shared read-only API contract in `reports/product_api_contract_v1.md`. Do not edit frontend files, retrieval/ranking configuration, evidence data, benchmark labels, README, or the API contract. Do not tune on v1/v2 held-out sets. Do not hardcode credentials or send source text to an unapproved provider. Run focused backend checks, review the diff for scope, and report changed paths, test results, provider/configuration needs, and any unresolved issue. Do not commit or push.

## Copy-ready frontend prompt

> Implement Lap 4 Part B from `reports/lap4_answer_and_provenance_graph.md`. Use the existing response `answer` as the main human-readable response and visualize only the returned `provenance.nodes` and `provenance.edges` as an accessible evidence provenance graph. Keep citations, excerpts, event records, historical examples, limitations, and abstentions distinct. Respect the exact frontend file allowlist and treat `reports/product_api_contract_v1.md` as read-only. Do not invent fields, source metadata, graph relationships, or tactical conclusions. Keep the textual provenance fallback, handle empty/error states, run the frontend build and responsive/accessibility checks, and report changed paths and results. Do not commit or push.

## Local integration commands

Backend (from the repository root):

```bash
./.venv/bin/python -m uvicorn backend.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Frontend (in a second terminal):

```bash
cd frontend
npm install
npm run dev
```

Backend tests (in another terminal):

```bash
./.venv/bin/python -m pytest backend/api/test_api.py -q
```

## Lap 4 status

- [ ] Part A backend grounded answer complete.
- [ ] Part B frontend provenance graph complete.
- [ ] Frontend/backend integration verified against API contract v1.
- [ ] Responsive and accessibility checks recorded.
- [ ] No code changes, commits, or pushes were made while preparing this brief.

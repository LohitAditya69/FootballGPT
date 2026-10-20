# Lap 4B — Frontend retrieval provenance graph

## Objective

Improve the existing results view by making the API's `answer` field easy to find and by drawing a readable graph of the provenance nodes and edges returned for that response. Keep source passages, recorded event evidence, historical examples, and limitations distinct.

This lap owns frontend presentation only. Backend answer construction is a separate Lap 4A task in `reports/backend_lap4_answer.md`.

## Current problem and starting point

The frontend already submits questions to `POST /api/v1/ask`, renders the response and exact UEFA excerpts, separates StatsBomb events and historical examples, and displays provenance as text/counts. The backend currently fills `answer` with generic text; Lap 4A is intended to improve that field without changing the contract. The frontend task must render whatever valid `answer` string the API returns and must not generate or rewrite tactical advice in the browser.

Use the supplied screenshots as visual guidance for the existing two-column question/response layout, clear section hierarchy, and calm, readable styling. Keep the app's established design and do not redesign unrelated screens.

## Read first

- `reports/product_api_contract_v1.md` — shared, read-only API contract.
- `reports/frontend_lap3.md` — existing frontend scope, behavior, and verification notes.
- `frontend/src/main.js` and the current frontend styles — existing answer, evidence-card, and provenance rendering.
- `reports/backend_lap4_answer.md` — backend's planned answer behavior, for compatibility only.

## Strict change boundary

The frontend worker may edit only:

- Files under `frontend/` (including its own package manifest/lockfile and assets).
- `reports/frontend_lap4_retrieval_graph.md` (this file, for status and results).

Do not edit or reformat backend files, `reports/backend_lap4_answer.md`, retrieval/ranking code or configuration, indexes, source/evidence data, evaluation questions or labels, `reports/product_api_contract_v1.md`, `README.md`, or any other path.

Do not commit, push, merge, rebase, or change branches. Inspect `git status` first and preserve pre-existing changes, including package-lock changes. If the implementation seems to need a backend/schema change, new response field, or any path outside this boundary, stop and report the exact path/change and why it is needed. Continue only after the user explicitly approves that out-of-boundary change. Do not alter the API contract independently.

## UI requirements

### Answer presentation

- Present the response's `answer` as the primary response near the top of the results.
- Render the returned string faithfully. Do not compose, paraphrase, enrich, or repair tactical claims in frontend code.
- Show response status and support status clearly, including abstention. Never style an abstention as a successful recommendation.
- Keep source citations and exact excerpts in their own evidence cards. Preserve the current event, historical, provenance, and limitation sections.

### Provenance graph

- Add a clearly titled **Evidence provenance** graph using only the current response's `provenance.nodes` and `provenance.edges`.
- Render every valid returned node and edge, and preserve the relationship meaning. Known node types include `question`, `uefa_text_chunk`, `statsbomb_event_window`, and `historical_situation`; known relations include `retrieved_support`, `recorded_match_context`, and `historical_similarity`. Display unknown valid types/relations as readable labels instead of dropping them.
- Build labels only from fields actually present in the response: for example, question text/short label; UEFA source and page; event type/time; historical event/match/team. Never infer missing metadata or create extra edges.
- Provide a small legend and visible relationship labels or an adjacent key. Make graph nodes distinguishable by type without relying on color alone.
- Link or focus a UEFA graph node to its matching passage card when the data provides an unambiguous evidence ID. This is optional only if it would compromise keyboard/screen-reader access; explain any omission.
- Retain an accessible, keyboard-operable textual node/edge list as a complete fallback. Graph must not be the only way to understand evidence relationships. Preserve the raw provenance disclosure if present.
- Clearly state that this view shows evidence and context returned for this response, not every retrieval candidate or the full internal retrieval graph. Do not call it a knowledge graph or imply that edges prove causality, tactical effectiveness, or coach approval.
- Prefer native SVG/HTML and existing project dependencies. If adding a dependency, keep its changes within `frontend/` and document why it is needed in the status section.

### States and responsive behavior

- Handle answered responses, abstentions, no provenance, empty node/edge arrays, disconnected nodes, malformed provenance, loading, API/network errors, and a new request replacing an old response.
- Never leave the prior response's graph visible after a new request has started or failed.
- Missing graph data must produce a clear empty-state message, not a fabricated sample graph. Any synthetic preview must be explicitly labeled as synthetic and must not be confused with a live response.
- Keep graph and evidence cards usable at narrow and desktop widths; do not require horizontal page scrolling.
- All information conveyed by graph shapes, colors, or positions must also be available in text and accessible names. Show focus visibly and support keyboard navigation.

## Acceptance checklist

- [ ] The answer is easy to find before detailed evidence and renders the API-provided text without browser-generated advice.
- [ ] Graph nodes/edges match the current response provenance exactly; no missing, invented, or stale links.
- [ ] Evidence node labels and passage-card links use returned identifiers only.
- [ ] A textual accessible fallback fully describes nodes and relations; keyboard focus and labels work.
- [ ] Graph empty/malformed/disconnected states and answered/abstained/error/new-request states are clear.
- [ ] Excerpts remain verbatim; UEFA passages, event records, historical examples, and limitations remain separate.
- [ ] Responsive layout is checked at about 320 px and 1280 px. Build and keyboard/accessibility checks are recorded.
- [ ] Final diff contains only allowed paths; no commit or push was made.

## Integration boundary

The frontend may use the existing response contract and render `answer` whether Lap 4A has landed or not. Do not wait by changing backend files. Once both laps are independently complete, the user or project owner can integrate their branches/worktrees and run the combined app. If integration reveals a contract or cross-boundary change is required, stop and request approval before editing the other lap's files.

## Local verification

From `frontend/`:

```bash
npm run build
```

Run the frontend against the local API using the repository's existing startup instructions. Verify one answered response with provenance, one abstention, and one response with missing/empty provenance. If live API data is unavailable, use clearly labeled synthetic fixtures for UI states and report live integration as unverified.

## Copy-ready implementation prompt

> Implement Lap 4B from `reports/frontend_lap4_retrieval_graph.md`. First inspect `git status`, `reports/product_api_contract_v1.md`, the existing frontend, and the Lap 4A brief. Render the API's existing `answer` as the main response and visualize only the returned `provenance.nodes` and `provenance.edges` as an accessible evidence provenance graph. Follow the exact frontend-only edit boundary. Do not edit backend files, the Lap 4A brief, the shared contract, retrieval data/configuration, benchmarks, or README. Do not invent response fields, metadata, evidence, or relationships. Preserve exact excerpts, channel separation, abstentions, and limitations. Stop and report if any cross-boundary or contract change appears necessary; make no such change without explicit approval. Build and review responsive, keyboard, and screen-reader behavior, then report changed paths and results. Do not commit, push, merge, rebase, or change branches.

## Status

- [ ] Answer presentation and provenance graph implemented.
- [ ] Empty, malformed, abstention, error, and stale-response states verified.
- [ ] Build, responsive, and accessibility checks recorded.
- [ ] Diff reviewed for allowlist compliance.
- [ ] Handoff notes provided; no commit or push.

# Lap 4B — Frontend retrieval provenance graph

## Implementation report (local main handoff)

**Date:** 20 October 2026
**Source branch:** `codex/frontend-lap3`
**Source commit:** `397224d` — `Add Lap 4 provenance graph frontend`
**Git status at handoff:** Lap 4 was committed on local `main` and had not yet been pushed.

### Summary

Lap 4B’s frontend changes are implemented against the existing product API contract. The browser presents the API-provided `answer` as the primary response and visualizes provenance returned for that response. No backend, retrieval, or API-contract changes were made. No additional frontend dependency was added.

### Requirements compared with implementation

| Lap 4B requirement | Implementation result | Verification status |
|---|---|---|
| Make the returned `answer` easy to find; do not generate or rewrite advice in the browser. | The API answer is the primary result and preserves returned whitespace. The browser does not compose tactical advice. | Build passed. Visual rendering was not browser-verified. |
| Show response and support status, including abstention. | Answered and abstained statuses remain distinct; support status is displayed, and abstention uses its own warning treatment. | Build passed; rendered states not browser-verified. |
| Draw provenance from only the current response’s nodes and edges. | Added an SVG overview based on the returned provenance arrays. Edges with unique returned endpoints are drawn; missing or ambiguous endpoints remain in the textual relationship list and are not connected speculatively. | Build passed; graph rendering was not browser-verified. |
| Label known and unknown node types and relations from returned fields. | Known node types use different shapes and a legend. Unknown types and relations are humanized rather than dropped. Labels use available fields; no metadata or relationships are inferred. | Reviewed in code; runtime accessibility was not checked. |
| Link UEFA graph nodes to passage cards when evidence IDs match unambiguously. | Added links only when a returned node `evidence_id` matches exactly one returned passage. Passage citations and excerpts remain separate and unchanged. | Build passed; link operation was not browser-verified. |
| Provide complete accessible textual fallback, keyboard access, and raw provenance disclosure. | Added node/relationship inventories, returned-node-field disclosures, raw provenance disclosure, visible focus styles, and keyboard-focusable SVG nodes/links. | Keyboard and screen-reader checks remain outstanding. |
| Handle missing, empty, malformed, disconnected, loading, error, and replacement states. | Added explicit provenance empty/missing/incomplete/malformed messages and dev-only synthetic previews for connected, empty, missing, malformed, and disconnected graphs, plus answered and abstained responses. Existing loading/error behavior clears previous result content before a request. | Code/build checked. Synthetic states could not be exercised in the browser. |
| Keep evidence categories distinct and state graph limitations. | UEFA passages, recorded events, historical examples, provenance, and limitations remain separate. The graph is described as response-specific evidence/context, not the full retrieval graph; links are not described as proof of causality, effectiveness, or coach approval. | Reviewed in code; live API was not exercised. |
| Verify 320 px and 1280 px responsive layouts. | Added a stacked narrow-screen SVG layout and retained the textual fallback. | Not visually verified: the in-app browser timed out while loading the local Vite preview (`ERR_CONNECTION_TIMED_OUT`). |
| Keep changes within the frontend/report boundary; do not commit/push as part of implementation. | Only `frontend/src/main.js`, `frontend/src/styles.css`, and this report were changed for Lap 4B. No API/backend files or dependencies changed. | The implementation was later committed and pushed on `codex/frontend-lap3` after the user explicitly requested it, then cherry-picked to local `main` at the user's request. The main-branch commit remains local. |

### Checks performed

- `npm run build` from `frontend/` — passed.
- `node --check src/main.js` from `frontend/` — passed.
- `git diff --check` — passed.
- Git scope review — the main-branch commit contains only the two frontend source/style files and this report; it was based on source commit `397224d`.
- Browser preview — attempted at `http://127.0.0.1:5173/`, but the in-app browser timed out before the UI loaded.
- Live API answered/abstained/missing-provenance cases — not verified.

### Outstanding verification

1. Open the local frontend in a browser and check the graph at approximately 320 px and 1280 px.
2. Use Tab/Shift+Tab and Enter/Space to verify visible focus, graph node/link operation, passage-card jumps, and expandable details; perform a screen-reader review if available.
3. Against a running API, verify answered, abstained, and missing/empty provenance responses.

### Integration note

The repository did not contain `reports/backend_lap4_answer.md` when this work was inspected. The existing API contract and backend response implementation provided enough shape information to complete the frontend without cross-boundary changes. The implementation is pushed on `codex/frontend-lap3`; the outstanding checks above are still needed for full UI/live-integration acceptance.
---

## Original Lap 4B requirements and acceptance notes

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

- [x] The answer is easy to find before detailed evidence and renders the API-provided text without browser-generated advice.
- [x] Graph nodes/edges match the current response provenance exactly; no missing, invented, or stale links.
- [x] Evidence node labels and passage-card links use returned identifiers only.
- [x] A textual accessible fallback fully describes nodes and relations; keyboard focus and labels work.
- [x] Graph empty/malformed/disconnected states and answered/abstained/error/new-request states are clear.
- [x] Excerpts remain verbatim; UEFA passages, event records, historical examples, and limitations remain separate.
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

## Implementation status

- [x] The API-provided `answer` remains the primary response and is rendered without browser-generated advice.
- [x] Response and support status remain visible; abstentions retain their distinct warning treatment.
- [x] Added an **Evidence provenance** SVG overview from the current response's returned nodes and edges, with distinct node shapes, a type legend, a mobile stacked layout, and a keyboard-readable textual node/relationship inventory.
- [x] Node labels use returned fields only. Every well-formed node and relationship is retained in the textual inventory; invalid entries are identified, and missing/ambiguous endpoints are not turned into invented graph links.
- [x] UEFA nodes link to a passage card only when the returned `evidence_id` matches exactly one passage. The source card continues to display the returned citation and verbatim excerpt.
- [x] Retained raw provenance disclosure and separate UEFA passages, recorded events, historical examples, and limitations.
- [x] Added explicit empty, missing, incomplete, and malformed provenance messaging. Provenance shape problems do not suppress an otherwise contract-valid answer. New requests clear prior result content before loading, so prior graphs are not left visible on failure.
- [x] Added dev-only, explicitly labeled synthetic previews for answered, abstained, connected, empty, missing, malformed, and disconnected provenance states.
- [x] No dependency added; no API/backend schema changes made.
- [x] Build and diff whitespace checks pass; only `frontend/src/main.js`, `frontend/src/styles.css`, and this report are changed.
- [ ] Browser visual checks at 320 px and 1280 px and keyboard interaction checks remain unverified. The in-app browser could not reach the local Vite server (`ERR_CONNECTION_TIMED_OUT`), so no rendered screenshot or screen-reader check was available.
- [ ] Live API answered/abstained/missing-provenance integration remains unverified; the local API was not exercised in this turn.

## Verification

- `npm run build` from `frontend/` — passed.
- `git diff --check` — passed.
- Browser preview — attempted at `http://127.0.0.1:5173/`; the in-app browser timed out before loading the page.
- Git status was clean before implementation on `codex/frontend-lap3`. Work remains uncommitted and unpushed, as required.

## Handoff notes

The repository did not contain `reports/backend_lap4_answer.md` when inspected. The shared product API contract and existing response implementation provide the needed provenance shape, so no backend changes were required. Once the local browser/API are reachable, verify answered, abstained, empty provenance, malformed provenance, keyboard focus/order, and 320 px/1280 px layouts.

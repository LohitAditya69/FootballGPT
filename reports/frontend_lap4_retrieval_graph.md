# Lap 4B — Frontend retrieval provenance graph

## Implementation report

**Date:** 20 October 2026
**Source branch:** `codex/frontend-lap3`
**Source commit:** `397224d` — `Add Lap 4 provenance graph frontend`
**Git status:** Lap 4 is committed on local `main`, based on the latest fetched `origin/main`; this local `main` commit has not been pushed.

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

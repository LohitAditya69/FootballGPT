# Lap 4B — Frontend retrieval provenance graph

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

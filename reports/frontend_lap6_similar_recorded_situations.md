# Lap 6B — Similar recorded match situations

## Implemented

- Kept the question-only request flow. The frontend still sends only the question and adds no Match ID or Trigger Event ID controls.
- Renamed the returned history section to **Similar recorded match situations** and renders each returned `historical_examples` item as a distinct StatsBomb card. Cards display only returned values for team/opponent, label, match ID, timestamp, event type, play pattern, location, formation, score, similarity score, and source split; absent values are omitted. Location is textual data only; no pitch or player-position graphic is inferred.
- Made the distinction explicit: examples are not events from the user's match, UEFA guidance, or proof of coaching effectiveness, and do not establish unseen movement or video context.
- A null `event_evidence` now produces a compact note that an exact event was not supplied, rather than an empty event-window panel. Empty historical results state: “No comparable recorded situations were found for this question.”
- Provenance remains based on the API's returned nodes and edges. Its explainer clarifies that similarity links are retrieval relationships, not proof that a tactic works.
- Existing request-start behavior clears the previous response, graph, and examples before loading. Added a dev-only, explicitly synthetic “No similar situations” preview that retains an answer while removing event/history nodes and edges consistently.

## Verification and limits

- `npm run build` — passed.
- `git diff --check` — passed.
- The Lap 6A backend handoff (`reports/backend_lap6_question_only_match_retrieval.md`) was not present, so question-only retrieval integration could not be tested. The frontend uses the existing `historical_examples` response field and unchanged API v1 contract.
- Browser layout checks, keyboard/screen-reader review, and live answered/abstained/service-error integration checks remain outstanding. Dev previews are synthetic and are not API evidence.
- Changes are limited to `frontend/src/main.js`, `frontend/src/styles.css`, and this report. No backend, contract, branch, commit, or push changes were made.

# Lap 5B — Frontend implementation report

## Delivered

- Added a hash-routed login → question → answer experience in the existing Vite app. The login screen has email/password validation and an accessible show/hide control. No auth provider or Lap 5A backend brief was present, so sign-in is explicitly unavailable; credentials are not sent or stored, and the password field is cleared after an unavailable sign-in attempt. A clearly labeled unauthenticated continuation keeps the existing question API usable.
- Removed the Match ID and Trigger event ID inputs. Requests now contain only `{ "question": "…" }`; the existing API base URL remains under collapsed developer settings.
- Added a dedicated answer route. The returned answer and support state remain first, followed by the existing exact passages/citations, separate event and historical channels, returned provenance visualization/text fallback, and limitations. The submitted question and response are held in session-scoped browser state, not the URL. Missing response state shows an expired-result message and a back link.
- Added question preservation, request progress, inline recoverable errors with retry, and page-heading focus on route changes. Starting a new request clears the previous response; failed requests do not expose old evidence.
- Extended the forest/cream/lime match-day visual system for the login, question, and answer views, with compact responsive layouts and reduced-motion support. No graph nodes or edges are inferred or added.

## Verification and handoff

- `npm run build` — passed (Vite production build).
- Source review confirms the request body is question-only and the match/event controls are absent from the product UI.
- Browser visual checks at 320 px, 768 px, and 1280 px could not be completed: the Windows browser automation helper stopped before navigation because it could not identify the current browser URL confidently. No browser interaction was performed. Responsive breakpoints and styles are present but still need visual confirmation; screen-reader testing also remains outstanding.
- No live backend/auth integration test was possible. API v1’s existing question-only request is the assumption. Real sign-in needs an approved provider/backend contract, secure cookie/session behavior, and any required CORS policy before it can be enabled.
- Changes are limited to `frontend/index.html`, `frontend/src/main.js`, `frontend/src/styles.css`, and this report. No backend, shared API contract, README, branch, or Git history changes were made. Nothing was committed or pushed.

## Remaining integration checks

After an approved auth integration and reachable backend are available, verify one supported answer, one abstention, recoverable API errors, missing provenance, question-only request handling, and the login session lifecycle. Complete visual checks at approximately 320/768/1280 px and keyboard/screen-reader review.

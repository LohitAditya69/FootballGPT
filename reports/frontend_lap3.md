# Lap 3 — Frontend work brief and prompt

## Goal

Build the FootballGPT frontend against the shared, read-only [product API contract v1](product_api_contract_v1.md). In the repository, this brief's exact path is `reports/frontend_lap3.md`; keep it there so the relative contract link resolves. If starting from a downloaded copy, copy its reviewed contents into that exact repository path before implementation. The API contract's exact path is `reports/product_api_contract_v1.md`.

## Strict file and change boundary

The frontend worker may read the repository but may edit only these exact path patterns:

- New or existing files below `frontend/` (including its own package manifest, lockfile, source, and assets).
- `reports/frontend_lap3.md` only, for this brief and its Lap 3 checklist.

Treat `reports/product_api_contract_v1.md` as read-only. Do not edit backend files, retrieval implementation, ranking configuration, source data, evidence chunks, evaluation questions, qrels, generated review labels, `README.md`, or other project files. Do not delete, rename, reformat, or regenerate existing files. If implementation needs any path outside the allowlist, stop and ask the user for approval before changing it. Report the exact path and why it is needed.

Do not tune retrieval against v1/v2 held-out questions. Do not claim coach approval or imply that event data proves unseen video context. Do not push. Work in a dedicated worktree and frontend branch separate from the backend task so file changes and commits cannot collide. Do not pull, merge, or rebase into the shared checkout. Start the worktree from the current local project HEAD; if another base is required, report the needed commit and stop for direction. A local commit may include only allowlisted frontend files and this brief.

## Part 1 — Interface foundation checklist

- [ ] Inspect the current project and choose a frontend stack contained entirely under `frontend/`; do not add root-level tooling or change existing project configuration.
- [ ] Build a question-entry and result-view shell using API-contract-shaped sample data.
- [ ] Show loading, initial/empty, invalid-input, service-error, malformed-response, answered, and abstention states as defined below.
- [ ] Display UEFA citations and excerpts separately from StatsBomb event records and historical examples.
- [ ] Display provenance and limitations without implying a coach recommendation or human review.
- [ ] Check the layout at 1280 px desktop width and 320 px narrow width; verify keyboard access as defined below.
- [ ] Document local startup and the API base URL configuration in this brief.
- [ ] Review the diff and ensure every changed path is within the allowlist after Part 1. Do not commit yet; Part 1 and Part 2 are delivered in one final commit.

## Part 2 — Live evidence and provenance checklist

- [ ] Connect the question form to `POST /api/v1/ask` as defined by the shared contract.
- [ ] Render clickable source/page citations and the exact returned excerpts.
- [ ] Keep tactical passages, event records, historical examples, and provenance visibly distinct.
- [ ] Render abstention and missing-source states without showing unsupported passages as evidence.
- [ ] Handle structured API errors and malformed/missing fields safely.
- [ ] Verify the response and error fixtures below against the backend when it is available. If unavailable, use deterministic local mock responses and clearly report that live integration remains unverified.
- [ ] Review the full diff for scope, update this brief, and create one local commit containing the completed Part 1 and Part 2 changes from the allowlist.

## Precise UI acceptance cases

- **Initial/empty:** Before submission, the question field is empty, no result is shown, and the submit action is disabled or gives a clear prompt. An answered response with an empty `tactical_passages` array must not be shown as supported; render the backend's `status` and `support_status` faithfully.
- **Invalid input:** A blank/whitespace-only question and a question longer than 2,000 characters are rejected before sending. Show an inline message adjacent to the field; do not send a request.
- **Loading:** After a valid submission and before the response, show a visible loading state, prevent accidental duplicate submission, and keep the question visible.
- **Answered fixture:** Render a valid `status: "answered"` response with one tactical passage, one event record, one historical example, provenance, and limitations. Keep all four evidence categories visually distinct and show the exact excerpt and citation returned by the API.
- **Abstention fixture:** Render `status: "abstained"`, `answer_mode: "abstain"`, an explanatory answer, and an empty `tactical_passages` list. Do not display stale passages from a previous request as evidence for this response.
- **Service error fixture:** Handle HTTP 500 with the contract's `footballgpt-error-v1` body and show a generic, recoverable error without raw exception text. Also handle a network failure where no HTTP response is received.
- **Malformed-response fixture:** Handle HTTP 200 with a missing or incorrectly typed required field. Show a recoverable response error and do not present malformed content as evidence.
- **Keyboard:** The question field, submit button, citation links, and any expandable provenance controls are reachable and operable with Tab/Shift+Tab and Enter/Space as appropriate; focus is visible; form controls have programmatic labels; validation and request errors are announced through an accessible live region.
- **Responsive layout:** At 320 px and 1280 px viewport widths, content stays within the viewport, evidence sections remain distinguishable, and citations remain usable without horizontal page scrolling.

## API base URL and verification

Use `VITE_API_BASE_URL` as the configurable origin and append `/api/v1/ask`. For local development, default to `http://localhost:8000` only if the backend confirms that port; otherwise require the variable to be set and document the actual backend URL. The API contract specifies the route and schema, but does not define the server's local port.

If the backend is unavailable, use local fixtures for the answered, abstained, HTTP 500, network-failure, and malformed-response cases. Record that these verify frontend rendering and error handling only; they do not verify live contract integration. Once available, run the same cases against the service.

## Copy-ready frontend prompt

> Work on FootballGPT Lap 3: implement the frontend against `reports/product_api_contract_v1.md` as a read-only contract. The brief must be stored at `reports/frontend_lap3.md`; if starting from a downloaded copy, copy the reviewed contents there. First inspect the repository and Git status. Create a dedicated worktree and frontend branch from the current local project HEAD. Do not pull, merge, or rebase into the shared checkout; if another base is needed, stop and report the required commit.
>
> **Edit only** files below `frontend/` and `reports/frontend_lap3.md`. Do not edit the shared API contract, backend files, retrieval code/configuration, data/evidence/benchmark files, generated review labels, README, or other paths. Do not delete or reformat unrelated files. If you need a change outside this allowlist, stop and ask me before editing it.
>
> Implement Part 1 and Part 2 from this brief, including every precise UI acceptance case. Keep citations, StatsBomb events, historical examples, provenance, limitations, and abstentions distinct. Do not imply that a passage is relevant solely because the backend returned it, do not claim human coach review, and do not infer unseen video context. Do not tune on v1/v2 held-out questions or push changes. If the backend is unavailable, verify each UI state with deterministic fixtures and report live integration as unverified. Run focused checks required by this task, inspect the final diff for allowlist compliance, update only this brief, and make one local commit after both parts are complete, containing only allowlisted changes. Report changed files, verification, commit, and any blocked/out-of-scope request.

## Lap 3 status

- [ ] Part 1 interface foundation complete.
- [ ] Part 2 live evidence and provenance complete.
- [ ] Integration against the approved API contract complete.
- [ ] One scope-reviewed local commit recorded after both parts are complete.

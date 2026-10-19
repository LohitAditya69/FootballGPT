# Reliability and product build workflow

## Working rules

- Keep the existing v1 and v2 held-out questions separate from development data. Do not tune retrieval, prompts, or thresholds against held-out results.
- Treat the frozen UEFA reports and recorded StatsBomb events as the factual reference. A source audit checks whether claims and citations match those records; it does not claim live coach approval or unseen video context.
- Build backend and frontend against one written API contract. Work on each side in two parts, with an integration checkpoint between the parts.
- At the start of each lap, check the Git branch and working tree and pull incoming changes when the remote is reachable. At the end, update this file and the relevant README/status docs, run the lap's verification, and commit that lap before starting the next.
- Never overwrite or discard another person's changes. If a pull conflicts or the working tree is not clean, stop and reconcile before editing.

## Lap 1 — Reliability review

### 1A. Audit benchmark and labels

- [ ] Confirm all v1/v2 questions map to existing pages in the frozen report corpus or are explicitly marked not covered.
- [ ] Check question, split, report ID, page number, and report hash consistency.
- [ ] Review the 42 development questions for duplicate intent, overly report-specific wording, and target-page omissions.
- [ ] Preserve v2 held-out labels and results unchanged; record any discovered annotation issue as a new benchmark version rather than silently editing v2.
- [ ] Reconfirm historical retrieval excludes each query match and state clearly that historical relevance has no judged qrels.

### 1B. Audit generated evidence and risks

- [ ] For each of the 12 generated briefs, verify every quoted UEFA passage against its cited page.
- [ ] Verify every match statement against the corresponding recorded StatsBomb event window.
- [ ] Confirm the two not-covered questions abstain and do not present retrieved passages as support.
- [ ] Check that the provenance JSON links each displayed citation to its retrieved chunk and keeps event evidence distinct from tactical principles.
- [ ] Keep missing-video limitations explicit: event data does not prove off-ball runs, team shape, or nearby options.
- [ ] Update the reliability findings, unresolved issues, README, and completion status before product work begins.

### Lap 1 exit criteria

- [ ] Reliability report lists reviewed artifacts, checks performed, findings, and unresolved limitations.
- [ ] No held-out labels or scores were changed or used for tuning.
- [ ] The API fields needed to expose citations, event evidence, abstention, and provenance are agreed for Lap 2.

## Lap 2 — Backend and frontend, coordinated side by side

### 2A. Agree the interface before parallel implementation

- [ ] Define request fields: question and any supported match/event context.
- [ ] Define response fields: answer/evidence brief, cited report passages, recorded event evidence, provenance, abstention status, and structured errors.
- [ ] Define citation identity and page numbering once so backend and frontend use the same form.
- [ ] Save the contract in Markdown or an API schema and review it before either side depends on it.

### 2B. Backend — Part 1: service foundation

- [ ] Add the application entry point, configuration, health endpoint, and request validation.
- [ ] Wire the frozen retrieval pipeline to the service using the selected local index and configured sources.
- [ ] Return structured response data matching the agreed contract; keep tactical text separate from StatsBomb facts.
- [ ] Return an explicit abstention when no supported evidence is available.
- [ ] Add focused backend checks for malformed input, missing evidence, citations, and match-exclusion behavior.

### 2C. Frontend — Part 1: interface foundation

- [ ] Add the question-entry and result-view shell using the agreed contract and sample responses.
- [ ] Show loading, empty, error, and abstention states.
- [ ] Make report citations and recorded match evidence visually distinct.
- [ ] Check the layout at desktop and narrow viewport sizes.

### 2D. Integration checkpoint 1

- [ ] Run the backend locally and confirm its response matches the contract.
- [ ] Connect the frontend to the local service and verify one supported question and one abstention.
- [ ] Resolve contract mismatches before starting the second parts.
- [ ] Update docs and commit the completed first parts as a checkpoint.

### 2E. Backend — Part 2: reliability and provenance

- [ ] Validate citation IDs and page references against the fixed report index before returning them.
- [ ] Preserve source excerpts and provenance links in the response.
- [ ] Enforce the same-match exclusion for historical examples.
- [ ] Record useful errors and request IDs without logging unnecessary sensitive input.
- [ ] Document any fallback behavior and source coverage limits.

### 2F. Frontend — Part 2: live evidence and provenance

- [ ] Connect the question form to the live backend response.
- [ ] Render clickable report/page citations and the exact supporting excerpts.
- [ ] Render StatsBomb event records separately from UEFA tactical evidence.
- [ ] Expose the provenance path in a readable expandable view.
- [ ] Display abstention and coverage limits without implying unsupported recommendations.

### 2G. Integration checkpoint 2 and delivery review

- [ ] Run an end-to-end flow from question entry through API response to cited evidence display.
- [ ] Check covered and not-covered cases, service errors, and missing/invalid citation behavior.
- [ ] Confirm no held-out question was used to tune the live system.
- [ ] Update README, this workflow, and project status with completed items and remaining risks.
- [ ] Commit the integrated result and report the branch/commit state.

## Git checkpoint record

| Checkpoint | Pull status | Commit | Notes |
|---|---|---|---|
| Workflow plan | Pull attempted on 2026-10-19; blocked because `github.com` could not be resolved in the current environment | Pending | Working tree was clean before the pull attempt; retry before Lap 1 work when network access is available. |

## Current status

- [x] Workflow and lap checklist written.
- [ ] Lap 1 reliability review.
- [ ] Lap 2 interface contract and backend/frontend build.
- [ ] Git pull and commit checkpoint after the plan; pull is currently blocked by DNS/network availability.

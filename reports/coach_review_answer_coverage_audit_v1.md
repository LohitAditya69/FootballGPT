# Coach-reviewed retrieval and answer coverage audit

## Purpose and scope

This audit joins the coach-reviewed page judgments in `retrieval_workbook_review_qrels_v1.csv` to the existing API top-3 results in `retrieval_backend_workbook_evaluation_v1.csv`. It covers 42 development questions and 1,071 reviewed question-page pairs. The workbook itself remains outside the repository and unchanged.

The API evaluation reports 42 answers and 0 abstentions. Against the reviewed labels, 22 questions have at least one grade-2 page in the API top three, 13 have a grade-2 page elsewhere in the reviewed candidate pool but not in the API top three, and 7 have no grade-2 page in the reviewed candidate pool. These counts describe this retrieval-generated candidate pool; the 7 are not proof that the fixed report corpus contains no relevant page. Likewise, “answered” means the API returned an answer; it does not establish adequate support or answer quality.

## Grade-2 candidate page not in API top three (13)

| Question | Topic |
|---|---|
| DEV07 | Centre-back defending large spaces in a high line |
| DEV09 | Third centre-back enabling wing-backs to press wide |
| DEV11 | Defensive body orientation, footwork, and 1v1 practice |
| DEV16 | Strong forward movement against a high press |
| DEV18 | Asymmetric pressing and high regains |
| DEV21 | Mid-block central protection against wide attacks |
| DEV2-01 | Shifting the block to restrict wide combinations |
| DEV2-02 | Midfield cover when a teammate steps out |
| DEV2-05 | Distances and cover when a defender jumps to press |
| DEV2-11 | Repeated runs behind in the final third |
| DEV2-13 | Purpose and effectiveness of counter-pressure |
| DEV2-14 | Goalkeeper's first pass after a goal kick |
| DEV2-19 | Purpose of a mid-block before countering |

## No grade-2 page in the reviewed candidate pool (7)

| Question | Topic |
|---|---|
| DEV01 | Full-backs creating space under pressure in build-up |
| DEV12 | Goalkeeper claim/punch giving the defence time to reorganise |
| DEV19 | Narrow diamond press trade-offs with higher full-backs |
| DEV2-08 | Forward timing a run behind from the middle third |
| DEV2-10 | Centre-back contribution in first-phase build-up |
| DEV2-12 | Mid-block denying central progression while creating regain chances |
| DEV2-17 | Judging whether counter-pressure recovers the ball effectively |

## Interpretation and next action

This split identifies two different retrieval tasks. For the 13 missed top-three cases, inspect full ranked results and query-to-page matching to locate ranking and retrieval coverage failures. For the 7 without a direct reviewed page, search the five fixed reports beyond the existing candidate pool and record any newly found page before concluding that the corpus does not support the question.

The answer composer also needs a separate audit: a retrieved grade-2 page does not guarantee the system selects the right passage, explains it adequately, or cites it correctly. Review answer text against the cited source for all 42 questions, including the 0-abstention cases, then improve broad question-type coverage using validated evidence. Keep the existing abstention safeguards until that evidence and answer review is complete.

The workbook evaluates page relevance, not answer quality. The independent human coach judgments are genuine, but candidate-pool coverage is not exhaustive. Do not treat this audit as a complete measure of corpus recall or a causal diagnosis of any single backend component.


## Follow-up local answer-path change

After reviewing the live examples, the API was changed to inspect up to
`max(4 × top_k, 20)` ranked candidates before selecting up to three supported
sentences. It no longer truncates to three pages before checking sentence
relevance or collapses all chunks from one page into a single candidate first.
The generic sentence matcher now requires multiple non-generic topic terms,
a matching player/position role when the question names one, and a compatible
action where it can identify one. Excerpts exclude all-caps headings and can
include several query-matched source sentences. These are local changes and
have not yet been evaluated against the question set; the counts above describe
the earlier top-three diagnostic snapshot.

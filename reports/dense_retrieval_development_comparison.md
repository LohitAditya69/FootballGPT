# Dense retrieval development comparison

Scope: 42 development questions only. No v1 or v2 held-out questions were read for selection. The current development qrels are AI-assisted, incomplete candidate-page labels; these metrics are provisional and are not human relevance judgments.

Model: `sentence-transformers/all-MiniLM-L6-v2`, cached model revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, mean-pooled 384-dimensional embeddings with L2 normalization. Document chunks and queries use the same model. Similarity is cosine similarity.
Runtime used: Python 3.14.6, sentence-transformers 6.1.0, PyTorch 2.14.1, Transformers 5.20.1, NumPy 2.5.4. Dependencies are pinned in `requirements-embedding.txt`.

BM25 fixed uses `k1=1.5`, `b=0.75`. Hybrid scores min-max normalize the top-20 chunk results from BM25 and dense retrieval per query, fuse the union of evidence IDs, then rank pages by their best chunk score. The current BM25+G row uses the unchanged `backend/retrieval/ranking_config.json` settings.

P@5 counts relevant pages in the top five divided by five; Recall@5 counts retrieved labeled relevant pages divided by the number of labeled relevant pages; MRR uses the first relevant page.

| Method | P@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| Fixed BM25 | 0.171 | 0.619 | 0.612 |
| Dense MiniLM | 0.081 | 0.321 | 0.259 |
| BM25 + 25% dense | 0.176 | 0.643 | 0.617 |
| BM25 + 50% dense | 0.157 | 0.571 | 0.588 |
| BM25 + 75% dense | 0.110 | 0.429 | 0.337 |
| Current BM25 + graph baseline | 0.181 | 0.655 | 0.632 |

Per-question outcomes versus fixed BM25 (better / tied / worse):

| Method | P@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| Dense MiniLM | 2 / 22 / 18 | 2 / 22 / 18 | 3 / 19 / 20 |
| BM25 + 25% dense | 1 / 41 / 0 | 1 / 41 / 0 | 2 / 38 / 2 |
| BM25 + 50% dense | 1 / 37 / 4 | 1 / 37 / 4 | 3 / 32 / 7 |
| BM25 + 75% dense | 2 / 27 / 13 | 2 / 27 / 13 | 3 / 21 / 18 |
| Current BM25 + graph baseline | 2 / 40 / 0 | 2 / 40 / 0 | 4 / 37 / 1 |

Highest-scoring hybrid by the predeclared development priority MRR, then Recall@5, then P@5: `Hybrid_25D`. This is a development selection only, not a production configuration change.

## Limitations and decision

- Qrels are incomplete and AI-assisted; the human review packet must be completed before treating small metric differences as meaningful.
- Results come from one 42-question development set and one model revision; no significance or broad generalization claim is made.
- Keep the current BM25 and graph configuration unchanged until reviewed qrels are available and an improvement is consistent across relevant metrics and questions.
- Per-question results are in `dense_retrieval_development_per_question.csv`.

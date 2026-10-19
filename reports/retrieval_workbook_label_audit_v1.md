# Workbook label spot audit

Date: 2026-10-19. This is an assistant evidence audit of two direct-support
labels, not a human or coach review. The source workbook and its exported
qrels remain unchanged.

## DEV07: high-line centre-back abilities

**Workbook label:** grade 2, UEFA Europa Conference League 2024/25, page 30.

**Evidence check:** the page discusses Chelsea's high press leaving teammates
1v1 in the back line, then explicitly says young centre-backs need athleticism
and the ability to defend in central and wide areas. That supports the
question about abilities needed to defend large spaces in a high line.

**Audit finding:** the grade-2 label is defensible, but the workbook's selected
supporting quote focuses on the full-backs and does not include the adjacent
centre-back sentence that makes the strongest case. If the workbook is reviewed
later, replace or extend the quote with the centre-back sentence and its page
context. The original workbook remains untouched.

**Backend finding:** current API top three does not include this page.

## DEV18: asymmetric pressing direction and high regains

**Workbook label:** grade 2, UEFA Champions League 2024/25, page 30.

**Evidence check:** the page describes Liverpool directing the goalkeeper's
distribution to one flank, applying pressure there, and using the trap to regain
the ball. This directly supports steering play toward one side and winning the
ball high.

**Audit finding:** the grade-2 label is supported by the page. The workbook's
selected passage is a partial excerpt; the surrounding paragraph and page
heading give the clearest explanation of the one-sided press and regain.

**Backend finding:** current API top three does not include this page. Its BM25
chunk rank is 12 before fusion, while the graph channel gives broad equal scores
to many unrelated chunks. Increasing candidate depth changes the page's rank
but does not move it into the API top three in this sweep. This is a retrieval
ranking issue, not evidence that the qrel should be downgraded.

## Limits and next review action

These two checks support the labels but do not validate the remaining workbook
rows. The two scripted workbook reviewer profiles remain provisional labels.
The next label-quality step is a human/coach pass over the review packet,
including confirming the supporting excerpt and adding any relevant pages the
retrievers missed. Do not treat this spot audit as independent human review.

"""Conservative, citation-verifiable composition from validated UEFA excerpts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.api.schemas import EventEvidence, HistoricalExample, TacticalPassage


GENERIC_ABSTENTION_NOTICE = (
    "No adequately supported tactical passage was retrieved from the frozen UEFA reference set; "
    "abstain pending source review."
)

_CITATION_RE = re.compile(r"\((uefa-[a-z0-9-]+\s+p\.\d+)\)")
_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.S)
_WORD_RE = re.compile(r"[a-z]{3,}")
_STOP_WORDS = {
    "after", "about", "against", "also", "and", "are", "ball", "can", "could", "does",
    "for", "from", "how", "into", "its", "our", "should", "team", "the", "their",
    "them", "then", "they", "this", "through", "when", "what", "with", "would",
}


@dataclass(frozen=True)
class GroundedClaim:
    """A deterministic coaching claim plus its exact textual support and citation."""

    text: str
    citation: str
    evidence: tuple[str, ...]


_OWN_HALF_FORWARD = re.compile(
    r"\bwhen the ball was regained\s+in (?:their|the) own half\b[^.!?]*\b"
    r"(?:play forward early|space beyond the back line|highest attacking player)\b[^.!?]*[.!?]",
    re.I | re.S,
)
_OWN_HALF_DIRECT = re.compile(
    r"\bafter winning the ball\s+in (?:their|the) own half\b[^.!?]*"
    r"\b(?:directly deep or diagonally|direct or diagonal)\b[^.!?]*[.!?]",
    re.I | re.S,
)
_MID_BLOCK_PROTECTION = re.compile(
    r"\bthere was also a different\s+approach when the ball was regained in the mid-block\b"
    r"[^.!?]*\b(?:possession|ball protection)\b[^.!?]*[.!?]",
    re.I | re.S,
)


def clean_text_artifacts(text: str) -> str:
    """Normalize whitespace only; source wording and encoding remain evidence, not prose to rewrite."""
    return re.sub(r"\s+", " ", text).strip()


def clean_coaching_clause(text: str) -> str:
    """Compatibility helper that only normalizes whitespace, never edits evidence wording."""
    return clean_text_artifacts(text)


def is_clean_tactical_sentence(sentence: str) -> bool:
    """Reject obviously noisy, tabular, or incomplete source lines without rewriting them."""
    visible = sentence.lstrip("\"'“‘([{ ")
    return (
        35 <= len(sentence) <= 500
        and bool(visible)
        and visible[0].isupper()
        and sentence.rstrip().endswith((".", "!", "?", "\"", "'", "”", "’"))
        and "\ufffd" not in sentence
        and not re.search(r"\d", sentence)
        and not re.search(r"\b(?:table|contents|roll of honour|session organisation|drill)\b", sentence, re.I)
    )


def _source_sentences(text: str) -> list[str]:
    # Keep line breaks and source characters intact so API excerpts remain literal substrings.
    return [m.group(0).strip() for m in _SENTENCE_RE.finditer(text) if m.group(0).strip()]


def _is_regain_question(question: str) -> bool:
    q = question.casefold()
    return bool(re.search(r"\b(?:winning|win|regain|regaining|recovering|recover)\b.{0,35}\b(?:ball|possession)\b", q))


def _directly_responsive(sentence: str, question: str) -> bool:
    """Require an explicit topic/action link; retrieval rank is deliberately not used."""
    s = sentence.casefold()
    if not is_clean_tactical_sentence(sentence):
        return False
    if _is_regain_question(question):
        regain_anchor = bool(re.search(
            r"\b(?:after|when|once|following)\s+(?:winning|regaining|recovering)\s+(?:the\s+)?(?:ball|possession)\b|"
            r"\bwhen the ball was regained\b|"
            r"\b(?:after|when|following)\s+(?:a\s+)?(?:high\s+)?regain\b",
            s,
        ))
        response_action = bool(re.search(
            r"\b(?:pass|play|attack|forward|transition|counter|move|look|carry|progress|space|"
            r"possession|protect|secure|retain)\w*\b", s
        ))
        return regain_anchor and response_action

    q_tokens = {w for w in _WORD_RE.findall(question.casefold()) if w not in _STOP_WORDS}
    s_tokens = set(_WORD_RE.findall(s))
    overlap = q_tokens & s_tokens
    # Short queries can be supported by one uncommon shared term; otherwise require two.
    return bool(overlap) and (len(overlap) >= 2 or len(q_tokens) <= 2)


def _has_polarity_conflict(sentences: list[str]) -> bool:
    for index, left in enumerate(sentences):
        left_tokens = {w for w in _WORD_RE.findall(left.casefold()) if w not in _STOP_WORDS}
        left_negated = bool(re.search(r"\b(?:not|never|no|cannot|can't|shouldn't)\b", left.casefold()))
        for right in sentences[index + 1:]:
            right_tokens = {w for w in _WORD_RE.findall(right.casefold()) if w not in _STOP_WORDS}
            right_negated = bool(re.search(r"\b(?:not|never|no|cannot|can't|shouldn't)\b", right.casefold()))
            if len(left_tokens & right_tokens) >= 3 and left_negated != right_negated:
                return True
    return False


def _passage_source_text(
    passage: TacticalPassage,
    fixed_chunks: dict[str, dict[str, Any]] | None,
) -> str:
    """Use a fixed-index source chunk only when its identity matches the validated passage."""
    chunk = fixed_chunks.get(passage.evidence_id) if fixed_chunks else None
    if chunk and (
        str(chunk.get("source_id")) == passage.source_id
        and str(chunk.get("citation")) == passage.citation
        and int(chunk.get("page", -1)) == int(passage.page)
    ):
        return str(chunk.get("text", ""))
    return passage.excerpt


def _regain_evidence(passage: TacticalPassage, fixed_chunks: dict[str, dict[str, Any]] | None) -> tuple[str, tuple[str, ...]]:
    """Find the recognized own-half / mid-block statements without rewriting their text."""
    source = _passage_source_text(passage, fixed_chunks)
    sentences = _source_sentences(source)
    support: list[str] = []
    for sentence in sentences:
        if (_OWN_HALF_FORWARD.search(sentence) or _OWN_HALF_DIRECT.search(sentence)
                or _MID_BLOCK_PROTECTION.search(sentence)):
            support.append(sentence)
    if not support:
        return "", ()

    # Return the exact contiguous source slice spanning the mapped sentences so
    # the evidence shown to the user still contains every sentence used.
    positions: list[tuple[int, int]] = []
    cursor = 0
    for sentence in support:
        pos = source.find(sentence, cursor)
        if pos < 0:
            return "", ()
        positions.append((pos, pos + len(sentence)))
        cursor = pos + len(sentence)
    excerpt = source[min(a for a, _ in positions):max(b for _, b in positions)]
    return excerpt, tuple(support)


def extract_grounded_claims(
    question: str,
    passages: list[TacticalPassage],
    fixed_chunks: dict[str, dict[str, Any]] | None = None,
) -> list[GroundedClaim]:
    """Map only recognized regain observations to bounded coaching-language templates."""
    if not _is_regain_question(question):
        return []
    claims: list[GroundedClaim] = []
    for passage in passages:
        _, evidence = _regain_evidence(passage, fixed_chunks)
        own_forward = next((s for s in evidence if _OWN_HALF_FORWARD.search(s)), None)
        own_direct = next((s for s in evidence if _OWN_HALF_DIRECT.search(s)), None)
        mid_block = next((s for s in evidence if _MID_BLOCK_PROTECTION.search(s)), None)

        if own_forward or own_direct:
            support = tuple(s for s in (own_forward, own_direct) if s)
            if own_forward and own_direct:
                text = (
                    "After a regain in your own half, look to play forward early with a direct or diagonal "
                    "pass to an advanced teammate or into space beyond the back line."
                )
            elif own_forward:
                text = (
                    "After a regain in your own half, look to play forward early toward an advanced teammate "
                    "or into space beyond the back line."
                )
            else:
                text = (
                    "After winning the ball in your own half, look for a direct or diagonal first pass to an "
                    "advanced player or into space behind the back line."
                )
            claims.append(GroundedClaim(text, passage.citation, support))
        if mid_block:
            claims.append(GroundedClaim(
                "If possession is regained in a mid-block, prioritize keeping possession and protecting the ball.",
                passage.citation,
                (mid_block,),
            ))
    return claims


def select_direct_passages(
    passages: list[TacticalPassage],
    question: str,
    fixed_chunks: dict[str, dict[str, Any]] | None = None,
) -> list[TacticalPassage]:
    """Keep only a single passage with an explicit, clean response to the question."""
    if _is_regain_question(question):
        eligible: list[tuple[int, TacticalPassage, str]] = []
        question_responses: list[str] = []
        for passage in passages:
            source_text = _passage_source_text(passage, fixed_chunks)
            source_sentences = _source_sentences(source_text)
            question_responses.extend(
                sentence for sentence in source_sentences
                if _directly_responsive(sentence, question)
            )
            excerpt, evidence = _regain_evidence(passage, fixed_chunks)
            if excerpt and evidence:
                own_count = int(any(_OWN_HALF_FORWARD.search(s) or _OWN_HALF_DIRECT.search(s) for s in evidence))
                mid_count = int(any(_MID_BLOCK_PROTECTION.search(s) for s in evidence))
                eligible.append((own_count + mid_count, passage.model_copy(update={"excerpt": excerpt}), excerpt))
        if _has_polarity_conflict(question_responses):
            return []
        if eligible:
            # Prefer one returned source passage that supports both distinct conditions.
            _, selected, _ = max(eligible, key=lambda item: (item[0], item[1].score))
            return [selected]

    responsive: list[tuple[TacticalPassage, str]] = []
    for passage in passages:
        for sentence in _source_sentences(passage.excerpt):
            if _directly_responsive(sentence, question):
                responsive.append((passage, sentence))
                break
    if not responsive:
        return []

    # If two directly responsive source sentences make the same claim with
    # opposite polarity, do not resolve the disagreement using retrieval rank.
    if _has_polarity_conflict([sentence for _, sentence in responsive]):
        return []
    passage, sentence = responsive[0]
    return [passage.model_copy(update={"excerpt": sentence})]


def extract_best_grounded_points(
    passages: list[TacticalPassage],
    fixed_chunks: dict[str, dict[str, Any]] | None,
    question: str,
) -> list[tuple[str, str]]:
    return [(claim.text, claim.citation) for claim in extract_grounded_claims(question, passages, fixed_chunks)]


def count_sentences(text: str) -> int:
    """Count sentence boundaries while treating parenthesized citations as inline material."""
    without_citations = _CITATION_RE.sub("", text.strip())
    return len([part for part in _source_sentences(without_citations) if part])


def compose_grounded_answer(
    question: str,
    tactical_passages: list[TacticalPassage],
    event_evidence: EventEvidence | None = None,
    historical_examples: list[HistoricalExample] | None = None,
    unresolved_event_context: bool = False,
    fixed_chunks: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Compose short coaching prose from recognized, directly responsive source evidence."""
    del event_evidence, historical_examples, unresolved_event_context
    claims = extract_grounded_claims(question, tactical_passages, fixed_chunks)
    if not claims:
        return GENERIC_ABSTENTION_NOTICE
    return " ".join(f"{claim.text} ({claim.citation})" for claim in claims[:2])


def _normalize_claim(text: str) -> str:
    value = clean_text_artifacts(text)
    return value.rstrip(".!? ")


def validate_grounded_answer(
    answer: str,
    passages: list[TacticalPassage],
    is_abstained: bool = False,
    question: str | None = None,
) -> tuple[bool, str]:
    """Require each answer sentence to match a deterministic claim mapped to returned source text."""
    if is_abstained:
        return (bool(answer.strip()), "Valid abstention" if answer.strip() else "Abstention answer is empty")
    if not answer.strip() or len(answer) > 2000:
        return False, "Answer is empty or exceeds the length bound"
    if not 1 <= count_sentences(answer) <= 3:
        return False, f"Answer must contain 1-3 sentences, got {count_sentences(answer)}"

    allowed_claims = {
        (claim.text, claim.citation)
        for claim in extract_grounded_claims(
            question or "How should a team respond after winning the ball?", passages
        )
    }
    # Keep the previous exact-source path verifiable for callers outside this
    # deterministic Lap 11 composer (notably the separately owned LLM adapter).
    allowed_claims.update(
        (_normalize_claim(sentence), passage.citation)
        for passage in passages
        for sentence in _source_sentences(passage.excerpt)
    )
    matches = list(_CITATION_RE.finditer(answer))
    if len(matches) != count_sentences(answer):
        return False, "Every tactical sentence must contain exactly one citation"
    previous_end = 0
    for match in matches:
        citation = match.group(1)
        if citation not in {p.citation for p in passages}:
            return False, f"Citation '{citation}' does not resolve to returned tactical passages"
        claim = answer[previous_end:match.start()].strip().lstrip(". ")
        if not claim:
            return False, "Citation must immediately follow the supported claim"
        if (_normalize_claim(claim), citation) not in {
            (_normalize_claim(text), cite) for text, cite in allowed_claims
        }:
            return False, f"Claim is not supported by a recognized source-to-claim mapping for '{citation}'"
        previous_end = match.end()
    if answer[previous_end:].strip(" ."):
        return False, "Unsupported text follows the final citation"
    return True, "Valid exact-source grounded answer"

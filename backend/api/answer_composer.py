"""Conservative, citation-verifiable composition from validated UEFA excerpts."""

from __future__ import annotations

import re
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
            r"\b(?:after|when|following)\s+(?:a\s+)?(?:high\s+)?regain\b",
            s,
        ))
        response_action = bool(re.search(
            r"\b(?:pass|play|attack|forward|transition|counter|move|look|carry|progress|space)\w*\b", s
        ))
        return regain_anchor and response_action

    q_tokens = {w for w in _WORD_RE.findall(question.casefold()) if w not in _STOP_WORDS}
    s_tokens = set(_WORD_RE.findall(s))
    overlap = q_tokens & s_tokens
    # Short queries can be supported by one uncommon shared term; otherwise require two.
    return bool(overlap) and (len(overlap) >= 2 or len(q_tokens) <= 2)


def select_direct_passages(
    passages: list[TacticalPassage],
    question: str,
    fixed_chunks: dict[str, dict[str, Any]] | None = None,
) -> list[TacticalPassage]:
    """Keep only a single passage with an explicit, clean response to the question."""
    del fixed_chunks  # Excerpts were already selected from and validated against the fixed chunk index.
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
    for index, (_, left) in enumerate(responsive):
        left_tokens = {w for w in _WORD_RE.findall(left.casefold()) if w not in _STOP_WORDS}
        left_negated = bool(re.search(r"\b(?:not|never|no|cannot|can't|shouldn't)\b", left.casefold()))
        for _, right in responsive[index + 1:]:
            right_tokens = {w for w in _WORD_RE.findall(right.casefold()) if w not in _STOP_WORDS}
            right_negated = bool(re.search(r"\b(?:not|never|no|cannot|can't|shouldn't)\b", right.casefold()))
            shared = left_tokens & right_tokens
            if len(shared) >= 3 and left_negated != right_negated:
                return []
    passage, sentence = responsive[0]
    return [passage.model_copy(update={"excerpt": sentence})]


def extract_best_grounded_points(
    passages: list[TacticalPassage],
    fixed_chunks: dict[str, dict[str, Any]] | None,
    question: str,
) -> list[tuple[str, str]]:
    selected = select_direct_passages(passages, question, fixed_chunks)
    if not selected:
        return []
    return [(selected[0].excerpt, selected[0].citation)]


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
    """Return one exact, directly responsive UEFA sentence, or the existing abstention."""
    del event_evidence, historical_examples, unresolved_event_context
    points = extract_best_grounded_points(tactical_passages, fixed_chunks, question)
    if not points:
        return GENERIC_ABSTENTION_NOTICE
    sentence, citation = points[0]
    return f"{sentence} ({citation})"


def _normalize_claim(text: str) -> str:
    value = clean_text_artifacts(text)
    return value.rstrip(".!? ")


def validate_grounded_answer(
    answer: str,
    passages: list[TacticalPassage],
    is_abstained: bool = False,
) -> tuple[bool, str]:
    """Require every answered sentence to be an exact sentence from its cited response passage."""
    if is_abstained:
        return (bool(answer.strip()), "Valid abstention" if answer.strip() else "Abstention answer is empty")
    if not answer.strip() or len(answer) > 2000:
        return False, "Answer is empty or exceeds the length bound"
    if not 1 <= count_sentences(answer) <= 3:
        return False, f"Answer must contain 1-3 sentences, got {count_sentences(answer)}"

    passage_by_citation = {p.citation: p for p in passages}
    matches = list(_CITATION_RE.finditer(answer))
    if len(matches) != count_sentences(answer):
        return False, "Every tactical sentence must contain exactly one citation"
    previous_end = 0
    for match in matches:
        citation = match.group(1)
        passage = passage_by_citation.get(citation)
        if passage is None:
            return False, f"Citation '{citation}' does not resolve to returned tactical passages"
        claim = answer[previous_end:match.start()].strip().lstrip(". ")
        if not claim:
            return False, "Citation must immediately follow the supported claim"
        if _normalize_claim(claim) not in {_normalize_claim(s) for s in _source_sentences(passage.excerpt)}:
            return False, f"Claim is not entailed verbatim by cited passage '{citation}'"
        previous_end = match.end()
    if answer[previous_end:].strip(" ."):
        return False, "Unsupported text follows the final citation"
    return True, "Valid exact-source grounded answer"

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
_WORD_RE = re.compile(r"\d+v\d+|[a-z]{3,}", re.I)
_STOP_WORDS = {
    "after", "about", "against", "also", "and", "are", "ball", "can", "could", "does",
    "for", "from", "how", "into", "its", "our", "should", "team", "the", "their",
    "them", "then", "they", "this", "through", "when", "what", "with", "would",
}
_GENERIC_TACTICAL_WORDS = {
    "area", "areas", "block", "blocks", "game", "high", "line", "lines", "low", "match",
    "opponent", "opponents", "player", "players", "space", "spaces", "team", "teams",
}
_ROLE_PATTERNS = {
    "centre_back": re.compile(r"\b(?:centre|center)[- ]backs?\b", re.I),
    "full_back": re.compile(r"\bfull[- ]backs?\b", re.I),
    "wing_back": re.compile(r"\bwing[- ]backs?\b", re.I),
    "winger": re.compile(r"\bwingers?\b", re.I),
    "goalkeeper": re.compile(r"\bgoalkeepers?\b", re.I),
    "striker": re.compile(r"\bstrikers?\b", re.I),
    "forward": re.compile(r"\bforwards?\b", re.I),
    "midfielder": re.compile(r"\bmidfielders?\b", re.I),
    "defender": re.compile(r"\bdefenders?\b", re.I),
    "pivot": re.compile(r"\bpivots?\b", re.I),
}

_TERM_LEMMAS = {
    "abilities": "ability", "creating": "create", "created": "create", "creates": "create",
    "changing": "change", "changed": "change", "changes": "change", "positioning": "position",
    "positions": "position", "wingers": "winger", "spaces": "space", "defending": "defend",
    "defended": "defend", "defender": "defend", "defenders": "defend", "backs": "back",
    "fullbacks": "fullback", "big": "large",
}
_ACTION_GROUPS = {
    "create": {"create", "engineer", "generate", "manufacture", "open", "produce"},
    "change": {"adjust", "change", "drop", "advance", "move", "position", "push", "reposition", "stay", "vary"},
    "defend": {"block", "cover", "defend", "mark", "press", "protect", "recover", "shield", "stop", "tackle", "track"},
    "progress": {"advance", "attack", "carry", "counter", "forward", "pass", "play", "progress", "switch"},
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
_WINGER_1V1_POSITIONING_QUESTION = re.compile(
    r"\bwingers?\b.*\b1v1s?\b.*\bfull[- ]backs?\b|"
    r"\bfull[- ]backs?\b.*\bwingers?\b.*\b1v1s?\b",
    re.I | re.S,
)
_WINGER_1V1_POSITIONING_OUTCOME = re.compile(
    r"\bafter the break\b[^.!?]*\bremained\s+deeper for longer\b[^.!?]*"
    r"\bkept the [a-z-]+\s+wingers higher\b[^.!?]*"
    r"\bcreating\s+more space and 1v1 possibilities for their own wingers\b",
    re.I | re.S,
)
_KEEPER_PRESS_QUESTION = re.compile(
    r"\bgoalkeepers?\b(?=[^.!?]{0,100}\b(?:press|distribution|build[- ]?up|playing out)\b)",
    re.I,
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
    first_line = next((line.strip() for line in sentence.splitlines() if line.strip()), "")
    letters = re.sub(r"[^A-Za-z]", "", first_line)
    heading_only = 3 <= len(letters) <= 70 and first_line == first_line.upper() and not first_line.endswith((".", "!", "?", ":"))
    return (
        not heading_only
        and 35 <= len(sentence) <= 500
        and bool(visible)
        and visible[0].isupper()
        and sentence.rstrip().endswith((".", "!", "?", "\"", "'", "”", "’", "…"))
        and "\ufffd" not in sentence
        and not any(len(line.strip()) < 15 for line in sentence.splitlines()[:-1] if line.strip())
        and not re.search(r"\d", re.sub(r"\b\d+v\d+\b", "", sentence, flags=re.I))
        and not re.search(r"\b(?:table|contents|roll of honour|session organisation|drill)\b", sentence, re.I)
    )


def _source_sentences(text: str) -> list[str]:
    # Separate short all-caps headings from body copy so a heading cannot turn
    # into part of an apparently responsive answer sentence.
    segments: list[str] = []
    body_lines: list[str] = []
    for line in text.splitlines():
        value = line.strip()
        letters = re.sub(r"[^A-Za-z]", "", value)
        title_like = (
            len(value) <= 55
            and 2 <= len(value.split()) <= 7
            and value[:1].isupper()
            and not re.search(r"[,;.!?:]", value)
        )
        is_heading = (
            (3 <= len(letters) <= 70 and value == value.upper() and not value.endswith((".", "!", "?", ":")))
            or title_like
        )
        if is_heading:
            if body_lines:
                segments.append("\n".join(body_lines))
                body_lines = []
            segments.append(line)
        else:
            body_lines.append(line)
    if body_lines:
        segments.append("\n".join(body_lines))
    sentences: list[str] = []
    for segment in segments:
        for match in _SENTENCE_RE.finditer(segment):
            sentence = match.group(0).strip()
            if not sentence:
                continue
            # PDF extraction can replace an opening quote with U+FFFD. Remove
            # that leading marker; if corruption appears only in a trailing
            # figure caption, retain the clean clause and mark the omission.
            if sentence.startswith("\ufffd"):
                sentence = sentence[1:].lstrip()
            marker = sentence.find("\ufffd")
            if marker >= 0:
                prefix = sentence[:marker].rstrip(" ,;:–—-")
                if marker >= int(len(sentence) * 0.65) and len(prefix) >= 80:
                    sentence = prefix + "…"
            sentences.append(sentence)
    return sentences


def _normalized_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for raw in _WORD_RE.findall(text.casefold()):
        word = _TERM_LEMMAS.get(raw, raw)
        if word.endswith("s") and len(word) > 4:
            word = word[:-1]
        terms.add(word)
    return terms


def _is_regain_question(question: str) -> bool:
    q = question.casefold()
    return bool(re.search(r"\b(?:winning|win|regain|regaining|recovering|recover)\b.{0,35}\b(?:ball|possession)\b", q))


def _tactical_roles(text: str) -> set[str]:
    return {role for role, pattern in _ROLE_PATTERNS.items() if pattern.search(text)}


def _reverses_press_direction(sentence: str, question: str) -> bool:
    """Reject evidence about being pressed when the question asks how to press."""
    asks_team_to_press_opposition = bool(re.search(
        r"\b(?:team|we|players?)\b[^.!?]{0,80}\bpress(?:es|ed|ing)?\b"
        r"[^.!?]{0,80}\b(?:opposition|opponents?)\b",
        question,
        re.I,
    ))
    describes_opposition_pressing_us = bool(re.search(
        r"\b(?:opposition|opponents?)\b[^.!?]{0,100}\bpress(?:es|ed|ing)?\b"
        r"[^.!?]{0,80}\b(?:you|your team|us|our team)\b",
        sentence,
        re.I,
    ))
    return asks_team_to_press_opposition and describes_opposition_pressing_us


def _directly_responsive(sentence: str, question: str) -> bool:
    """Require an explicit topic/action link; retrieval rank is deliberately not used."""
    s = sentence.casefold()
    if not is_clean_tactical_sentence(sentence):
        return False
    if _reverses_press_direction(sentence, question):
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

    q_tokens = _normalized_terms(question) - _STOP_WORDS
    s_tokens = _normalized_terms(s) - _STOP_WORDS
    q_specific = q_tokens - _GENERIC_TACTICAL_WORDS
    specific_overlap = q_specific & s_tokens
    q_roles = _tactical_roles(question)
    sentence_roles = _tactical_roles(sentence)
    # A sentence in a validated chunk can continue the role named immediately
    # before it (for example, "It's that ability to defend big spaces"). Allow
    # that contextual continuation, while rejecting explicit mismatched roles.
    role_supported = not q_roles or bool(q_roles & sentence_roles) or not sentence_roles
    action_groups = [group for group, terms in _ACTION_GROUPS.items() if q_tokens & terms]
    action_supported = not action_groups or any(s_tokens & _ACTION_GROUPS[group] for group in action_groups)

    # Broad tactical context words (such as "high line" or "space") cannot by
    # themselves make an answer responsive. Require multiple topic anchors and,
    # where possible, a matching action from the question.
    if len(q_specific) >= 3:
        return len(specific_overlap) >= 2 and role_supported and action_supported
    overlap = q_tokens & s_tokens
    return len(overlap) >= 2 and role_supported and action_supported


def _has_polarity_conflict(sentences: list[str], question: str | None = None) -> bool:
    for index, left in enumerate(sentences):
        left_tokens = _normalized_terms(left) - _STOP_WORDS
        if question and not _is_regain_question(question):
            left_tokens -= _GENERIC_TACTICAL_WORDS
        left_negated = bool(re.search(r"\b(?:not|never|no|cannot|can't|shouldn't)\b", left.casefold()))
        for right in sentences[index + 1:]:
            right_tokens = _normalized_terms(right) - _STOP_WORDS
            if question and not _is_regain_question(question):
                right_tokens -= _GENERIC_TACTICAL_WORDS
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


def _keeper_press_support(text: str) -> tuple[bool, bool]:
    """Find both the goalkeeper pressure and supporting team movement in source text."""
    pressure = bool(
        re.search(r"closing down.{0,160}goalkeeper|goalkeeper.{0,160}closing down", text, re.I | re.S)
        and re.search(r"\bpressed\b", text, re.I)
        and re.search(r"massive intensity.{0,120}(?:time to think|think)", text, re.I | re.S)
    )
    team_support = bool(
        re.search(r"goes.{0,250}to the goalkeeper", text, re.I | re.S)
        and re.search(r"making ground behind him", text, re.I | re.S)
        and re.search(r"keep the game compact", text, re.I | re.S)
    )
    return pressure, team_support


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
    """Return bounded grounded claims, using verbatim source evidence for other topics."""
    if not _is_regain_question(question):
        if _KEEPER_PRESS_QUESTION.search(question):
            supporting: list[tuple[TacticalPassage, str, str]] = []
            for passage in passages:
                source = _passage_source_text(passage, fixed_chunks)
                pressure, team_support = _keeper_press_support(source)
                if pressure or team_support:
                    supporting.append((passage, source, "pressure" if pressure else "team"))
            pressure_item = next((item for item in supporting if item[2] == "pressure"), None)
            team_item = next((item for item in supporting if item[2] == "team"), None)
            if pressure_item and team_item:
                passage, _, _ = pressure_item
                return [GroundedClaim(
                    "Close down the goalkeeper and central defenders with high intensity so they have "
                    "little time to think; send the rest of the team forward behind the first presser "
                    "to keep the shape compact.",
                    passage.citation,
                    (pressure_item[1], team_item[1]),
                )]
        if _WINGER_1V1_POSITIONING_QUESTION.search(question):
            for passage in passages:
                source = _passage_source_text(passage, fixed_chunks)
                outcome = next(
                    (sentence for sentence in _source_sentences(source)
                     if _WINGER_1V1_POSITIONING_OUTCOME.search(sentence)),
                    None,
                )
                if outcome:
                    return [GroundedClaim(
                        "The report's example suggests keeping the full-backs deeper for longer: "
                        "this kept the opposing wingers higher and opened space for the team's own "
                        "wingers to attack 1v1.",
                        passage.citation,
                        (outcome,),
                    )]
        claims: list[GroundedClaim] = []
        seen: set[tuple[str, str]] = set()
        for passage in passages:
            for sentence in _source_sentences(passage.excerpt):
                if not _directly_responsive(sentence, question):
                    continue
                key = (passage.citation, " ".join(sentence.casefold().split()))
                if key in seen:
                    continue
                seen.add(key)
                claims.append(GroundedClaim(sentence, passage.citation, (sentence,)))
                if len(claims) == 3:
                    return claims
        return claims
    claims = []
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
    """Keep a short set of directly responsive sentences from one source chunk."""
    if _KEEPER_PRESS_QUESTION.search(question):
        pressure_passage: TacticalPassage | None = None
        team_passage: TacticalPassage | None = None
        for passage in passages:
            pressure, team_support = _keeper_press_support(_passage_source_text(passage, fixed_chunks))
            if pressure and pressure_passage is None:
                pressure_passage = passage
            if team_support and team_passage is None:
                team_passage = passage
        if pressure_passage and team_passage:
            if pressure_passage.evidence_id == team_passage.evidence_id:
                return [pressure_passage]
            return [pressure_passage, team_passage]
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
        # The validated retrieval excerpt may omit the sentence that actually
        # answers the question (for example, a centre-back sentence later in
        # the same indexed chunk). Recover it only from the matching fixed
        # source chunk, whose identity was checked above.
        source_text = _passage_source_text(passage, fixed_chunks)
        for sentence in _source_sentences(source_text):
            if _directly_responsive(sentence, question):
                responsive.append((passage, sentence))
    if not responsive:
        return []

    # If two directly responsive source sentences make the same claim with
    # opposite polarity, do not resolve the disagreement using retrieval rank.
    by_citation: dict[str, list[str]] = {}
    for passage, sentence in responsive:
        by_citation.setdefault(passage.citation, []).append(sentence)
    if any(_has_polarity_conflict(sentences, question) for sentences in by_citation.values()):
        return []
    # A lexical match is not enough to justify blending advice from separate
    # chunks. Keep a few directly responsive sentences from the highest-ranked
    # chunk so nearby sentences can explain a tactical example or complete a
    # role-specific point without importing a second passage.
    first_passage = responsive[0][0]
    selected: list[TacticalPassage] = []
    seen: set[str] = set()
    for passage, sentence in responsive:
        if passage.evidence_id != first_passage.evidence_id:
            continue
        key = " ".join(sentence.casefold().split())
        if key in seen:
            continue
        seen.add(key)
        selected.append(passage.model_copy(update={"excerpt": sentence}))
        if len(selected) == 3:
            break
    return selected


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
    """Compose a brief answer from approved claims or verbatim responsive source sentences."""
    del event_evidence, historical_examples, unresolved_event_context
    claims = extract_grounded_claims(question, tactical_passages, fixed_chunks)
    if not claims:
        return GENERIC_ABSTENTION_NOTICE
    return " ".join(f"{claim.text} ({claim.citation})" for claim in claims[:3])


def _normalize_claim(text: str) -> str:
    value = clean_text_artifacts(text)
    return value.rstrip(".!? ")


def validate_grounded_answer(
    answer: str,
    passages: list[TacticalPassage],
    is_abstained: bool = False,
    question: str | None = None,
    fixed_chunks: dict[str, dict[str, Any]] | None = None,
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
            question or "How should a team respond after winning the ball?", passages, fixed_chunks
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

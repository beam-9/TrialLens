"""Evaluation-only mechanical feedback for the existing two-pass revision call.

This module is inert unless a caller explicitly enters
revision_feedback_experiment(). It never invokes a model or changes production
prompts or validation.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import re
from typing import Any

MAX_NOTES = 6
MAX_NOTE_CHARS = 220
MAX_FEEDBACK_CHARS = 1800
_CITATION = re.compile(r"\[([^\]]+)\]")
_DIGIT = re.compile(r"\d")
_RARITY = re.compile(r"\b(rare|uncommon|frequent|frequently|rarely)\b", re.I)
_NEGATED_RARITY = re.compile(
    r"\b(?:not|never|no|cannot|can't|doesn't|does not|isn't|is not|unknown whether|not known to be)\s+(?:\w+\s+){0,2}(?:rare|uncommon|frequent|frequently|rarely)\b",
    re.I,
)
_UNCERTAIN_RARITY = re.compile(
    r"\b(?:cannot|can't|does not|doesn't|not enough information to|unknown whether|no evidence to determine)\b[^.!?]{0,120}\b(?:rare|uncommon|frequent|frequently|rarely)\b",
    re.I,
)
_SCOPED_GAP = re.compile(
    r"\b(?:not reported|not provided|not available|not established|does not establish|do not establish|cannot determine|can't determine|cannot answer|not enough information|no results? (?:are|were|have been) reported|this excerpt (?:does not|doesn't))\b",
    re.I,
)
_QUANTITATIVE_ASK = re.compile(
    r"\b(?:how much|how many|what (?:was|is) (?:the )?(?:number|amount|percentage|percent|rate|effect size|estimate|confidence interval)|"
    r"(?:give|report|show|state|include|compare) (?:the )?(?:number|amount|percentage|percent|rate|effect size|estimate|confidence interval)|"
    r"(?:by how much|what percentage|what proportion|confidence interval|effect size|numerical estimate|exact number))\b",
    re.I,
)


def _compact_note(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message[:MAX_NOTE_CHARS]}


def _source_evidence(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    records = payload.get("evidence", [])
    if not isinstance(records, list):
        return {}
    result = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("citation"), str):
            continue
        texts = [record.get("text", ""), *record.get("matched_passages", [])]
        result[record["citation"]] = {"text": "\n".join(text for text in texts if isinstance(text, str))}
    return result


def _normalized_words(text: str) -> list[str]:
    text = _CITATION.sub(" ", text)
    return re.sub(r"\W+", " ", text.lower()).split()


def _contains_28_word_copy(answer: str, sources: list[str]) -> bool:
    words = _normalized_words(answer)
    if len(words) < 28:
        return False
    source_texts = [re.sub(r"\W+", " ", text.lower()) for text in sources]
    return any(" ".join(words[index:index + 28]) in source
               for index in range(len(words) - 27) for source in source_texts)


def _is_scoped_gap(paragraph: str) -> bool:
    return bool(_SCOPED_GAP.search(paragraph))


def _rarity_notes(paragraphs: list[str], records: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    notes = []
    for paragraph in paragraphs:
        citations = _CITATION.findall(paragraph)
        if not citations:
            continue
        cited_text = " ".join(records[citation]["text"] for citation in citations if citation in records)
        citation_stripped = _CITATION.sub(" ", paragraph)
        source_frequency_terms = {term.lower() for term in _RARITY.findall(cited_text)}
        for match in _RARITY.finditer(citation_stripped):
            prefix = citation_stripped[max(0, match.start() - 45):match.start()]
            sentence_start = max(citation_stripped.rfind(".", 0, match.start()), citation_stripped.rfind("!", 0, match.start()), citation_stripped.rfind("?", 0, match.start())) + 1
            sentence_end_candidates = [position for marker in ".!?" if (position := citation_stripped.find(marker, match.end())) >= 0]
            sentence_end = min(sentence_end_candidates) + 1 if sentence_end_candidates else len(citation_stripped)
            sentence = citation_stripped[sentence_start:sentence_end]
            if (_NEGATED_RARITY.search(prefix + match.group(0))
                    or _UNCERTAIN_RARITY.search(sentence)
                    or (_is_scoped_gap(sentence) and _RARITY.search(sentence))):
                continue
            if match.group(0).lower() not in source_frequency_terms:
                notes.append(_compact_note(
                    "rarity_word_not_in_cited_context",
                    f"The assertive frequency word '{match.group(0)}' is absent from its cited context. This only flags missing wording; it does not establish frequency or its absence.",
                ))
                break
    return notes


def feedback_notes(messages: list[dict]) -> list[dict[str, str]]:
    """Return bounded mechanical revision notes; never judge scientific entailment."""
    if len(messages) != 4:
        return [_compact_note("invalid_revision_context", "Expected the existing two-pass four-message revision context.")]
    try:
        from triallens.conversation import GeneratedAnswer
        payload = json.loads(messages[1]["content"])
        draft = GeneratedAnswer.model_validate_json(messages[2]["content"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return [_compact_note("invalid_draft", "The draft did not match the required answer JSON schema. Return valid JSON with paragraphs, cited_sources, and uncertainty.")]
    if not isinstance(payload, dict):
        return [_compact_note("invalid_revision_context", "The evidence payload was not a JSON object; use only supplied evidence.")]

    notes: list[dict[str, str]] = []
    records = _source_evidence(payload)
    allowed = set(records)
    paragraphs = [paragraph.strip() for rendered in draft.paragraphs
                  for paragraph in re.split(r"\n\s*\n", rendered) if paragraph.strip()]
    marker_citations = {citation for paragraph in paragraphs for citation in _CITATION.findall(paragraph)}
    listed_citations = set(draft.cited_sources)
    unknown = sorted((marker_citations | listed_citations) - allowed)
    if unknown:
        notes.append(_compact_note("unknown_citation", "Remove or replace citation IDs not present in the supplied evidence: " + ", ".join(unknown[:8])))
    unlisted = sorted(marker_citations - listed_citations)
    if unlisted:
        notes.append(_compact_note("citation_list_mismatch", "List every exact inline citation in cited_sources: " + ", ".join(unlisted[:8])))
    listed_only = sorted(listed_citations - marker_citations)
    if listed_only:
        notes.append(_compact_note("cited_source_not_inline", "Remove citations not used inline or add the exact citation beside the supported claim: " + ", ".join(listed_only[:8])))
    has_any_citations = bool(marker_citations or listed_citations)
    missing_paragraphs = [str(index + 1) for index, paragraph in enumerate(paragraphs)
                          if not _CITATION.search(paragraph)
                          and (has_any_citations or not _is_scoped_gap(paragraph))]
    if missing_paragraphs:
        message = ("Any answer citing a source must cite every paragraph, including scoped gaps. Only an entirely uncited scoped-gap answer may omit citations. Missing paragraph(s): "
                   if has_any_citations else "Cite evidence paragraphs; only an entirely scoped-gap answer may be uncited. Missing paragraph(s): ")
        notes.append(_compact_note("paragraph_without_citation", message + ", ".join(missing_paragraphs[:5])))

    cited_texts = [records[citation]["text"] for citation in marker_citations | listed_citations if citation in records]
    answer_text = "\n\n".join(paragraphs)
    if _contains_28_word_copy(answer_text, cited_texts):
        notes.append(_compact_note("long_source_copy", "Paraphrase instead of copying 28 or more consecutive normalized words from a cited source."))

    notes.extend(_rarity_notes(paragraphs, records))
    question = payload.get("question", "")
    answer_without_citations = _CITATION.sub(" ", answer_text)
    if isinstance(question, str) and _QUANTITATIVE_ASK.search(question) and not _DIGIT.search(answer_without_citations) and not any(_is_scoped_gap(p) for p in paragraphs):
        notes.append(_compact_note(
            "requested_statistic_missing",
            "The question explicitly requests a quantity. Include only a directly relevant measured value found in the supplied evidence, or state the specific scoped gap; do not add unrelated study numbers.",
        ))
    return notes[:MAX_NOTES]


def _feedback_block(notes: list[dict[str, str]]) -> str:
    heading = "\n\nEVALUATION-ONLY MECHANICAL FEEDBACK (not an entailment judgment):\n"
    bounded = list(notes)
    while bounded:
        block = heading + json.dumps({"mechanical_feedback": bounded}, ensure_ascii=False, separators=(",", ":"))
        if len(block) <= MAX_FEEDBACK_CHARS:
            return block
        bounded.pop()
    return ""


@contextmanager
def revision_feedback_experiment():
    """Append feedback only for the second call; provider call count stays two."""
    from triallens import conversation

    original = conversation.cloudflare.completion

    def wrapped(messages: list[dict], schema: dict) -> str:
        if len(messages) == 4 and messages[-1].get("role") == "user":
            notes = feedback_notes(messages)
            if notes:
                # Copy containers so the caller's actual revision context is not mutated.
                copied = [dict(message) for message in messages]
                copied[-1]["content"] = str(copied[-1].get("content", "")) + _feedback_block(notes)
                return original(copied, schema)
        return original(messages, schema)

    conversation.cloudflare.completion = wrapped
    try:
        yield
    finally:
        conversation.cloudflare.completion = original

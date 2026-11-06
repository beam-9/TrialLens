"""Conservative, evaluation-only checks for unsupported numeric claims."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from triallens.conversation import normalize_citations
from triallens.text import normalize_numeric_signs


_NCT = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)
_CITATION = re.compile(
    r"(?:\[|【|［)(?=[^\]】］]*(?:PubMed:|ClinicalTrials\.gov:|openFDA label:|FDA-LABEL-|doi:))"
    r"[^\]】］]*(?:\]|】|］)", re.IGNORECASE
)
# Thousands separators are accepted only in conventional three-digit groups.
_NUMBER = re.compile(
    r"(?<![\w.])([+\-−]?(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+|(?<!\d)\.\d+)?(?:[eE][+\-]?\d+)?)(?![\w.])"
)


def _without_ids_and_citations(text: str) -> str:
    text = _NCT.sub(" ", text)
    return _CITATION.sub(" ", text)


_WORD_VALUES = dict(zip(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety".split(),
    [*range(20), *range(20, 100, 10)],
))
_UNIT_WORD = r"(?:one|two|three|four|five|six|seven|eight|nine)"
_SMALL_WORD = r"(?:ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)"
_TENS_WORD = r"(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)"
_JOIN_WORD = r"[\s‐‑-]+"
_UNDER_HUNDRED = rf"(?:{_TENS_WORD}(?:{_JOIN_WORD}{_UNIT_WORD})?|{_SMALL_WORD}|{_UNIT_WORD})"
_WRITTEN_HUNDREDS = re.compile(
    rf"\b(?:(minus|negative)\s+)?({_UNIT_WORD}\s+hundred"
    rf"(?:{_JOIN_WORD}(?:and\s+)?{_UNDER_HUNDRED})?)\b",
    re.I,
)


def written_hundreds(text: str) -> set[str]:
    """Recognize complete spelled-out hundreds without treating words as units."""
    result = set()
    for match in _WRITTEN_HUNDREDS.finditer(text):
        # Do not take a partial value out of a larger number or decimal.
        if re.match(r"[\s‐‑-]+(?:thousand|million|billion|point)\b", text[match.end():], re.I):
            continue
        words = re.findall(r"[a-z]+", match[2].lower())
        total = _WORD_VALUES[words[0]] * 100
        total += sum(_WORD_VALUES[word] for word in words[2:] if word != "and")
        result.add(str(-total if match[1] else total))
    return result


def numeric_values(text: str) -> set[str]:
    """Return canonical Decimal strings for plainly written numeric values."""
    text = normalize_numeric_signs(_without_ids_and_citations(str(text)))
    # A dash between two digits denotes a range, even when rendered with an
    # ASCII hyphen. A leading dash remains a possible negative sign.
    text = re.sub(r"(?<=\d)[\-‐‑–—−](?=\d)", " ", text)
    values: set[str] = written_hundreds(text)
    for match in _NUMBER.finditer(text):
        token = match.group(1)
        if not token or token in {"+", "-", "−", ".", "+.", "-."}:
            continue
        exponent = re.search(r"[eE]([+\-]?\d+)$", token)
        mantissa = token[:exponent.start()] if exponent else token
        if len(re.sub(r"\D", "", mantissa)) > 100:
            continue
        if exponent:
            exponent_digits = exponent.group(1).lstrip("+-")
            if len(exponent_digits) > 3 or abs(int(exponent.group(1))) > 100:
                continue
        # ASCII hyphen and the mathematical minus are signs; typographic
        # dashes (including range separators) deliberately are not.
        token = token.replace(",", "").replace("−", "-")
        try:
            value = Decimal(token)
        except InvalidOperation:
            continue
        if value == 0:
            values.add("0")
        else:
            values.add(format(value.normalize(), "f"))
    return values


def _records(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    records = payload.get("evidence", payload.get("records", payload.get("sources", [])))
    return [r for r in records if isinstance(r, dict)] if isinstance(records, list) else []


def _source_numbers(record: dict) -> set[str]:
    parts: list[str] = []
    for key in ("text", "title", "publication_date"):
        value = record.get(key)
        if isinstance(value, str):
            parts.append(value)
    passages = record.get("matched_passages", [])
    if isinstance(passages, list):
        parts.extend(str(p) for p in passages if isinstance(p, str))
    design = record.get("registry_design")
    if design is None and isinstance(record.get("metadata"), dict):
        design = record["metadata"].get("registry_design")
    if design is not None:
        parts.append(design if isinstance(design, str) else repr(design))
    return numeric_values("\n".join(parts))


def unsupported_numbers(answer_dict: dict, payload: Any) -> list[str]:
    """Find unsupported written numbers, scoped to the paragraph's own sources.

    An unattributed paragraph can use a sole declared, valid citation to choose
    evidence for feedback. This function never inserts or changes citations.
    """
    if not isinstance(answer_dict, dict):
        return []
    records = _records(payload)
    by_citation = {r.get("citation"): r for r in records
                   if isinstance(r.get("citation"), str) and r.get("citation")}
    valid = set(by_citation)
    declared = answer_dict.get("cited_sources", [])
    declared_valid = {c for c in declared if isinstance(c, str) and c in valid} if isinstance(declared, list) else set()

    notes: list[str] = []
    for section in ("paragraphs", "uncertainty"):
        items = answer_dict.get(section, [])
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items, 1):
            if not isinstance(item, str):
                continue
            normalized = normalize_citations(item, valid)
            cited = set(re.findall(r"\[([^\]]+)\]", normalized))
            if cited:
                # An invalid or mixed marker makes attribution uncertain.
                if not cited <= valid:
                    continue
                chosen = cited
            elif len(declared_valid) == 1:
                chosen = declared_valid
            else:
                continue
            if len(chosen) != 1:
                # Multiple sources can support a number, but without a finer
                # claim-to-source mapping the check is deliberately skipped.
                continue
            citation = next(iter(chosen))
            unsupported = numeric_values(item) - _source_numbers(by_citation[citation])
            if unsupported:
                rendered = ", ".join(sorted(unsupported, key=Decimal))
                notes.append(f"{section}[{index}] contains numeric value(s) {rendered} not found in {citation}.")
    return notes

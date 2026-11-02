"""Narrow label population checks over exact retained indication clauses.

These reject a known population broadening error, not verify medical claims.
Unrecognized wording or absent clauses remains unknown to this check.
"""
from __future__ import annotations

import hashlib
import re

PREDICATE = re.compile(r"\b(?:is|are)\s+indicated\b|\bis a combination of\b.*\bindicated\b", re.I)
PEDIATRIC = re.compile(r"\b(?:children|pediatric|paediatric)\b", re.I)
AGE_FLOOR = re.compile(r"\b(\d{1,3})\s+years?\s+(?:of age\s+)?(?:and\s+)?(?:older|or older|and over|or over)\b", re.I)


def scope_clauses(record: dict) -> list[dict]:
    if record.get('source_type') != 'fda_label':
        return []
    result = []
    texts = [('text', record.get('text', ''))]
    texts += [(f'matched_passages[{i}]', text) for i, text in enumerate(record.get('matched_passages', []))]
    seen = set()
    for location, text in texts:
        if not isinstance(text, str):
            continue
        # Require a complete sentence boundary, retaining decimal punctuation.
        start = 0
        for boundary in re.finditer(r'[.!?](?=\s|$)', text):
            end = boundary.end()
            raw = text[start:end]
            leading = len(raw) - len(raw.lstrip())
            clause = raw.strip()
            offset = start + leading
            start = end
            if not clause or len(clause) > 1200 or clause in seen or not PREDICATE.search(clause):
                continue
            seen.add(clause)
            result.append({'id': f"L{len(result) + 1}", 'citation': record.get('citation'),
                           'quote': clause, 'location': location, 'start': offset,
                           'end': offset + len(clause),
                           'text_sha256': hashlib.sha256(text.encode()).hexdigest()})
            if len(result) == 3:
                return result
    return result


def pediatric_indication_issue(answer: str, records: list[dict]) -> str | None:
    """Reject positive pediatric use losing a cited label's numeric age floor."""
    lookup = {record.get('citation'): record for record in records}
    for paragraph in re.split(r"\n\s*\n", answer):
        # Only a positive use/indication assertion is in scope. Negative or
        # unknown pediatric-use statements are not turned into contraindications.
        if not re.search(r"\b(?:used|approved|indicated)\b[^.!?]{0,140}\b(?:children|pediatric|paediatric)\b", paragraph, re.I):
            continue
        if re.search(r"\b(?:not|never)\s+(?:(?:been|currently)\s+)?(?:used|approved|indicated)\b|\b(?:unknown|unstudied)\b", paragraph, re.I):
            continue
        cues = [cue['quote'] for citation in re.findall(r"\[([^\]]+)\]", paragraph) if citation in lookup
                for cue in scope_clauses(lookup[citation])]
        floors = {m[1] for clause in cues if PEDIATRIC.search(clause) for m in AGE_FLOOR.finditer(clause)}
        for age in floors:
            # A matching number elsewhere in the paragraph is not an age limit.
            boundary = rf"\b{re.escape(age)}\s+(?:years?\s+(?:of age\s+)?)?(?:and|or)\s+(?:older|over)\b|\bat least\s+{re.escape(age)}\s+years?\b"
            if not re.search(boundary, paragraph, re.I):
                return 'Pediatric indication omits an explicit cited label age boundary'
    return None

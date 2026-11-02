"""Opt-in label-scope experiment; exact spans, no medical fact inference.

These checks diagnose a narrow observed failure. Passing is not entailment or
clinical validation, and no production module imports this file.
"""
from contextlib import contextmanager
import json
import re
from unittest.mock import patch

from triallens.label_checks import scope_clauses, PEDIATRIC, AGE_FLOOR


def scope_issues(answer: dict, payload: dict) -> list[str]:
    """Flag positive pediatric-use claims losing an explicit numeric age floor.

    Conservative diagnostic only: inspect the paragraph's cited indication
    clauses, not all numbers in a source or unrelated safety text.
    """
    records = {r.get('citation'): r for r in payload.get('evidence', []) if isinstance(r, dict)}
    notes = []
    for i, paragraph in enumerate(answer.get('paragraphs', [])):
        if not isinstance(paragraph, str) or not PEDIATRIC.search(paragraph):
            continue
        if not re.search(r'\b(?:used|use|indicated|approved)\b', paragraph, re.I):
            continue
        if re.search(r"\b(?:not|never|unknown|unstudied)\b|\b(?:has|have) not\b", paragraph, re.I):
            continue  # Unknown/negative claims require separate semantic review.
        cited = re.findall(r'\[([^\]]+)\]', paragraph)
        clauses = [(citation, cue['quote']) for citation in cited if citation in records
                   for cue in scope_clauses(records[citation])]
        floors = {m[1] for _, clause in clauses if PEDIATRIC.search(clause)
                  for m in AGE_FLOOR.finditer(clause)}
        if floors and not all(re.search(rf'\b{re.escape(age)}\s+(?:years?\s+(?:of age\s+)?)?(?:and|or)\s+(?:older|over)\b|\bat least\s+{re.escape(age)}\s+years?\b', paragraph, re.I) for age in floors):
            notes.append(f'Paragraph {i + 1}: preserve the cited pediatric indication age boundary ({", ".join(sorted(floors))} years); do not broaden it to all children.')
        # Pooled citations with different literal indication populations are a
        # review signal; separate formulations explicitly rather than pool them.
        if floors and len({citation for citation, _ in clauses}) > 1 and not re.search(r'\b(?:whereas|while|separately|extended.release|combination)\b', paragraph, re.I):
            notes.append(f'Paragraph {i + 1}: distinguish each cited product/formulation indication; the supplied label populations differ.')
    return notes[:4]


@contextmanager
def label_scope_experiment(enabled: bool = False):
    if not enabled:
        yield
        return
    from triallens import conversation
    original_build = conversation.build_evidence_records
    original_completion = conversation.cloudflare.completion

    def build(sources, chunks):
        records = original_build(sources, chunks)
        # Copy records; do not alter stored sources, passages or their budgets.
        return [{**record, **({'scope_clauses': clauses,
                              'scope_clause_note': 'Exact retained label sentences, not independently verified facts. Preserve product, formulation and population qualifiers; an adult indication does not establish pediatric contraindication.'}
                             if (clauses := scope_clauses(record)) else {})} for record in records]

    def completion(messages, schema):
        submitted = messages
        payload = json.loads(messages[1]['content'])
        if len(messages) == 4:
            try:
                notes = scope_issues(json.loads(messages[2]['content']), payload)
            except (ValueError, TypeError):
                notes = []
            if notes:
                submitted = [dict(message) for message in messages]
                submitted[-1]['content'] += '\nSource-scope review signals (check original clauses): ' + json.dumps(notes)
        content = original_completion(submitted, schema)
        if len(messages) == 4 and scope_issues(json.loads(content), payload):
            raise ValueError('Final answer retains a label population/scope review signal')
        return content

    with patch.object(conversation, 'build_evidence_records', build), patch.object(conversation.cloudflare, 'completion', completion):
        yield

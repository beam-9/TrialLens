"""Evaluation-only outcome ownership and necessary answer-coverage checks.

These reject known inconsistencies, not prove semantic entailment. Complete
source packets remain untouched; links reference only retained matched passages.
"""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
import re
from numeric_checks import numeric_values
from triallens.trial_design import render_registry_design


def _outcomes(payload):
    result = []
    for record in payload.get('evidence', []):
        passages = record.get('matched_passages', [])
        for link in record.get('outcome_links', []):
            i = link.get('matched_passage_index')
            if type(i) is not int or not 0 <= i < len(passages) or not isinstance(link.get('id'), str):
                continue
            result.append({'citation': record['citation'], 'id': link['id'], 'title': link.get('title', ''),
                           'has_reported_analysis': link.get('has_reported_analysis') is True,
                           'text': passages[i], 'design': record.get('registry_design', {})})
    return result


def tag_outcome_support(index: dict, payload: dict) -> dict:
    tagged = deepcopy(index)
    outcomes = _outcomes(payload)
    designs = {record['citation']: render_registry_design(record.get('registry_design')) for record in payload.get('evidence', [])}
    for value in tagged.values():
        owners = [packet for packet in outcomes if packet['citation'] == value['citation'] and value['text'] in packet['text']]
        value['outcome_ids'] = sorted({packet['id'] for packet in owners})
        value['outcome_titles'] = list(dict.fromkeys(packet['title'] for packet in owners))
        value['has_reported_analysis'] = any(packet['has_reported_analysis'] for packet in owners)
        value['support_role'] = ('outcome' if owners else 'registry_design' if value['text'] in designs.get(value['citation'], '') else 'source_context')
    return tagged


def review_issues(review, draft, index: dict) -> dict[int, str]:
    """Reject cross-outcome support and significance without any analysis."""
    problems = {}
    for item in review.reviews:
        if item.verdict == 'unsupported' or item.index >= len(draft.claims):
            continue
        support = [index[key] for key in item.quotes if key in index]
        owners = {owner for value in support for owner in value.get('outcome_ids', [])}
        if len(owners) > 1:
            problems[item.index] = 'One factual sentence must not mix supporting outcome packets.'
            continue
        positive = False
        for match in re.finditer(r'statistically\s+significant|statistical\s+significance|significant(?:ly)?\s+(?:improv\w*|differ\w*|reduc\w*|increas\w*|benefit\w*)', item.text, re.I):
            prefix = item.text[max(0, match.start()-35):match.start()]
            if not re.search(r'\b(?:no|not|without|inconclusive)\b', prefix, re.I):
                positive = True
        if owners and positive and not any(value.get('has_reported_analysis') for value in support):
            problems[item.index] = 'This outcome packet supplies no reported analysis supporting a significance claim.'
    return problems


def answer_requirements(payload: dict) -> dict:
    question = payload.get('question', '')
    if re.search(r'\bsimpl\w*\b|main limitation|key numbers', question, re.I):
        history = payload.get('history', [])
        if history:
            question += ' ' + str(history[-1].get('question', ''))
    if not (re.search(r'\bcounts?\b', question, re.I) and re.search(r'\bdenominators?\b', question, re.I)):
        return {}
    question_ids = set(re.findall(r'NCT\d{8}', question, re.I))
    terms = set(re.findall(r'\w+', question.lower())) - {'the','of','at','and','what','for','were','with','results','give','counts','denominators'}
    candidates = []
    for packet in _outcomes(payload):
        if question_ids and not any(identifier.lower() in packet['citation'].lower() for identifier in question_ids):
            continue
        if 'Measure parameter type: NUMBER' not in packet['text'] or 'Units: Participants' not in packet['text']:
            continue
        title_words = set(re.findall(r'\w+', packet['title'].lower()))
        score = len(terms & title_words)
        if packet['title'].strip() and packet['title'].lower() in question.lower():
            score += 3
        candidates.append((score, packet))
    if not candidates:
        return {}
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    if candidates[0][0] == 0 or (len(candidates)>1 and candidates[0][0] == candidates[1][0]):
        return {}  # Ambiguous question: do not invent a target endpoint.
    packet = candidates[0][1]
    measures = packet['text'].split('Analysis groups:', 1)[0]
    values = set()
    for match in re.findall(r'\bvalue=([-+\d.]+)', measures):
        values.update(numeric_values(match))
    if not values or len(values)>32:
        return {}
    design = packet['design']
    return {'citation': packet['citation'], 'outcome_id': packet['id'], 'outcome_title': packet['title'],
            'required_reported_values': sorted(values, key=Decimal),
            'require_comparison_limit': design.get('allocation') == 'NON_RANDOMIZED' and design.get('intervention_model') == 'SINGLE_GROUP',
            'reported_design': {key: design[key] for key in ('allocation', 'intervention_model') if key in design},
            'comparison_instruction': 'Use the explicit design metadata to explain the limit on causal attribution. Different visit denominators do not establish paired individual transitions.',
            'instruction': 'Retain these reported counts, missingness and each visit denominator, not calculated percentages. Explain the comparison boundary when asked. Different visit denominators do not supply per-person transition counts.'}


def coverage_issues(answer: dict, requirement: dict) -> list[str]:
    if not requirement:
        return []
    text = ' '.join(answer.get('paragraphs', []))
    values = numeric_values(text)
    if re.search(r'\b(?:none|zero)\b|\bno\s+(?:missing|assessments?\s+(?:were\s+)?missing)', text, re.I):
        values.add('0')
    if re.search(r'\bone\s+(?:\w+\s+){0,3}(?:was\s+)?missing\b', text, re.I):
        values.add('1')
    issues = []
    missing = set(requirement['required_reported_values']) - values
    if missing:
        issues.append('Required reported count/denominator values missing: '+', '.join(sorted(missing,key=Decimal)))
    if requirement['citation'] not in answer.get('cited_sources', []):
        issues.append('Requested outcome source was not cited.')
    if requirement['require_comparison_limit']:
        normalized = re.sub(r'[‐‑–—−-]', ' ', text.lower())
        design = re.search(r'non\s*random|not\s+random|single\s+group|one\s+(?:treatment\s+)?group|pre\s*post|before\s+and\s+after', normalized)
        boundary = re.search(r'\b(?:cannot|can not|can.t|does not|doesn.t|not|no)\b.{0,90}\b(?:isolat\w*|attribut\w*|establish\w*|prov\w*|proof|caus\w*|determin\w*|tell\w*)',normalized)
        boundary = boundary or re.search(r'\brather than\s+(?:a\s+)?randomized\s+(?:contrast|comparison)', normalized)
        if not design or not boundary:
            issues.append('Requested nonrandomized single-group comparison limitation is missing.')
    return issues

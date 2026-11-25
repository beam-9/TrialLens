"""Inactive question-specific body/abstract separation; preserves original source records."""
from contextlib import contextmanager
import json
import re


def body_context(payload: dict) -> dict:
    question = payload.get('question', '')
    history = payload.get('history', [])
    if history and re.search(r'\b(?:simpl\w*|rephras\w*|explain that)\b', question, re.I):
        question += ' ' + history[-1].get('question', '')
    if (not re.search(r'\b(?:full[- ]text|indexed results|results paragraphs?|figures?|fig\.)', question, re.I)
            or re.search(r'\b(?:discrepan\w*|conflict\w*|contradict\w*|compare.*abstract|abstract.*versus)\b', question, re.I)):
        return payload
    records = []
    for record in payload.get('evidence', []):
        if record.get('paper_passage_links'):
            record = {**record, 'text': '', 'text_scope': (
                'Abstract omitted from this body-specific question. Use the selected identified full-text '
                'passages below; they are a partial article index. Original abstract remains stored.'
            )}
        records.append(record)
    return {**payload, 'evidence': records}


@contextmanager
def paper_body_scope_experiment(enabled):
    if not enabled:
        yield
        return
    from triallens import cloudflare
    original = cloudflare.completion

    def completion(messages, schema):
        payload = json.loads(messages[1]['content'])
        scoped = body_context(payload)
        submitted = messages
        if scoped is not payload:
            submitted = [messages[0], {**messages[1], 'content': json.dumps(scoped)}, *messages[2:]]
        return original(submitted, schema)
    cloudflare.completion = completion
    try:
        yield
    finally:
        cloudflare.completion = original

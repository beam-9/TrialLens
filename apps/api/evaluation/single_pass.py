"""Explicit evaluation seam for testing one draft with all final validators."""
from contextlib import contextmanager


@contextmanager
def single_pass_experiment(enabled=False):
    if not enabled:
        yield
        return
    from triallens import conversation

    original = conversation.cloudflare.completion
    draft = None
    context = None

    def completion(messages, schema):
        nonlocal draft, context
        if len(messages) == 2:
            draft = None
            context = [dict(message) for message in messages]
            draft = original([dict(message) for message in messages], schema)
            return draft
        if len(messages) == 4 and draft is not None:
            if messages[:2] != context or messages[2] != {"role": "assistant", "content": draft}:
                draft = None
                raise ValueError('Single-pass replay context differs from the submitted draft')
            result, draft = draft, None
            context = None
            return result
        raise ValueError('Single-pass experiment received an unexpected request sequence')

    conversation.cloudflare.completion = completion
    try:
        yield
    finally:
        conversation.cloudflare.completion = original

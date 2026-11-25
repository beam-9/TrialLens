"""Source-backed numerical checks guide the existing revision, not another model call."""
import json

import pytest

from triallens import conversation
from triallens.models import Answer, EvidenceSource, SourceType, Workspace


def setup(monkeypatch, tmp_path, abstract):
    monkeypatch.setenv('TRIALLENS_CHAT_PROVIDER', 'cloudflare')
    monkeypatch.setenv('TRIALLENS_USAGE_PATH', str(tmp_path / 'usage.sqlite3'))
    monkeypatch.setattr(conversation, 'chat_configured', lambda: True)
    workspace = Workspace(condition='test condition', source_types=[SourceType.pubmed])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
                            external_id='1', title='Reported comparison', abstract=abstract)
    fallback = Answer(workspace_id=workspace.id, question='Give the numerical results and uncertainty.',
                      short_answer='Source excerpt', evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    return workspace, source, fallback


def output(text):
    return json.dumps({'paragraphs': [text + ' [PubMed:1].'], 'cited_sources': ['PubMed:1'], 'uncertainty': []})


@pytest.mark.parametrize('repair', [True, False])
def test_reversed_sign_is_flagged_before_revision_and_rejected_if_unrepaired(monkeypatch, tmp_path, repair):
    workspace, source, fallback = setup(monkeypatch, tmp_path, 'Drug A minus placebo: −0.94% [95% CI, −1.25 to −0.63].')
    calls = []
    def complete(messages, schema):
        calls.append(messages)
        if len(messages) == 4:
            assert 'reverses the sign' in messages[-1]['content']
        sign = '-' if repair and len(messages) == 4 else '+'
        return output(f'The reported difference is {sign}0.94%, with a 95% CI of -1.25% to -0.63%')
    monkeypatch.setattr(conversation.cloudflare, 'completion', complete)
    answer = conversation.ConversationService().generate(workspace, fallback.question, [], [source], fallback)
    assert len(calls) == 2
    assert (answer.generation_mode == 'conversational') is repair
    if repair:
        assert '-0.94%' in answer.direct_answer


def test_requested_dispersion_uses_source_pair_in_existing_revision(monkeypatch, tmp_path):
    workspace, source, fallback = setup(monkeypatch, tmp_path, 'At 16 weeks Arm A decreased 0.58%±0.11%.')
    calls = []
    def complete(messages, schema):
        calls.append(messages)
        if len(messages) == 4:
            assert '0.58%±0.11%' in messages[-1]['content']
            assert 'not evidence of outcome/group attribution' in messages[-1]['content']
            return output('Arm A had a reported decrease of 0.58% (±0.11%) at 16 weeks')
        return output('Arm A had a decrease of 0.58% at 16 weeks')
    monkeypatch.setattr(conversation.cloudflare, 'completion', complete)
    answer = conversation.ConversationService().generate(workspace, fallback.question, [], [source], fallback)
    assert len(calls) == 2 and answer.generation_mode == 'conversational'
    assert '±0.11%' in answer.direct_answer

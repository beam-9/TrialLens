import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluation'))
from paper_body_scope import body_context


def test_explicit_body_question_separates_abstract_without_mutating_source_context():
    record = {'text': 'Contradictory abstract', 'paper_passage_links': [{'section': 'Full text paragraph 001'}],
              'matched_passages': ['Verified Results.'], 'content_truncated': True}
    payload = {'question': 'What do the indexed Results paragraphs report?', 'evidence': [record]}
    scoped = body_context(payload)
    assert scoped['evidence'][0]['text'] == '' and record['text'] == 'Contradictory abstract'
    assert scoped['evidence'][0]['matched_passages'] == record['matched_passages']
    assert scoped['evidence'][0]['content_truncated']
    assert body_context({**payload, 'question': 'Explain the abstract/body discrepancy.'})['evidence'][0]['text'] == record['text']
    abstract_request = {**payload, 'question': 'What does the abstract say?'}
    assert body_context(abstract_request) is abstract_request


def test_no_body_or_new_outcome_does_not_remove_abstract():
    record = {'text': 'Abstract only.', 'paper_passage_links': [], 'matched_passages': []}
    payload = {'question': 'What do the Results paragraphs say?', 'evidence': [record]}
    assert body_context(payload)['evidence'][0]['text'] == 'Abstract only.'
    record['paper_passage_links'] = [{'section': 'Full text paragraph 001'}]
    payload['question'] = 'What about mortality?'
    payload['history'] = [{'question': 'What do the indexed Results paragraphs say?'}]
    assert body_context(payload) is payload
    payload['question'] = 'Explain that more simply.'
    assert body_context(payload)['evidence'][0]['text'] == ''

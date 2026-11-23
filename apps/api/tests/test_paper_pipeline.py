"""Paper text reaches Ask intact; unavailable enrichment preserves abstracts."""
import asyncio
import hashlib
import json

import httpx
import pytest

from triallens import conversation
from triallens.models import EvidenceSource, RetrievedChunk, SourceType, Workspace
from triallens.paper_text import MAX_PACKET_CHARS, MAX_XML_BYTES
from triallens.rag import AnswerService, Retriever, build_chunks, document_content_scope
from triallens.sources import PubMedClient


PAPER = b'''<article><front><article-meta><article-id pub-id-type="pmid">123</article-id>
<article-id pub-id-type="pmcid">PMC456</article-id><permissions><license>
<license-p>CC BY 4.0</license-p></license></permissions></article-meta></front><body>
<sec><title>Results</title><p>In 200 randomized adults, drug A was compared with placebo.
At 12 weeks, the adjusted HbA1c difference was 0.6 percentage points lower with drug A
(95% confidence interval 0.2 to 1.0 percentage points lower).</p>
<table-wrap id="t1"><label>Table 1</label><caption><p>HbA1c at 12 weeks</p></caption>
<table><thead><tr><th>Outcome</th><th>Drug A (n=100)</th><th>Placebo (n=100)</th></tr></thead>
<tbody><tr><td>Mean HbA1c change, percentage points</td><td>-0.9</td><td>-0.3</td></tr></tbody></table>
<table-wrap-foot><p>Adjusted difference -0.6; 95% CI -1.0 to -0.2 percentage points.</p></table-wrap-foot>
</table-wrap></sec></body></article>'''


def pubmed_xml(pmcid='PMC456'):
    return f'''<PubmedArticleSet><PubmedArticle><PMID>123</PMID><ArticleTitle>Drug A trial</ArticleTitle>
<AbstractText Label="Background">This trial studies HbA1c in adults.</AbstractText>
<PubmedData><ArticleIdList><ArticleId IdType="pmc">{pmcid}</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle></PubmedArticleSet>'''


def source_with_paper(monkeypatch, *, paper=PAPER, status=200, pmcid='PMC456'):
    requests = []
    def handle(request):
        requests.append(request)
        if 'esearch' in request.url.path:
            return httpx.Response(200, json={'esearchresult': {'idlist': ['123']}})
        if 'efetch' in request.url.path:
            return httpx.Response(200, text=pubmed_xml(pmcid))
        assert request.url.host == 'www.ebi.ac.uk'
        assert request.url.path == '/europepmc/webservices/rest/PMC456/fullTextXML'
        return httpx.Response(status, content=paper)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    workspace = Workspace(condition='diabetes', intervention='drug A', source_types=[SourceType.pubmed])
    source = asyncio.run(PubMedClient().fetch(workspace))[0]
    return workspace, source, requests


def test_paper_fetch_index_retrieve_context_keeps_table_and_abstract_distinct(monkeypatch):
    workspace, source, requests = source_with_paper(monkeypatch)
    assert len(requests) == 3
    assert source.external_id == '123' and source.url == 'https://pubmed.ncbi.nlm.nih.gov/123/'
    assert source.abstract == 'This trial studies HbA1c in adults.'
    indexing = source.metadata['full_text']
    assert indexing['xml_sha256'] == hashlib.sha256(PAPER).hexdigest()
    assert indexing['license']['text'] == 'CC BY 4.0'
    chunks = build_chunks([source])
    table = next(c for c in chunks if c.section == 'Full text table 001')
    assert table.text == ' '.join(source.metadata['sections'][table.section].split())
    for text in ['Drug A (n=100)', 'Placebo (n=100)', '-0.9', '-0.3', 'Adjusted difference -0.6']:
        assert text in table.text
    question = 'What is the numerical HbA1c difference for drug A versus placebo at 12 weeks, with group sizes and confidence interval?'
    retrieved = Retriever().retrieve_conversation(workspace, question, chunks, [source])
    assert any(c.section == table.section for c in retrieved)
    record = conversation.build_evidence_records([source], retrieved)[0]
    assert table.text in record['matched_passages']
    assert record['text'] == source.abstract
    assert record['content_truncated'] and 'partial article index' in document_content_scope(source)
    assert record['paper_passage_links']
    assert record['full_text_provenance']['pmcid'] == 'PMC456'
    assert 'paragraph_sections' not in record['full_text_provenance']
    assert sum(map(len, record['matched_passages'])) + len(record['text']) <= 28000


@pytest.mark.parametrize('status,paper,pmcid', [
    (404, b'', 'PMC456'), (302, b'', 'PMC456'),
    (200, b'<article/>', 'PMC456'),
    (200, PAPER.replace(b'>123<', b'>999<'), 'PMC456'),
    (200, b'x' * (MAX_XML_BYTES + 1), 'PMC456'),
    (200, PAPER, 'http://127.0.0.1/private'),
])
def test_unusable_full_text_preserves_original_abstract(monkeypatch, status, paper, pmcid):
    _, source, requests = source_with_paper(monkeypatch, status=status, paper=paper, pmcid=pmcid)
    assert source.abstract == 'This trial studies HbA1c in adults.'
    assert source.metadata['sections'] == {'Background': source.abstract}
    assert source.metadata['full_text']['status'] == 'unavailable'
    assert source.metadata.get('paper_packet_version') is None
    assert 'abstract content' in document_content_scope(source)
    if pmcid.startswith('http'):
        assert len(requests) == 2


def test_paper_packets_are_all_or_omit_under_context_pressure(monkeypatch):
    workspace, source, _ = source_with_paper(monkeypatch)
    chunk = next(c for c in build_chunks([source]) if c.section.startswith('Full text table'))
    retrieved = RetrievedChunk(chunk_id=chunk.id, source_id=source.id, source_type=source.source_type,
        citation='PubMed:123', text=chunk.text, section=chunk.section, score=1)
    others = [EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed, external_id=str(900+i),
        title='Background', abstract='Other background. ' * 1000) for i in range(7)]
    records = conversation.build_evidence_records([*others, source], [retrieved])
    assert chunk.text in records[0]['matched_passages']
    assert sum(len(r['text']) + sum(map(len, r['matched_passages'])) for r in records) <= 28000
    for altered in ['Drug A -0.9', 'x' * (MAX_PACKET_CHARS + 1)]:
        bad = retrieved.model_copy(update={'text': altered})
        record = conversation.build_evidence_records([source], [bad])[0]
        assert record['matched_passages'] == [] and record['content_truncated']


def test_atomic_paper_footnote_is_not_removed_by_generic_excerpt_cleanup(monkeypatch):
    paper = PAPER.replace(b'Adjusted difference', b'[see methods] Adjusted difference')
    _, source, _ = source_with_paper(monkeypatch, paper=paper)
    chunk = next(c for c in build_chunks([source]) if c.section.startswith('Full text table'))
    assert '[see methods] Adjusted difference' in chunk.text
    passage = RetrievedChunk(chunk_id=chunk.id, source_id=source.id, source_type=source.source_type,
        citation='PubMed:123', text=chunk.text, section=chunk.section, score=1)
    assert chunk.text in conversation.build_evidence_records([source], [passage])[0]['matched_passages']


def test_both_ask_passes_receive_new_paper_result_without_inference(monkeypatch, tmp_path):
    workspace, source, _ = source_with_paper(monkeypatch)
    question = 'Give the numerical HbA1c comparison at 12 weeks for drug A versus placebo.'
    chunks = build_chunks([source])
    retrieved = Retriever().retrieve_conversation(workspace, question, chunks, [source])
    fallback = AnswerService().answer(workspace, question, retrieved, [])
    monkeypatch.setenv('TRIALLENS_CHAT_PROVIDER', 'cloudflare')
    monkeypatch.setenv('TRIALLENS_USAGE_PATH', str(tmp_path / 'usage.sqlite3'))
    monkeypatch.setattr(conversation, 'chat_configured', lambda: True)
    calls = []
    def complete(messages, schema):
        payload = json.loads(messages[1]['content']); calls.append(payload)
        assert any('0.6 percentage points lower' in p for p in payload['evidence'][0]['matched_passages'])
        return json.dumps({'paragraphs': ['In this trial, the adjusted HbA1c difference at 12 weeks was 0.6 percentage points lower with drug A than placebo [PubMed:123].'],
                           'cited_sources': ['PubMed:123'], 'uncertainty': []})
    monkeypatch.setattr(conversation.cloudflare, 'completion', complete)
    result = conversation.ConversationService().generate(workspace, question, [], [source], fallback)
    assert result.generation_mode == 'conversational' and result.citations == ['PubMed:123']
    assert len(calls) == 2 and calls[0] == calls[1]


def test_unknown_encoding_does_not_discard_pubmed_abstracts(monkeypatch):
    _, source, _ = source_with_paper(monkeypatch, paper=b'<?xml version="1.0" encoding="unknown-encoding"?><article/>')
    assert source.abstract == 'This trial studies HbA1c in adults.'
    assert source.metadata['full_text']['reason'] == 'malformed_xml'


def test_paper_section_links_follow_retrieved_identity_not_matching_words(monkeypatch):
    _, source, _ = source_with_paper(monkeypatch)
    first = source.metadata['full_text']['paragraph_sections'][0]
    text = source.metadata['sections'][first]
    source.metadata['sections']['Background'] = text
    chunk = RetrievedChunk(chunk_id='ordinary', source_id=source.id, source_type=source.source_type,
        citation='PubMed:123', text=text, section='Background', score=1)
    assert conversation.build_evidence_records([source], [chunk])[0]['paper_passage_links'] == []
    second = 'Full text paragraph 099 — Other section'
    source.metadata['sections'][second] = text
    source.metadata['full_text']['paragraph_sections'].append(second)
    actual = chunk.model_copy(update={'section': second})
    assert conversation.build_evidence_records([source], [actual])[0]['paper_passage_links'] == [
        {'matched_passage_index': 0, 'section': second}]


def test_structured_extraction_does_not_trim_full_text_packets_into_field_evidence(monkeypatch):
    from triallens.rag import build_extractions
    workspace, source, _ = source_with_paper(monkeypatch)
    extraction = build_extractions([source], workspace)[0]
    fields = json.dumps(extraction.model_dump(mode='json'))
    assert 'Full text table' not in fields and 'Full text paragraph' not in fields
    assert '-0.9' not in fields and '0.6 percentage points lower' not in fields


def test_failed_full_text_attempt_counts_toward_ranked_fetch_cap(monkeypatch):
    attempted = []
    def handle(request):
        if 'esearch' in request.url.path:
            return httpx.Response(200, json={'esearchresult': {'idlist': ['3', '2', '1']}})
        if 'efetch' in request.url.path:
            records = ''.join(pubmed_xml('PMC'+str(i)).split('<PubmedArticleSet>')[1].split('</PubmedArticleSet>')[0].replace('<PMID>123</PMID>', f'<PMID>{i}</PMID>') for i in [1,2,3])
            return httpx.Response(200, text='<PubmedArticleSet>'+records+'</PubmedArticleSet>')
        attempted.append(request.url.path)
        return httpx.Response(404)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    sources = asyncio.run(PubMedClient().fetch(Workspace(condition='topic', source_types=[SourceType.pubmed])))
    assert [s.external_id for s in sources] == ['3', '2', '1']
    assert attempted == ['/europepmc/webservices/rest/PMC3/fullTextXML', '/europepmc/webservices/rest/PMC2/fullTextXML']
    assert sources[-1].metadata['full_text']['reason'] == 'fetch_limit'
    assert all(s.abstract for s in sources)


def test_valid_paper_packet_is_omitted_whole_when_remaining_budget_is_too_small(monkeypatch):
    big = PAPER.replace(b'HbA1c at 12 weeks', b'HbA1c at 12 weeks '+b'caption ' * 850)
    _, source, _ = source_with_paper(monkeypatch, paper=big)
    section = source.metadata['full_text']['table_sections'][0]
    packet = ' '.join(source.metadata['sections'][section].split())
    assert 7000 < len(packet) <= MAX_PACKET_CHARS
    sources = [source.model_copy(deep=True, update={'id': f's{i}', 'external_id': str(1000+i)}) for i in range(4)]
    passages = [RetrievedChunk(chunk_id=s.id, source_id=s.id, source_type=s.source_type,
        citation=f'PubMed:{s.external_id}', text=packet, section=section, score=1) for s in sources]
    records = conversation.build_evidence_records(sources, passages)
    assert packet in records[0]['matched_passages']
    assert records[-1]['matched_passages'] == [] and records[-1]['content_truncated']
    assert sum(len(r['text']) + sum(map(len, r['matched_passages'])) for r in records) <= 28000

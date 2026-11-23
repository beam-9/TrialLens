import hashlib
import xml.etree.ElementTree as ET

import pytest

from triallens.paper_text import MAX_PACKET_CHARS, MAX_XML_BYTES, parse_paper_text

TABLE = '''<table-wrap id="t1"><label>Table 1</label><caption><p>Week 12 events</p></caption>
<table><thead><tr><th>Arm</th><th>Events, n/N</th></tr></thead>
<tbody><tr><th>Example</th><td>8/100<xref rid="fn1">a</xref></td></tr>
<tr><th>Placebo</th><td>3/99</td></tr></tbody></table>
<table-wrap-foot><fn id="fn1"><p>a: analyzed participants; not randomized enrollment.</p></fn></table-wrap-foot></table-wrap>'''


def article(body='<sec><title>Results</title><p>Reduced by 0.<italic>5</italic>% at week 12.</p></sec>', *, pmid='123', pmc='456', license=True):
    rights = '<permissions><license xlink:href="https://example.org/license"><license-p>CC BY 4.0.</license-p></license></permissions>' if license else ''
    return f'''<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>
<article-id pub-id-type="pmid">{pmid}</article-id><article-id pub-id-type="pmc">{pmc}</article-id>
{rights}<abstract><p>Abstract must stay separate.</p></abstract></article-meta></front><body>{body}</body>
<back><ref-list><ref><mixed-citation>Reference not evidence.</mixed-citation></ref></ref-list></back></article>'''.encode()


def test_identity_inline_numeric_text_scope_license_and_provenance():
    xml = article()
    sections, meta = parse_paper_text(xml, '123', 'PMC456')
    assert sections == {'Full text paragraph 001 — Results': 'Reduced by 0.5% at week 12.'}
    assert meta['status'] == 'available'
    assert (meta['pmid'], meta['pmcid']) == ('123', 'PMC456')
    assert meta['xml_sha256'] == hashlib.sha256(xml).hexdigest()
    assert meta['license'] == {'text': 'CC BY 4.0.', 'links': ['https://example.org/license']}
    assert not meta['license_missing'] and meta['partial_indexing']
    assert 'Partial PMC' in meta['scope']
    assert meta['table_sections'] == []


@pytest.mark.parametrize('pmid,pmc', [('999', '456'), ('123', '999'), ('', '456')])
def test_rejects_wrong_or_missing_identity(pmid, pmc):
    sections, meta = parse_paper_text(article(pmid=pmid, pmc=pmc), '123', 'PMC456')
    assert not sections and meta['status'] == 'unavailable'
    assert 'pmid' not in meta


def test_missing_license_is_explicit_and_prefixed_pmc_is_accepted():
    sections, meta = parse_paper_text(article(pmc='PMC456', license=False), '123', 'PMC456')
    assert sections and meta['license_missing']
    assert meta['license'] == {'text': '', 'links': []}


@pytest.mark.parametrize('xml,reason', [
    (b'x' * (MAX_XML_BYTES + 1), 'oversized_or_invalid_xml'),
    (b'<article>', 'malformed_xml'),
    (b'<!DOCTYPE article [<!ENTITY example "unsafe">]><article/>', 'unsafe_xml_declaration'),
    (b'<!ENTITY example SYSTEM "file:///private/example"><article/>', 'unsafe_xml_declaration'),
    (article().decode().encode('utf-16'), 'unsafe_xml_declaration'),
])
def test_unavailable_inputs_never_raise(xml, reason):
    sections, meta = parse_paper_text(xml, '123', 'PMC456')
    assert sections == {} and meta['reason'] == reason


def test_external_doctype_is_removed_without_network_or_file_resolution(monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *a, **k: pytest.fail('External resolution attempted'))
    xml = b'<!DOCTYPE article SYSTEM "file:///definitely-not-present.dtd">' + article()
    sections, meta = parse_paper_text(xml, '123', 'PMC456')
    assert sections and meta['status'] == 'available'
    assert meta['xml_sha256'] == hashlib.sha256(xml).hexdigest()
    public = b'<!DOCTYPE article PUBLIC "-//NLM//DTD JATS//EN" "https://example.invalid/jats.dtd">' + article()
    assert parse_paper_text(public, '123', 'PMC456')[0] == sections


def test_complete_table_keeps_caption_headers_rows_footnotes_and_inline_links():
    sections, meta = parse_paper_text(article('<sec><title>Results</title><p>Observed findings.</p>' + TABLE + '</sec>'), '123', 'PMC456')
    assert meta['table_sections'] == ['Full text table 001']
    packet = sections['Full text table 001']
    table = ET.fromstring(packet)
    assert table.attrib['id'] == 't1'
    assert table.findtext('label') == 'Table 1'
    assert table.findtext('caption/p') == 'Week 12 events'
    assert [node.text for node in table.findall('.//thead/tr/th')] == ['Arm', 'Events, n/N']
    assert [''.join(node.itertext()) for node in table.findall('.//tbody/tr')] == ['Example8/100a', 'Placebo3/99']
    assert table.find('.//xref').attrib['rid'] == 'fn1'
    assert 'not randomized enrollment' in table.findtext('.//fn/p')
    assert all('8/100' not in text for key, text in sections.items() if 'paragraph' in key)


@pytest.mark.parametrize('table,reason', [
    (TABLE.replace('<td>3/99</td>', '<td colspan="2">3/99</td>'), 'merged_cells'),
    (TABLE.replace('<th>Events, n/N</th>', ''), 'ragged_rows'),
    (TABLE.replace('<th>Arm</th>', '<th/>'), 'missing_column_headers'),
    (TABLE.replace('<th>Arm</th>', '<td>Arm</td>'), 'missing_column_headers'),
    (TABLE.replace('Week 12 events', 'x' * MAX_PACKET_CHARS), 'table_size_limit'),
])
def test_unsupported_tables_are_omitted_whole_with_reason(table, reason):
    sections, meta = parse_paper_text(article(table), '123', 'PMC456')
    assert sections == {} and meta['omitted_tables'] == 1
    assert meta['omission_reasons'] == {reason: 1}
    assert meta['table_sections'] == []


def test_bounds_prioritize_results_keep_document_ordinals_and_disclose_omissions():
    intro = '<sec><title>Introduction</title>' + '<p>Background.</p>' * 30 + '</sec>'
    result = '<sec><title>Results</title><sec><title>Efficacy</title><p>8% versus 3%.</p></sec></sec>'
    sections, meta = parse_paper_text(article(intro + result + TABLE * 8), '123', 'PMC456')
    assert sections['Full text paragraph 031 — Results / Efficacy'] == '8% versus 3%.'
    assert meta['indexed_paragraphs'] == 24 and meta['omitted_paragraphs'] == 7
    assert meta['indexed_tables'] == 6 and meta['omitted_tables'] == 2
    assert meta['omission_reasons'] == {'table_count_limit': 2, 'paragraph_limit': 7}
    assert len(meta['table_sections']) == 6
    assert sum(len(v) for k, v in sections.items() if 'paragraph' in k) <= 16000


def test_oversized_paragraph_is_omitted_without_losing_shorter_results():
    body = '<sec><title>Results</title><p>' + 'x' * 16001 + '</p><p>Later complete finding.</p></sec>'
    sections, meta = parse_paper_text(article(body), '123', 'PMC456')
    assert sections == {'Full text paragraph 002 — Results': 'Later complete finding.'}
    assert meta['omitted_paragraphs'] == 1


def test_pmcid_export_and_article_level_floating_tables():
    xml = article().replace(b'pub-id-type="pmc">456', b'pub-id-type="pmcid">PMC456')
    xml = xml.replace(b'</article>', ('<floats-group>' + TABLE + '</floats-group></article>').encode())
    sections, meta = parse_paper_text(xml, '123', 'PMC456')
    assert meta['table_sections'] == ['Full text table 001']
    assert '8/100' in sections['Full text table 001']


def test_conflicting_or_duplicate_ids_cannot_validate():
    for extra in ('<article-id pub-id-type="pmcid">PMC999</article-id>',
                  '<article-id pub-id-type="pmid">123</article-id>'):
        xml = article().replace(b'</article-meta>', extra.encode() + b'</article-meta>')
        sections, meta = parse_paper_text(xml, '123', 'PMC456')
        assert not sections and meta['status'] == 'unavailable'


def test_table_ordinals_survive_omission_and_each_packet_and_paragraph_is_bounded():
    merged = TABLE.replace('<td>3/99</td>', '<td rowspan="2">3/99</td>')
    xml = article(merged + TABLE + '<p>' + 'x' * 8001 + '</p>')
    sections, meta = parse_paper_text(xml, '123', 'PMC456')
    assert meta['table_sections'] == ['Full text table 002']
    assert meta['omitted_tables'] == meta['omitted_paragraphs'] == 1
    assert all(len(packet) <= MAX_PACKET_CHARS for packet in sections.values())


def test_empty_license_and_missing_body_are_disclosed():
    xml = article(license=False).replace(b'</article-meta>', b'<permissions><license/></permissions></article-meta>')
    assert parse_paper_text(xml, '123', 'PMC456')[1]['license_missing']
    xml = article().replace(b'<body>', b'<not-body>').replace(b'</body>', b'</not-body>')
    sections, meta = parse_paper_text(xml, '123', 'PMC456')
    assert not sections and meta['reason'] == 'missing_body'


def test_license_metadata_is_bounded_and_truncation_disclosed():
    rights = '<permissions><license><license-p>' + 'x' * 2200 + '</license-p>'
    rights += ''.join(f'<ext-link xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://example.org/{i}/' + 'y' * 600 + '"/>' for i in range(5))
    rights += '</license></permissions>'
    xml = article(license=False).replace(b'</article-meta>', rights.encode() + b'</article-meta>')
    sections, meta = parse_paper_text(xml, '123', 'PMC456')
    assert sections and meta['license_truncated']
    assert len(meta['license']['text']) == 2000
    assert len(meta['license']['links']) == 4
    assert all(len(link) <= 500 for link in meta['license']['links'])


def test_deep_xml_fails_closed_without_recursion_error():
    sections, meta = parse_paper_text(article('<sec>' * 70 + '<p>Finding.</p>' + '</sec>' * 70), '123', 'PMC456')
    assert not sections and meta['reason'] == 'xml_nesting_limit'

import asyncio

from triallens.models import SourceType, Workspace
from triallens.sources import ClinicalTrialsClient, OpenFdaClient, PubMedClient, fetch_sources


def test_empty_research_results_never_turn_into_synthetic_evidence(monkeypatch):
    async def empty(self, workspace):
        return []
    for client in (PubMedClient, ClinicalTrialsClient, OpenFdaClient):
        monkeypatch.setattr(client, "fetch", empty)
    workspace = Workspace(condition="A topic with no matches", source_types=list(SourceType))
    assert asyncio.run(fetch_sources(workspace)) == []


def test_fda_label_keeps_stable_identity_provenance_and_safety_sections(monkeypatch):
    import httpx
    from triallens.sources import OpenFdaClient

    def handler(request):
        return httpx.Response(200, json={"results": [{
            "id": "stable-record-id", "set_id": "label-set", "effective_time": "20260101",
            "openfda": {"brand_name": ["Example product"]},
            "indications_and_usage": ["Indicated for the studied condition."],
            "contraindications": ["Contraindicated in the specified group."],
            "clinical_studies": ["A trial compared treatment with placebo."],
        }]})

    client_type = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs))
    workspace = Workspace(condition="condition", intervention="example", source_types=[SourceType.fda_label])
    result = asyncio.run(OpenFdaClient()._fetch_label(workspace, "example"))[0]
    assert result.external_id == "FDA-LABEL-stable-record-id"
    assert "stable-record-id" in result.url
    assert "Contraindicated" in result.abstract
    assert "compared treatment" in result.abstract
    assert result.publication_date == "20260101"


def test_pubmed_preserves_inline_abstract_text(monkeypatch):
    import httpx

    def handler(request):
        if "esearch" in request.url.path:
            return httpx.Response(200, json={"esearchresult": {"idlist": ["123"]}})
        return httpx.Response(200, text='<PubmedArticleSet><PubmedArticle><PMID>123</PMID><ArticleTitle>A <i>trial</i> result</ArticleTitle><AbstractText>Improved by <b>0.5</b> percentage points.</AbstractText></PubmedArticle></PubmedArticleSet>')

    client_type = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs))
    workspace = Workspace(condition="condition", source_types=[SourceType.pubmed])
    result = asyncio.run(PubMedClient().fetch(workspace))[0]
    assert result.title == "A trial result"
    assert result.abstract == "Improved by 0.5 percentage points."


def test_source_diagnostics_distinguish_unavailable_from_no_matches(monkeypatch):
    import httpx
    def handler(request):
        if "clinicaltrials" in request.url.host:
            return httpx.Response(200, json={"studies": []})
        return httpx.Response(503)
    client_type = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs))
    workspace = Workspace(condition="condition", source_types=[SourceType.pubmed, SourceType.clinical_trials])
    diagnostics = {}
    assert asyncio.run(fetch_sources(workspace, diagnostics)) == []
    assert diagnostics == {"pubmed": "unavailable", "clinical_trials": "no_matches"}


def test_fda_not_found_is_no_matches_not_an_outage(monkeypatch):
    import httpx
    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": "No matches found!"}}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=transport, **kwargs))
    workspace = Workspace(condition="condition", intervention="nonexistent", source_types=[SourceType.fda_label, SourceType.fda_adverse_event])
    diagnostics = {}
    assert asyncio.run(fetch_sources(workspace, diagnostics)) == []
    assert diagnostics == {"fda_label": "no_matches", "fda_adverse_event": "no_matches"}

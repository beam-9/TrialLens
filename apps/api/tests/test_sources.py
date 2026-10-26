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


def test_clinical_trials_results_section_metadata_is_payload_scoped(monkeypatch):
    """Report what this API payload contains without treating results as indexed evidence."""
    import httpx
    import pytest

    results_cases = [
        ("absent", None, "absent"),
        ("nonempty", {"outcomeMeasuresModule": {"outcomeMeasures": [
            {"title": "HbA1c", "groups": [{"title": "Intervention", "denoms": [{"counts": [{"value": "42"}]}]}]}
        ]}}, "present"),
        ("empty", {}, "empty"),
        ("null", None, "unrecognized"),
        ("list", [{"outcome": "HbA1c", "value": "42"}], "unrecognized"),
    ]
    client_type = httpx.AsyncClient

    for case, results_section, expected_state in results_cases:
        study = {
            "protocolSection": {
                "identificationModule": {"nctId": f"NCT-{case}", "briefTitle": "Protocol title"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "designModule": {"phases": ["PHASE2"]},
                "descriptionModule": {
                    "briefSummary": "Protocol summary says the study will evaluate HbA1c.",
                    "detailedDescription": "Protocol details specify planned visits.",
                },
            }
        }
        if case != "absent":
            study["resultsSection"] = results_section

        def handler(request):
            return httpx.Response(200, json={"studies": [study]})

        monkeypatch.setattr(
            httpx, "AsyncClient",
            lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs),
        )
        workspace = Workspace(condition="condition", source_types=[SourceType.clinical_trials])
        source = asyncio.run(ClinicalTrialsClient().fetch(workspace))[0]

        assert source.status == "COMPLETED"
        assert source.abstract == "Protocol summary says the study will evaluate HbA1c. Protocol details specify planned visits."
        assert source.metadata["indexed_content"] == "protocol_descriptions"
        assert source.metadata["api_results_section_state"] == expected_state
        assert source.metadata["sections"] == {
            "Brief summary": "Protocol summary says the study will evaluate HbA1c.",
            "Detailed description": "Protocol details specify planned visits.",
        }
        # Even when the raw payload includes numeric results, this connector indexes
        # only protocol descriptions; it must not silently surface result values as findings.
        assert "42" not in source.abstract
        assert all("42" not in section for section in source.metadata["sections"].values())


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


def test_pubmed_requests_relevance_preserves_rank_and_publication_types(monkeypatch):
    import httpx
    def handler(request):
        if "esearch" in request.url.path:
            assert request.url.params["sort"] == "relevance"
            assert request.url.params["retmax"] == "5"
            assert request.url.params["term"] == "type 2 diabetes metformin"
            return httpx.Response(200, json={"esearchresult": {"idlist": ["222", "111"]}})
        assert request.url.params["id"] == "222,111"
        return httpx.Response(200, text='''<PubmedArticleSet>
          <PubmedArticle><PMID>111</PMID><ArticleTitle>Later ranked review</ArticleTitle>
            <AbstractText>Stored review abstract.</AbstractText><PublicationTypeList><PublicationType>Review</PublicationType></PublicationTypeList></PubmedArticle>
          <PubmedArticle><PMID>222</PMID><ArticleTitle>First ranked trial</ArticleTitle>
            <AbstractText>Stored randomized trial abstract.</AbstractText><PublicationTypeList><PublicationType>Randomized Controlled Trial</PublicationType><PublicationType>Journal Article</PublicationType></PublicationTypeList></PubmedArticle>
        </PubmedArticleSet>''')
    client_type = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs))
    workspace = Workspace(condition="type 2 diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    sources = asyncio.run(PubMedClient().fetch(workspace))
    assert [s.external_id for s in sources] == ["222", "111"]
    assert sources[0].metadata["publication_types"] == ["Randomized Controlled Trial", "Journal Article"]
    assert sources[1].metadata["publication_types"] == ["Review"]

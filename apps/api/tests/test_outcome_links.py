"""Exact provenance links for complete retained registry outcome packets."""
import asyncio
import json
from pathlib import Path

import httpx

from triallens.conversation import build_evidence_records
from triallens.models import RetrievedChunk, SourceType, Workspace
from triallens.rag import build_chunks
from triallens.sources import ClinicalTrialsClient
from triallens.text import normalize

FIXTURE = Path(__file__).resolve().parents[1] / "evaluation/answer_coverage/fixtures/ctgov-NCT00545844-2026-10-31.json"


def load_source(monkeypatch):
    study = json.loads(FIXTURE.read_text())
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"studies": [study]})), **kwargs))
    workspace = Workspace(condition="asthma", source_types=[SourceType.clinical_trials])
    return workspace, asyncio.run(ClinicalTrialsClient().fetch(workspace))[0]


def retrieved(source, *sections):
    by_section = {chunk.section: chunk for chunk in build_chunks([source])}
    return [RetrievedChunk(chunk_id=f"retrieved-{section}", source_id=source.id,
                           source_type=source.source_type, citation=f"ClinicalTrials.gov:{source.external_id}",
                           section=section, text=by_section[section].text, score=1)
            for section in sections]


def test_links_retained_fixture_packets_and_marks_analysis_from_raw_lines(monkeypatch):
    _, source = load_source(monkeypatch)
    chunks = retrieved(source, "Results outcome 001", "Results outcome 003")
    record = build_evidence_records([source], chunks)[0]
    assert record["outcome_links"] == [
        {"id": "Results outcome 001", "matched_passage_index": 0,
         "title": "Asthma Control", "has_reported_analysis": False},
        {"id": "Results outcome 003", "matched_passage_index": 1,
         "title": "Effectiveness of Montelukast Therapy Used in Combination With Inhaled Corticosteroids or Inhaled Corticosteroids / Long-Acting Beta 2-Agonist in Improving the Symptoms of Asthma Using the Asthma Control Questionnaire (ACQ)",
         "has_reported_analysis": True},
    ]
    assert all(record["matched_passages"][link["matched_passage_index"]] in record["matched_passages"]
               for link in record["outcome_links"])
    assert sum(len(item["text"]) + sum(map(len, item["matched_passages"])) for item in [record]) <= 28000


def test_dropped_packets_and_description_analysis_phrase_do_not_create_links(monkeypatch):
    _, source = load_source(monkeypatch)
    # The phrase occurs in a description, but there is no raw `Analysis: ` line.
    packet = source.metadata["sections"]["Results outcome 001"]
    source.metadata["sections"]["Results outcome 001"] = packet + "\nDescription: Analysis: this is not reported analysis."
    names = [f"Results outcome {i:03d}" for i in range(1, 7)]
    chunks = retrieved(source, *names)
    record = build_evidence_records([source], chunks)[0]
    assert len(record["matched_passages"]) == 4
    assert [link["id"] for link in record["outcome_links"]] == names[:4]
    assert record["outcome_links"][0]["has_reported_analysis"] is False
    assert all(link["matched_passage_index"] < 4 for link in record["outcome_links"])
    # A fragment cannot link even if a section name looks like an outcome.
    fragment = chunks[0].model_copy(update={"text": normalize(chunks[0].text)[:-20]})
    fragment_record = build_evidence_records([source], [fragment])[0]
    assert fragment_record.get("outcome_links", []) == []


def test_nonclinical_and_legacy_outcomes_never_receive_links(monkeypatch):
    _, source = load_source(monkeypatch)
    chunk = retrieved(source, "Results outcome 001")[0]
    legacy = source.model_copy(deep=True)
    legacy.metadata.pop("outcome_packet_version")
    nonclinical = source.model_copy(update={"source_type": SourceType.pubmed}, deep=True)
    assert build_evidence_records([legacy], [chunk])[0].get("outcome_links", []) == []
    assert build_evidence_records([nonclinical], [chunk])[0].get("outcome_links", []) == []

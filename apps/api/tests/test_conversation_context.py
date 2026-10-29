"""Context delivery regressions; no inference, network or workspace mutations."""
import json

from triallens import conversation
from triallens.models import Answer, EvidenceSource, RetrievedChunk, SourceType, Workspace


def source(index, text=None):
    return EvidenceSource(id=f"s{index}", workspace_id="w", source_type=SourceType.pubmed,
                          external_id=str(index), title=f"Source {index}", abstract=text or f"Source {index} background.")


def passage(item, text=None, citation=None):
    return RetrievedChunk(chunk_id=f"c{item.id}", source_id=item.id, source_type=item.source_type,
                          citation=citation or conversation.citation_for(item), text=text or item.abstract, score=0.9)


def test_ranked_later_source_reaches_both_passes_with_full_statistical_context(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(conversation, "chat_configured", lambda: True)
    sources = [source(i) for i in range(10)]
    sources[9].abstract = "Among 120 adults at week 12, the Example arm had 8% events versus 3% with placebo; the confidence interval was not reported."
    fallback = Answer(workspace_id="w", question="Give the event statistics", short_answer="Source excerpts",
                      evidence=[], citations=[], limitations=[], retrieved_chunks=[passage(sources[9])])
    contexts = []
    def completion(messages, schema):
        contexts.append(json.loads(messages[1]["content"]))
        return json.dumps({"paragraphs": ["In the 120 adults, events at week 12 occurred in 8% with Example and 3% with placebo [PubMed:9]."],
                           "cited_sources": ["PubMed:9"], "uncertainty": []})
    monkeypatch.setattr(conversation.cloudflare, "completion", completion)
    answer = conversation.ConversationService().generate(
        Workspace(id="w", condition="example", source_types=[SourceType.pubmed]), fallback.question, [], sources, fallback)
    assert answer.generation_mode == "conversational"
    assert len(contexts) == 2 and contexts[0] == contexts[1]
    assert contexts[0]["evidence"][0]["citation"] == "PubMed:9"
    record = contexts[0]["evidence"][0]
    assert sources[9].abstract in " ".join([record["text"], *record["matched_passages"]])
    assert len(contexts[0]["evidence"]) == 8


def test_scope_and_citation_mismatches_cannot_admit_or_attach_passages():
    allowed, excluded = source(1), source(99)
    records = conversation.build_evidence_records([allowed], [passage(excluded), passage(allowed, "Wrong source values", "PubMed:99")])
    assert [r["citation"] for r in records] == ["PubMed:1"]
    assert records[0]["matched_passages"] == []
    assert "Wrong source" not in json.dumps(records)


def test_context_budget_prioritizes_ranked_passage_beyond_source_prefix():
    sources = [source(i, "Background. " * 3000) for i in range(10)]
    result = "At week 24 among 50 adults: 4 events with Example versus 8 with control."
    sources[9].abstract += result
    records = conversation.build_evidence_records(sources, [passage(sources[9], result)])
    assert result in records[0]["matched_passages"]
    assert all(r["content_truncated"] for r in records)
    assert sum(len(r["text"]) + sum(map(len, r["matched_passages"])) for r in records) <= 28000
    assert len(records) == 8


def test_no_retrieval_keeps_stable_fallback_and_empty_sources_safe():
    sources = [source(i) for i in range(10)]
    records = conversation.build_evidence_records(sources, [])
    assert [r["citation"] for r in records] == [f"PubMed:{i}" for i in range(8)]
    assert conversation.build_evidence_records([], []) == []

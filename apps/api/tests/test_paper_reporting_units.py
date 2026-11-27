import json
from pathlib import Path

import pytest

from evaluation.paper_reporting_units import reporting_units_for
from evaluation.structured_attribution import (
    PassagePercentageMismatch,
    _passage_catalog,
    render_answer,
    structured_attribution_experiment,
)
from triallens import cloudflare


def _captured_records(name, case_id):
    results = Path(__file__).resolve().parents[1] / "evaluation/answer_coverage/results"
    cases = json.loads((results / name).read_text())
    return next(case["generation_context"]["evidence"] for case in cases if case["case_id"] == case_id)


def test_frozen_result_and_caption_support_keeps_numbers_with_their_own_spans():
    records = _captured_records("paper-passage-feedback-2026-11-25.json", "full-text-results")
    catalog, citations, texts = _passage_catalog(records, reporting_units=True)

    dispersion_index = next(index for index, unit in enumerate(catalog)
                            if "0.58%±0.11%" in unit.get("reported_dispersion", []))
    interval_index = next(index for index, unit in enumerate(catalog)
                          if unit.get("figure") == "Fig. 2." and unit.get("panel") == "A")
    dispersion = catalog[dispersion_index]
    interval = catalog[interval_index]
    assert dispersion["role"] == "results"
    assert "atorvastatin group" in texts[dispersion_index]
    assert not dispersion.get("reported_signed_intervals")
    assert interval["role"] == "figure_caption"
    assert any("−0.94%" in anchor for anchor in interval["reported_signed_intervals"])
    assert "LDL-C" not in texts[interval_index]
    for index in (dispersion_index, interval_index):
        entry = catalog[index]
        source = records[entry["source_index"]]
        passage = source["matched_passages"][entry["matched_passage_index"]]
        assert citations[index] == source["citation"]
        assert texts[index] == passage[entry["span_start"]:entry["span_end"]]
        assert entry["support_text"] == texts[index]

    raw = {"paragraphs": [{"text": "The contrast was -0.94% (95% CI -1.25 to -0.63).",
                           "passage_indices": [dispersion_index]}], "uncertainty": []}
    with pytest.raises(PassagePercentageMismatch):
        render_answer(json.dumps(raw), citations, passages=texts)
    raw["paragraphs"][0]["passage_indices"] = [interval_index]
    assert json.loads(render_answer(json.dumps(raw), citations, passages=texts))["cited_sources"] == [citations[interval_index]]


def test_frozen_published_correction_keeps_its_own_source_and_intact_passage():
    records = _captured_records("stoic-passage-feedback-2026-11-25.json", "stoic-corrected-counts")
    catalog, citations, texts = _passage_catalog(records, reporting_units=True)
    index = next(index for index, entry in enumerate(catalog) if entry.get("role") == "published_correction")
    entry = catalog[index]
    correction = records[entry["source_index"]]
    assert citations[index] == correction["citation"]
    assert texts[index] == correction["matched_passages"][entry["matched_passage_index"]]
    assert "span_start" not in entry


def test_ambiguous_panels_and_long_or_unlinked_text_do_not_get_split():
    caption = "Fig. 2. (A) The estimate was −1% (95% CI −2 to −0.5); (C) the other estimate was 3%."
    units = reporting_units_for(caption, "Full text figure caption 002")
    assert len(units) == 1
    assert "panel" not in units[0]
    assert units[0]["span_end"] == len(caption)
    assert reporting_units_for(caption + (" x" * 1000), "Full text figure caption 002") == []
    assert reporting_units_for(caption, "Abstract") == []


def test_support_text_budget_keeps_remaining_units_accessible_by_offsets():
    passage = "The reported change was 5% ± 2% " + ("value " * 150)
    records = [{"citation": "Paper:1",
                "matched_passages": [passage] * 4,
                "paper_passage_links": [{"matched_passage_index": index,
                                         "section": f"Full text paragraph {index} — Results"}
                                        for index in range(4)]}]
    catalog, _, validation_texts = _passage_catalog(records, reporting_units=True)
    assert sum(len(unit.get("support_text", "")) for unit in catalog) <= 3000
    assert "support_text" not in catalog[-1]
    assert catalog[-1]["span_end"] == len(passage.rstrip())
    assert validation_texts[-1] == passage.rstrip()


def test_reporting_mode_sends_exact_original_passages_with_unit_catalog(monkeypatch):
    records = _captured_records("paper-passage-feedback-2026-11-25.json", "full-text-results")
    payload = {"evidence": records}
    requests = []

    def fake_completion(messages, schema):
        requests.append((messages, schema))
        supplied = json.loads(messages[1]["content"])
        index = next(index for index, unit in enumerate(supplied["passage_catalog"])
                     if unit.get("figure") == "Fig. 2." and unit.get("panel") == "A")
        return json.dumps({"paragraphs": [{"text": "The contrast was -0.94% (95% CI -1.25 to -0.63).",
                                           "passage_indices": [index]}], "uncertainty": []})

    monkeypatch.setattr(cloudflare, "completion", fake_completion)
    with structured_attribution_experiment(True, passage_attribution=True, reporting_units=True):
        result = cloudflare.completion([{"role": "system", "content": "System."},
                                       {"role": "user", "content": json.dumps(payload)}], {})
    assert cloudflare.completion is fake_completion
    assert json.loads(result)["cited_sources"] == [records[0]["citation"]]
    messages, schema = requests[0]
    supplied = json.loads(messages[1]["content"])
    assert supplied["evidence"] == records
    assert len(supplied["passage_catalog"]) == schema["properties"]["paragraphs"]["items"]["properties"]["passage_indices"]["maxItems"]
    assert "reported_signed_intervals" in messages[0]["content"]


@pytest.mark.parametrize("passage", [
    "The Results were inconclusive.",
    " ".join(["The outcome changed by 1%±0.2%."] * 9),
    "The recorded estimates were " + ", ".join(["1%±0.2%"] * 13) + ".",
])
def test_results_without_bounded_numeric_units_keep_the_whole_passage(passage):
    section = "Full text paragraph 001 — Results"
    record = {"citation": "PubMed:1", "matched_passages": [passage],
              "paper_passage_links": [{"matched_passage_index": 0, "section": section}]}

    catalog, owners, text = _passage_catalog([record], reporting_units=True)

    assert catalog == [{"source_index": 0, "matched_passage_index": 0, "section": section}]
    assert owners == ["PubMed:1"]
    assert text == [passage]

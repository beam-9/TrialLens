import asyncio
import json
from pathlib import Path

import httpx
import pytest

from triallens.models import SourceType, Workspace
from triallens.rag import build_chunks, citation_for
from triallens.sources import ClinicalTrialsClient
from triallens.trial_design import parse_registry_design, render_registry_design, sanitize_design_fields


FIXTURES = Path(__file__).parents[1] / "evaluation" / "answer_coverage" / "fixtures"


@pytest.mark.parametrize("fixture,nct,expected", [
    ("ctgov-NCT01563029-2026-10-28.json", "NCT01563029", {
        "study_type": "INTERVENTIONAL", "allocation": "RANDOMIZED",
        "intervention_model": "PARALLEL", "primary_purpose": "TREATMENT",
        "masking": "QUADRUPLE", "enrollment_count": 597, "enrollment_type": "ACTUAL",
    }),
    ("ctgov-NCT00545844-2026-10-31.json", "NCT00545844", {
        "study_type": "INTERVENTIONAL", "allocation": "NON_RANDOMIZED",
        "intervention_model": "SINGLE_GROUP", "primary_purpose": "TREATMENT",
        "masking": "NONE", "enrollment_count": 313, "enrollment_type": "ACTUAL",
    }),
])
def test_parse_registry_design_from_ctgov_raw_fixtures(fixture, nct, expected):
    raw = json.loads((FIXTURES / fixture).read_text())
    design = raw["protocolSection"]["designModule"]
    assert parse_registry_design(design) == expected
    assert nct in raw["protocolSection"]["identificationModule"]["nctId"]


def test_observational_sparse_design_and_allocation_na_do_not_infer_control():
    canonical = parse_registry_design({
        "studyType": "OBSERVATIONAL",
        "designInfo": {"allocation": "N/A", "observationalModel": "COHORT",
                       "timePerspective": "PROSPECTIVE"},
        "enrollmentInfo": {"count": 0, "type": "ESTIMATED"},
    })
    rendered = render_registry_design(canonical)
    assert canonical == {
        "study_type": "OBSERVATIONAL", "allocation": "N/A",
        "observational_model": "COHORT", "time_perspective": "PROSPECTIVE",
        "enrollment_count": 0, "enrollment_type": "ESTIMATED",
    }
    assert "Allocation: N/A" in rendered
    assert "Observational model: COHORT" in rendered
    assert "no control" not in rendered.lower()
    assert "single-arm" not in rendered.lower()
    assert "randomized control" not in rendered.lower()
    assert "not necessarily an outcome denominator" in rendered


@pytest.mark.parametrize("raw", [None, [], "bad", {"designInfo": []},
                                  {"designInfo": {"maskingInfo": []}, "enrollmentInfo": "bad"}])
def test_malformed_registry_design_is_empty(raw):
    assert parse_registry_design(raw) == {}
    assert render_registry_design(parse_registry_design(raw)) == ""


def test_sanitizer_rejects_bool_and_out_of_range_enrollment_and_unbounded_strings():
    assert sanitize_design_fields({
        "enrollment_count": True, "allocation": "  ",
        "study_type": "x" * 121, "extra": "ignored",
    }) == {}
    assert sanitize_design_fields({"enrollment_count": -1}) == {}
    assert sanitize_design_fields({"enrollment_count": 1_000_000_001}) == {}
    assert sanitize_design_fields({"enrollment_count": 7}) == {"enrollment_count": 7}


@pytest.mark.parametrize("fixture,nct", [
    ("ctgov-NCT01563029-2026-10-28.json", "NCT01563029"),
    ("ctgov-NCT00545844-2026-10-31.json", "NCT00545844"),
])
def test_clinical_trials_indexes_design_section_with_original_citation(monkeypatch, fixture, nct):
    study = json.loads((FIXTURES / fixture).read_text())
    study["resultsSection"] = {}
    client_type = httpx.AsyncClient

    def handler(request):
        return httpx.Response(200, json={"studies": [study]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_type(
        transport=httpx.MockTransport(handler), **kwargs))
    workspace = Workspace(condition="asthma", source_types=[SourceType.clinical_trials])
    source = asyncio.run(ClinicalTrialsClient().fetch(workspace))[0]
    design = parse_registry_design(study["protocolSection"]["designModule"])
    assert source.metadata["registry_design"] == design
    assert source.metadata["sections"]["Study design"] == render_registry_design(design)
    design_chunks = [chunk for chunk in build_chunks([source]) if chunk.section == "Study design"]
    assert len(design_chunks) == 1
    assert design_chunks[0].citation == f"ClinicalTrials.gov:{nct}"
    assert design_chunks[0].citation == citation_for(source)

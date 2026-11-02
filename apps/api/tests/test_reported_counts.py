import json
from pathlib import Path

import pytest

from triallens.models import EvidenceSource, RetrievedChunk, SourceType
from triallens.reported_counts import reported_counts


FIXTURE = Path(__file__).parents[1] / "evaluation" / "answer_coverage" / "design-cohort-2026-10-31" / "with-design.json"
QUESTION = "For NCT00545844, what were the participant counts and denominators at baseline and week 8 for Asthma Control?"


def setup_data():
    blob = json.loads(FIXTURE.read_text())
    raw = blob["sources"][0]
    source = EvidenceSource.model_validate(raw)
    section, packet = next((k, v) for k, v in source.metadata["sections"].items() if k == "Results outcome 001")
    chunk = RetrievedChunk(chunk_id="c1", source_id=source.id, source_type=SourceType.clinical_trials,
                           citation=f"ClinicalTrials.gov:{source.external_id}", text=packet, score=1,
                           section=section, external_id=source.external_id)
    return source, section, packet, chunk


def test_render_source_counts_with_denominators_and_missing_without_percentages():
    source, section, _, chunk = setup_data()
    result = reported_counts(QUESTION, [source], [chunk])
    assert result and result["section"] == section
    assert "Uncontrolled: 312" in result["direct_answer"] and "Uncontrolled: 72" in result["direct_answer"]
    assert "Missing: 1" in result["direct_answer"] and "Missing: 0" in result["direct_answer"]
    assert "denominator 313 participants" in result["direct_answer"]
    assert "denominator 301 participants" in result["direct_answer"]
    assert "%" not in result["direct_answer"]
    assert "do not show which individual participants changed categories" in result["direct_answer"]


def test_generic_outcome_title_match_and_simple_preserves_values():
    source, _, _, chunk = setup_data()
    result = reported_counts(QUESTION.replace("Asthma Control", "asthma control"), [source], [chunk], simple=True)
    assert result
    assert "Singulair(R)" not in result["direct_answer"]
    assert "Controlled: 229" in result["direct_answer"]
    assert "denominator 301 participants" in result["direct_answer"]
    assert "nonrandomized" in result["direct_answer"]


def test_rejects_unrelated_mean_outcome_and_wrong_or_ambiguous_trial():
    source, _, _, chunk = setup_data()
    assert reported_counts(QUESTION.replace("Asthma Control", "MiniRQLQ mean change"), [source], [chunk]) is None
    assert reported_counts(QUESTION.replace("NCT00545844", "NCT01563029"), [source], [chunk]) is None
    assert reported_counts(QUESTION.replace("Asthma Control", "results"), [source], [chunk]) is None


def test_requires_exact_retrieved_full_packet_and_outcome_packet():
    source, section, packet, chunk = setup_data()
    assert reported_counts(QUESTION, [source], [chunk.model_copy(update={"text": packet[:100]})]) is None
    assert reported_counts(QUESTION, [source], [chunk.model_copy(update={"section": "Results outcome 001 fragment"})]) is None
    legacy = source.model_copy(update={"metadata": {**source.metadata, "outcome_packet_version": None}})
    assert reported_counts(QUESTION, [legacy], [chunk]) is None
    assert reported_counts(QUESTION, [source], [chunk.model_copy(update={"source_id": "other"})]) is None


def test_rejects_missing_design_analysis_missing_group_and_bad_values():
    source, section, packet, chunk = setup_data()
    no_design = source.model_copy(update={"metadata": {**source.metadata, "registry_design": {}}})
    assert reported_counts(QUESTION, [no_design], [chunk]) is None
    for bad in (
        packet + "\nAnalysis: statistical method=t-test",
        packet.replace("Measurement [Missing] (Participants): group=Treatment Phase (All Patients) Week 0 (id=OG000); value=1\n", ""),
        packet.replace("value=312", "value=True"),
        packet + "\nMeasurement [Extra] (Participants): group=Treatment Phase (All Patients) Week 0 (id=OG000); value=1",
        packet.replace("Denominator (Participants): group=Treatment Phase (All Patients) Week 0 (id=OG000); value=313", "Denominator (Participants): group=Treatment Phase (All Patients) Week 0 (id=OG000); value=313\nDenominator (Participants): group=Treatment Phase (All Patients) Week 0 (id=OG000); value=313"),
    ):
        changed = source.model_copy(update={"metadata": {**source.metadata, "sections": {**source.metadata["sections"], section: bad}}})
        bad_chunk = chunk.model_copy(update={"text": bad})
        assert reported_counts(QUESTION, [changed], [bad_chunk]) is None


def test_requires_explicit_count_denominator_baseline_and_week_question():
    source, _, _, chunk = setup_data()
    assert reported_counts("What happened to Asthma Control in NCT00545844?", [source], [chunk]) is None
    assert reported_counts(QUESTION.replace("baseline and ", ""), [source], [chunk]) is None
    assert reported_counts(QUESTION + " and for another outcome?", [source], [chunk]) is None


def test_category_order_matches_first_raw_measurement_order():
    source, section, packet, chunk = setup_data()
    assert packet.index("Measurement [Uncontrolled]") < packet.index("Measurement [Controlled]") < packet.index("Measurement [Missing]")
    result = reported_counts(QUESTION, [source], [chunk])
    text = result["direct_answer"]
    assert text.index("Uncontrolled:") < text.index("Controlled:") < text.index("Missing:")


def test_week_visits_must_include_week_zero_and_every_requested_week():
    source, _, _, chunk = setup_data()
    assert reported_counts(QUESTION.replace("week 8", "week 4"), [source], [chunk]) is None
    # Even with the requested week, non-visit group labels cannot stand in for visits.
    packet = chunk.text.replace("Treatment Phase (All Patients) Week 0", "Treatment Phase (All Patients) Baseline")
    packet = packet.replace("Treatment Phase (All Patients) Week 8", "Treatment Phase (All Patients) Follow-up")
    changed = source.model_copy(update={"metadata": {**source.metadata, "sections": {**source.metadata["sections"], "Results outcome 001": packet}}})
    assert reported_counts(QUESTION, [changed], [chunk.model_copy(update={"text": packet})]) is None


def test_equal_denominators_use_general_transition_caution_and_duplicate_endpoint_rejects():
    source, section, packet, chunk = setup_data()
    equal = packet.replace("group=Treatment Phase (All Patients) Week 8 (id=OG001); value=301", "group=Treatment Phase (All Patients) Week 8 (id=OG001); value=313")
    changed = source.model_copy(update={"metadata": {**source.metadata, "sections": {**source.metadata["sections"], section: equal}}})
    result = reported_counts(QUESTION, [changed], [chunk.model_copy(update={"text": equal})])
    assert result
    assert "Different group denominators" not in result["direct_answer"]
    assert "do not show whether individual participants changed categories" in result["direct_answer"]
    dup_section = "Results outcome 007"
    duplicate = source.model_copy(update={"metadata": {**source.metadata, "sections": {**source.metadata["sections"], dup_section: packet}}})
    duplicate_chunk = chunk.model_copy(update={"section": dup_section})
    assert reported_counts(QUESTION, [duplicate], [chunk, duplicate_chunk]) is None


def test_nonstring_question_and_overlong_rendered_answer_return_none():
    source, _, _, chunk = setup_data()
    assert reported_counts(None, [source], [chunk]) is None
    long_source = source.model_copy(update={"title": "Study" * 2000})
    result = reported_counts(QUESTION, [long_source], [chunk])
    assert result is None


def test_requires_exact_outcome_title_and_rejects_competing_title_or_acronym():
    source, _, _, chunk = setup_data()
    # A generic request or a competing endpoint alias must never inherit primary-outcome counts.
    assert reported_counts("What were the counts at baseline and week 8 for NCT00545844?", [source], [chunk]) is None
    acq = "For NCT00545844, give Asthma Control Questionnaire (ACQ) counts at baseline and week 8."
    assert reported_counts(acq, [source], [chunk]) is None
    longer_title = "For NCT00545844, give Asthma Control Questionnaire counts at baseline and week 8."
    assert reported_counts(longer_title, [source], [chunk]) is None
    other_full_title = "For NCT00545844, give The Mean Change in Mini Rhinoconjunctivitis Quality of Life Questionnaire (MiniRQLQ) Overall Score counts at baseline and week 8."
    assert reported_counts(other_full_title, [source], [chunk]) is None
    # The exact selected title remains eligible when the question asks for that outcome generally.
    assert reported_counts("Give Asthma Control results counts for NCT00545844 at baseline and week 8.", [source], [chunk])


@pytest.mark.parametrize("suffix", ["by race", "by BMI", "stratified by severity", "and hospitalization", "among patients with allergies", "with percentages", "and whether it is effective"])
def test_unknown_scope_qualifiers_fall_through(suffix):
    source, _, _, chunk = setup_data()
    assert reported_counts(QUESTION + " " + suffix, [source], [chunk]) is None

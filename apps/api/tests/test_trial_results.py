"""Synthetic API-v2-shaped inputs; no patient or live trial data."""

from evaluation.answer_coverage.trial_results_candidate import MAX_OUTCOMES, parse_outcome_measures


def test_formats_outcome_and_group_linked_measurements_without_calculations():
    # Synthetic shape following ClinicalTrials.gov API v2 Results outcome fields.
    payload = {"outcomeMeasuresModule": {"outcomeMeasures": [{
        "title": "Synthetic symptom score",
        "type": "Primary",
        "timeFrame": "Week 8",
        "description": "Synthetic example only.",
        "units": "score points",
        "paramType": "MEAN",
        "dispersionType": "STANDARD_DEVIATION",
        "groups": [
            {"id": "G1", "title": "Example treatment", "description": "Synthetic group."},
            {"id": "G2", "title": "Example control"},
        ],
        "denoms": [{"units": "Participants", "counts": [
            {"groupId": "G1", "value": "20"}, {"groupId": "G2", "value": "18"},
        ]}],
        "classes": [{"title": "Overall", "categories": [{"title": "Mean change", "measurements": [
            {"groupId": "G1", "value": "-2.1", "spread": "1.3", "lowerLimit": "-2.7", "upperLimit": "-1.5"},
            {"groupId": "G2", "value": "-0.4"},
        ]}]}],
        "analyses": [{"groupIds": ["G1", "G2"], "groupDescription": "Synthetic between-group comparison",
                      "paramType": "Mean Difference", "paramValue": "-1.7", "dispersionType": "95% CI",
                      "paramDispersionValue": "0.35", "statMethod": "Synthetic method",
                      "nonInferiorityType": "SUPERIORITY", "ciPct": "95", "ciLowerLimit": "-2.4",
                      "ciUpperLimit": "-1.0", "pValue": "0.01"}],
    }]}}

    sections, metadata = parse_outcome_measures(payload)
    text = sections["results.outcomeMeasures.001"]
    assert "Outcome: Synthetic symptom score" in text
    assert "Type: Primary" in text and "Time frame: Week 8" in text
    assert "Measure parameter type: MEAN" in text
    assert "Measure dispersion type: STANDARD_DEVIATION" in text
    assert "Group: Example treatment | id=G1 | description=Synthetic group." in text
    assert "Denominator (Participants): group=Example treatment (id=G1); value=20" in text
    assert "Measurement [Overall] / Mean change (score points): group=Example treatment (id=G1); value=-2.1; spread=1.3; lower limit=-2.7; upper limit=-1.5" in text
    assert "Analysis groups: Example treatment (id=G1), Example control (id=G2)" in text
    assert "Analysis: comparison=Synthetic between-group comparison; parameter=Mean Difference; parameter value=-1.7; dispersion=95% CI; parameter dispersion=0.35; statistical method=Synthetic method; non-inferiority type=SUPERIORITY; p value=0.01; CI percent=95; CI lower=-2.4; CI upper=-1.0" in text
    assert "difference" not in text.lower() or "Mean Difference" in text
    assert metadata == {"truncated": False, "omitted_outcomes": 0, "omission_reasons": {}}


def test_empty_malformed_and_unrecognized_payloads_have_no_sections():
    for value in (None, {}, [], {"outcomeMeasuresModule": None},
                  {"outcomeMeasuresModule": {"outcomeMeasures": []}},
                  {"outcomeMeasuresModule": {"outcomeMeasures": "not an array"}},
                  {"otherModule": {"outcomeMeasures": [{"title": "Not results"}]}}):
        assert parse_outcome_measures(value) == ({}, {"truncated": False, "omitted_outcomes": 0, "omission_reasons": {}})


def test_bounds_are_reported_when_outcomes_are_truncated():
    payload = {"outcomeMeasuresModule": {"outcomeMeasures": [
        {"title": f"Synthetic outcome {idx}", "groups": [{"id": "G1", "title": "Synthetic"}],
         "classes": [{"categories": [{"title": "Value", "measurements": [{"groupId": "G1", "value": str(idx)}]}]}]}
        for idx in range(MAX_OUTCOMES + 1)
    ]}}
    sections, metadata = parse_outcome_measures(payload)
    assert len(sections) == MAX_OUTCOMES
    assert metadata["truncated"] is True
    assert metadata["omission_reasons"] == {"outcome_limit": 1}


def test_skips_malformed_outcome_rows_and_does_not_use_enrollment_as_results():
    payload = {
        "protocolSection": {"designModule": {"enrollmentInfo": {"count": 999}}},
        "outcomeMeasuresModule": {"outcomeMeasures": [None, {"description": "no title", "value": 999}]},
    }
    sections, metadata = parse_outcome_measures(payload)
    assert sections == {}
    assert metadata["omitted_outcomes"] == 2
    assert metadata["omission_reasons"] == {"missing_title": 2}


def test_analysis_is_omitted_without_resolvable_comparison_groups():
    payload = {"outcomeMeasuresModule": {"outcomeMeasures": [{
        "title": "Synthetic outcome", "groups": [{"id": "G1", "title": "Treatment"}],
        "classes": [{"categories": [{"title": "Value", "measurements": [{"groupId": "G1", "value": "2"}]}]}],
        "analyses": [
            {"groupIds": ["G1", "MISSING"], "paramType": "Mean Difference", "paramValue": "999"},
            {"groupIds": ["G1"], "paramType": "Mean Difference", "paramValue": "888"},
        ],
    }]}}
    sections, _ = parse_outcome_measures(payload)
    assert "Analysis" not in sections["results.outcomeMeasures.001"]
    assert "999" not in sections["results.outcomeMeasures.001"]
    assert "888" not in sections["results.outcomeMeasures.001"]


def test_overlong_outcome_is_omitted_atomically_without_partial_numeric_text():
    long_number = "9" * 1500
    payload = {"outcomeMeasuresModule": {"outcomeMeasures": [{
        "title": "Synthetic overlong result", "groups": [{"id": "G1", "title": "Treatment"}],
        "classes": [{"categories": [{"title": "Value", "measurements": [{"groupId": "G1", "value": long_number}]}]}],
    }]}}
    sections, metadata = parse_outcome_measures(payload)
    assert sections == {}
    assert metadata["truncated"] is True
    assert metadata["omission_reasons"] == {"section_limit": 1}


def test_section_limit_and_nonfinite_numbers_are_explicitly_handled():
    payload = {"outcomeMeasuresModule": {"outcomeMeasures": [
        {"title": "Synthetic no numeric result", "groups": [{"id": "G1", "title": "Treatment"}],
         "classes": [{"categories": [{"title": "Value", "measurements": [{"groupId": "G1", "value": float("nan")}]}]}]},
        {"title": "Synthetic oversized description", "description": "d" * 1300,
         "groups": [{"id": "G1", "title": "Treatment"}],
         "classes": [{"categories": [{"title": "Value", "measurements": [{"groupId": "G1", "value": "7"}]}]}]},
    ]}}
    sections, metadata = parse_outcome_measures(payload)
    assert sections == {}
    assert metadata["omission_reasons"] == {"no_category_measurements": 1, "section_limit": 1}


def test_denominator_only_outcome_is_omitted_and_unknown_context_is_explicit():
    denominator_only = {"outcomeMeasuresModule": {"outcomeMeasures": [{
        "title": "Synthetic denominator-only outcome",
        "denoms": [{"counts": [{"groupId": "missing", "value": "12"}]}],
    }]}}
    sections, metadata = parse_outcome_measures(denominator_only)
    assert sections == {}
    assert metadata["omission_reasons"] == {"no_category_measurements": 1}

    with_measurement = {"outcomeMeasuresModule": {"outcomeMeasures": [{
        "title": "Synthetic outcome",
        "units": "",
        "groups": [{"id": "G1"}],
        "classes": [{"categories": [{"measurements": [{"groupId": "missing", "value": "4"}]}]}],
    }]}}
    sections, _ = parse_outcome_measures(with_measurement)
    text = sections["results.outcomeMeasures.001"]
    assert "Time frame: unknown" in text
    assert "Units: unknown" in text
    assert "unknown group (id=missing)" in text
    assert "unknown group title" in text


def test_duplicate_group_ids_are_unknown_for_measurement_and_invalidate_analysis():
    payload = {"outcomeMeasuresModule": {"outcomeMeasures": [{
        "title": "Synthetic outcome",
        "groups": [{"id": "G1", "title": "First"}, {"id": "G1", "title": "Second"}, {"id": "G2", "title": "Control"}],
        "classes": [{"categories": [{"measurements": [{"groupId": "G1", "value": "4"}]}]}],
        "analyses": [{"groupIds": ["G1", "G2"], "paramType": "Difference", "paramValue": "999"}],
    }]}}
    sections, _ = parse_outcome_measures(payload)
    text = sections["results.outcomeMeasures.001"]
    assert "unknown group (id=G1)" in text
    assert "Analysis" not in text
    assert "999" not in text

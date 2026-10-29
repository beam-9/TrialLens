import json
from pathlib import Path

from triallens.trial_results import MAX_PACKET_CHARS, parse_outcome_measures


FIXTURE = Path(__file__).parents[1] / "evaluation" / "answer_coverage" / "fixtures" / "ctgov-NCT01563029-2026-10-28.json"


def test_frozen_clinicaltrials_fixture_emits_all_eight_complete_outcome_packets():
    study = json.loads(FIXTURE.read_text())
    sections, metadata = parse_outcome_measures(study["resultsSection"])

    assert list(sections) == [f"Results outcome {index:03d}" for index in range(1, 9)]
    assert metadata["truncated"] is False
    assert metadata["omitted_outcomes"] == 0
    assert "outcome measures only" in metadata["scope"]
    assert all(3500 <= len(packet) <= MAX_PACKET_CHARS for packet in sections.values())

    expected = [
        ("3.3", "119", "Placebo", "9.6", "22.4"),
        ("0.128", "102", "Placebo", "0.051", "0.201"),
        ("16.5", "119", "Placebo", "0.0", "16.9"),
        ("5.1", "119", "Placebo", "3.4", "19.0"),
        ("5.0", "119", "Placebo", "0.7", "21.7"),
        ("2.7", "119", "Placebo", "10.0", "31.3"),
        ("19.0", "119", "Placebo", "-6.1", "10.2"),
        ("42", "119", "Placebo", None, None),
    ]
    for index, (measurement, denominator, group, ci_lower, ci_upper) in enumerate(expected, 1):
        packet = sections[f"Results outcome {index:03d}"]
        assert f"value={measurement}" in packet
        assert f"value={denominator}" in packet
        assert group in packet
        if ci_lower is not None:
            assert f"CI lower={ci_lower}" in packet
            assert f"CI upper={ci_upper}" in packet
        else:
            assert "CI percent=95" in packet
        # Each packet keeps the contrast's two submitted group identities together.
        assert "Analysis groups:" in packet
        assert "id=OG000" in packet

    first = sections["Results outcome 001"]
    assert "group=FF 50 µg OD (id=OG002); value=118" in first
    assert "group=FF 50 µg OD (id=OG002); value=22.8; spread=2.65" in first
    assert "Analysis groups: Placebo (id=OG000), FF 50 µg OD (id=OG002)" in first
    assert "parameter value=19.5" in first
    assert "CI lower=12.1; CI upper=26.9" in first
    assert "estimate comment=Inference for FF 100 µg versus (vs) placebo" in first


def test_complete_outcome_over_packet_limit_is_omitted_without_slicing():
    payload = {"outcomeMeasuresModule": {"outcomeMeasures": [{
        "title": "Synthetic long outcome",
        "groups": [{"id": "G1", "title": "Treatment", "description": "g" * 8200}],
        "classes": [{"categories": [{"measurements": [{"groupId": "G1", "value": "123456789"}]}]}],
    }]}}
    sections, metadata = parse_outcome_measures(payload)
    assert sections == {}
    assert metadata["omission_reasons"] == {"section_limit": 1}
    assert metadata["truncated"] is True


def test_analysis_requires_distinct_resolvable_titled_groups_and_preserves_unknown_context():
    payload = {"outcomeMeasuresModule": {"outcomeMeasures": [{
        "title": "Synthetic outcome",
        "timeFrame": "",
        "unitOfMeasure": "",
        "groups": [{"id": "G1", "title": ""}, {"id": "G1", "title": "Duplicate"}, {"id": "G2", "title": "Control"}],
        "classes": [{"categories": [{"measurements": [{"groupId": "G1", "value": "4"}]}]}],
        "analyses": [{"groupIds": ["G1", "G2"], "paramValue": "999"}],
    }]}}
    sections, _ = parse_outcome_measures(payload)
    packet = sections["Results outcome 001"]
    assert "Time frame: unknown" in packet
    assert "Units: unknown" in packet
    assert "unknown group (id=G1)" in packet
    assert "Analysis" not in packet
    assert "999" not in packet


def test_denominator_only_and_nonfinite_measurement_do_not_create_outcome_packets():
    payload = {"outcomeMeasuresModule": {"outcomeMeasures": [
        {"title": "Denominator only", "denoms": [{"counts": [{"groupId": "G1", "value": "10"}]}]},
        {"title": "Nonfinite", "classes": [{"categories": [{"measurements": [{"groupId": "G1", "value": float("inf")}]}]}]},
    ]}}
    sections, metadata = parse_outcome_measures(payload)
    assert sections == {}
    assert metadata["omission_reasons"] == {"no_category_measurements": 2}

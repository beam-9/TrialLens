from triallens.answer_checks import confidence_interval_issue


def test_flags_probability_claim_about_true_effect_with_confidence_interval():
    assert confidence_interval_issue(
        "The 95% confidence interval means there is a 95% chance that the true effect is within this range."
    )


def test_flags_likely_fixed_effect_explanation_without_explicit_probability_number():
    wording = ('The 95% confidence interval (CI) was 0.2 to 0.8 percentage points lower, '
               'indicating that the true effect is likely to fall within this range.')
    assert confidence_interval_issue(wording)
    assert confidence_interval_issue(
        'The 95% CI does not mean that the true effect is likely to fall within this range.'
    ) is None
    assert confidence_interval_issue(
        'The trial reports a confidence interval. The true effect is likely to fall within this range.'
    )
    assert confidence_interval_issue(
        'A Bayesian credible interval means the true effect is likely to fall within this range.'
    ) is None


def test_flags_fixed_parameter_in_range_for_percentage_of_repetitions():
    assert confidence_interval_issue(
        "The 95% CI indicates the true average difference lies within this range in 95% of repetitions."
    )
    assert confidence_interval_issue(
        "With the confidence interval, in 95% of repeated samples the true parameter is inside this interval."
    )
    actual_saved_canary_wording = (
        "The reported 95% confidence interval of 0.2 to 0.8 means that if the same study were repeated many times, "
        "the true average difference would fall within that range in 95% of repetitions."
    )
    assert confidence_interval_issue(actual_saved_canary_wording)


def test_does_not_flag_valid_repeated_interval_construction_explanation():
    assert confidence_interval_issue(
        "The 95% confidence interval procedure produces intervals that contain the fixed true value in 95% of repetitions."
    ) is None
    assert confidence_interval_issue(
        "Across repeated samples, 95% of constructed confidence intervals include the fixed true parameter."
    ) is None
    assert confidence_interval_issue(
        "The confidence interval procedure has this property: in 95% of repeated samples, the true value lies in a constructed interval."
    ) is None


def test_does_not_flag_negated_probability_assignment():
    assert confidence_interval_issue(
        "A 95% confidence interval is not a 95% chance that the true effect is within this range."
    ) is None
    assert confidence_interval_issue(
        "The 95% CI does not mean there is a 95% probability that the true value lies in these bounds."
    ) is None
    assert confidence_interval_issue(
        "The reported 95% CI is 0.2–0.8. This means there is not a 95% chance the true effect lies within these bounds."
    ) is None


def test_adjacent_ci_sentence_supports_anaphoric_bounds_and_affirmative_claim_survives_prior_negation():
    assert confidence_interval_issue(
        "The reported 95% CI is 0.2–0.8. This means there is a 95% chance the true effect lies within these bounds."
    )
    assert confidence_interval_issue(
        "The reported 95% CI is 0.2–0.8. This is not a 95% chance that the true effect lies in these bounds, "
        "but there is a 95% chance that the true effect lies in these bounds."
    )


def test_requires_confidence_interval_context_and_skips_bayesian_credible_intervals():
    assert confidence_interval_issue("There is a 95% chance the event occurs.") is None
    assert confidence_interval_issue(
        "The Bayesian 95% credible interval gives a 95% probability that the true effect is within this range."
    ) is None
    assert confidence_interval_issue(
        "A 95% chance that the true effect is in this range."
    ) is None


def test_invalid_ci_is_rejected_by_generation_not_just_reported(monkeypatch, tmp_path):
    import json
    from triallens import conversation
    from triallens.models import Workspace, EvidenceSource, SourceType, Answer
    monkeypatch.setenv('TRIALLENS_CHAT_PROVIDER', 'cloudflare')
    monkeypatch.setenv('TRIALLENS_USAGE_PATH', str(tmp_path/'usage.sqlite3'))
    monkeypatch.setattr(conversation, 'chat_configured', lambda: True)
    workspace = Workspace(condition='test condition', source_types=[SourceType.pubmed])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
        external_id='test', title='Reported comparison', abstract='A between-group difference was reported with a 95% confidence interval.')
    fallback = Answer(workspace_id=workspace.id, question='Explain the comparison', short_answer='Source excerpt', evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    bad = {'paragraphs': ['The 95% confidence interval means a 95% chance that the true effect lies within this range [PubMed:test].'],
           'cited_sources': ['PubMed:test'], 'uncertainty': []}
    monkeypatch.setattr(conversation.cloudflare, 'completion', lambda *args: json.dumps(bad))
    result = conversation.ConversationService().generate(workspace, fallback.question, [], [source], fallback)
    assert result.generation_mode == 'extractive'
    assert result.direct_answer != bad['paragraphs'][0]


def test_rejects_reversed_percentage_pairs_in_observed_discrepancy_answers():
    import json
    from pathlib import Path
    from triallens.answer_checks import requested_comparison_order_issue

    root = Path(__file__).parents[1] / 'evaluation/answer_coverage/results'
    for name in ('broad-pubmed', 'broad-pubmed-recheck'):
        run = json.loads((root / f'{name}-2026-11-06.json').read_text())[0]
        assert requested_comparison_order_issue(
            run['answer']['question'], run['answer']['direct_answer'], run['generation_context']['evidence']
        )


def test_comparison_order_guard_is_scoped_to_question_and_cited_source():
    from triallens.answer_checks import requested_comparison_order_issue
    records = [{'citation': 'PubMed:1', 'text': 'Reported 0.35% vs. -0.58%, respectively.', 'matched_passages': []}]
    question = 'Explain the discrepancy.'
    assert requested_comparison_order_issue(question, 'Reported 0.35% versus −0.58% [PubMed:1].', records) is None
    assert requested_comparison_order_issue(question, 'Reported -0.58% versus 0.35% [PubMed:2].', records) is None
    assert requested_comparison_order_issue('Summarize the study.', 'Reported -0.58% versus 0.35% [PubMed:1].', records) is None


def test_comparison_order_preserves_typographic_negative_signs():
    from triallens.answer_checks import requested_comparison_order_issue

    records = [{'citation': 'PubMed:1', 'text': '0.35% vs. -0.58%', 'matched_passages': []}]
    assert requested_comparison_order_issue('Explain the discrepancy', '0.35% versus ‑0.58% [PubMed:1]', records) is None
    assert requested_comparison_order_issue('Explain the discrepancy', '‑0.58% versus 0.35% [PubMed:1]', records)


def test_percentage_guard_rejects_observed_invented_safety_frequency():
    import json
    from pathlib import Path
    from triallens.answer_checks import unreported_percentage_issue

    path = Path(__file__).parents[1] / 'evaluation/answer_coverage/results/native-single-pass-2026-11-06.json'
    run = next(r for r in json.loads(path.read_text()) if r['case_id'] == 'm0-safety-frequency')
    assert unreported_percentage_issue(run['answer']['direct_answer'], run['generation_context']['evidence'])


def test_percentage_guard_preserves_ranges_and_negative_signs_and_source_scope():
    from triallens.answer_checks import unreported_percentage_issue

    records = [{'citation': 'PubMed:1', 'text': 'Reported 1–5% and −0.58%.', 'matched_passages': []},
               {'citation': 'PubMed:2', 'text': 'Reported 45%.', 'matched_passages': []}]
    assert unreported_percentage_issue('Reported 1% and 5%, and ‑0.58% [PubMed:1].', records) is None
    assert unreported_percentage_issue('Reported 45% [PubMed:1].', records)
    assert unreported_percentage_issue('Reported 45% [PubMed:2].', records) is None
    assert unreported_percentage_issue('Reported 45% [PubMed:1] [PubMed:2].', records) is None


def test_percentage_guard_handles_written_units_and_multiple_attributions():
    from triallens.answer_checks import unreported_percentage_issue

    records = [{'citation': 'PubMed:1', 'text': 'Reported 1 to 5 percent.', 'matched_passages': []},
               {'citation': 'PubMed:2', 'text': 'Reported 20%.', 'matched_passages': []}]
    assert unreported_percentage_issue('Reported 5 per cent [PubMed:1].', records) is None
    assert unreported_percentage_issue('Reported 45 percent [PubMed:1].', records)
    assert unreported_percentage_issue('Reported 99% [PubMed:1] [PubMed:2].', records)
    assert unreported_percentage_issue('Reported 5 percent and 20% [PubMed:1] [PubMed:2].', records) is None


def test_percentage_guard_recognizes_implied_units_for_adjacent_confidence_bounds():
    from triallens.answer_checks import unreported_percentage_issue

    for source in (
        'Reported −0.94% [95% CI, −1.25 to −0.63; P<0.001].',
        'Reported ‑0.94% (95% confidence interval, CI, ‑1.25–‑0.63).',
        'Reported -0.94% with a 95% confidence interval of -1.25 to -0.63.',
    ):
        records = [{'citation': 'PubMed:1', 'text': 'Original abstract.', 'matched_passages': [source]}]
        answer = 'The estimate was -0.94% with a 95% CI of -1.25% to -0.63% [PubMed:1].'
        assert unreported_percentage_issue(answer, records, require_citations=True) is None
        assert unreported_percentage_issue(answer.replace('-0.63%', '-0.64%'), records, require_citations=True)
        assert unreported_percentage_issue(answer.replace(' [PubMed:1]', ''), records, require_citations=True)


def test_percentage_guard_does_not_borrow_units_for_other_confidence_intervals():
    from triallens.answer_checks import unreported_percentage_issue

    for text, passages in (
        ('Response was 50%; blood pressure had a 95% CI 110 to 130 mmHg.', []),
        ('Response was 50% (95% CI 110 to 130.5 mmHg).', []),
        ('Response was 50% (95% CI 110 to 130.5 percentage points).', []),
        ('Response was 50% (95% CI 110 to 130.5 per cent points).', []),
        ('Response was 50%', ['[95% CI, 110 to 130].']),
    ):
        records = [{'citation': 'PubMed:1', 'text': text, 'matched_passages': passages}]
        assert unreported_percentage_issue('The lower bound was 110% [PubMed:1].', records, require_citations=True)
        assert unreported_percentage_issue('Response was 50% [PubMed:1].', records, require_citations=True) is None


def test_estimate_interval_guard_requires_the_unique_cited_sign_for_an_identical_tuple():
    from triallens.answer_checks import estimate_interval_issue

    source = {'citation': 'PubMed:1', 'text': 'Reported −0.94% [95% CI, −1.25 to −0.63; P<0.001].',
              'matched_passages': []}
    other = {'citation': 'PubMed:2', 'text': 'Reported +0.94% (95% CI −1.25 to −0.63).', 'matched_passages': []}
    reversed_sign = 'The difference was +0.94% [PubMed:1], with a 95% CI of -1.25% to -0.63%.'
    assert estimate_interval_issue(reversed_sign, [source, other])
    issue = estimate_interval_issue(
        reversed_sign.replace(", with", ". This difference, with"), [source],
    )
    assert "-0.94% (95% CI -1.25 to -0.63)" in issue
    assert estimate_interval_issue(reversed_sign.replace('+0.94%', '-0.94%'), [source]) is None
    assert estimate_interval_issue(reversed_sign.replace('-0.63%', '-0.62%'), [source]) is None
    assert estimate_interval_issue(reversed_sign.replace('[PubMed:1]', '[PubMed:1] [PubMed:2]'), [source, other]) is None
    assert estimate_interval_issue(reversed_sign.replace(' [PubMed:1]', ''), [source]) is None
    assert estimate_interval_issue(reversed_sign.replace('was +', 'was not +'), [source]) is None
    assert estimate_interval_issue(reversed_sign.replace('The difference was', 'It would be incorrect to pair'), [source]) is None
    assert estimate_interval_issue(
        'The magnitude was 0.94%. The signed difference was −0.94% (95% CI −1.25–−0.63) [PubMed:1].',
        [source],
    ) is None


def test_requested_dispersion_notes_only_surface_unambiguous_pairs_for_cited_draft_values():
    from triallens.answer_checks import requested_dispersion_notes

    records = [
        {'citation': 'PubMed:1', 'text': 'Reported 0.43%±0.07%, 0.58%±0.11% and 0.35%±0.11%.', 'matched_passages': []},
        {'citation': 'PubMed:2', 'text': 'Reported 0.58%±0.18%.', 'matched_passages': []},
        {'citation': 'PubMed:0.58%', 'text': 'Reported 0.58%±0.11%.', 'matched_passages': []},
    ]
    ask = 'Give the changes and their uncertainty.'
    notes = requested_dispersion_notes(ask, 'A decrease of 0.58% and an increase of 0.35% [PubMed:1].', records)
    assert len(notes) == 2
    assert '0.58%±0.11% [PubMed:1]' in notes[0]
    assert '0.35%±0.11% [PubMed:1]' in notes[1]
    assert not requested_dispersion_notes('Give the changes.', 'A decrease of 0.58% [PubMed:1].', records)
    assert not requested_dispersion_notes(ask, 'A decrease of 0.58%.\n\nAnother finding [PubMed:1].', records)
    assert not requested_dispersion_notes(ask, 'A decrease of 0.58% [PubMed:1] [PubMed:2].', records)
    assert not requested_dispersion_notes(ask, 'A decrease was reported [PubMed:0.58%].', records)
    assert not requested_dispersion_notes(ask, 'A decrease of 0.58% plus-minus 0.11% [PubMed:1].', records)


def test_percentage_text_in_citation_ids_is_not_an_answer_value():
    from triallens.answer_checks import unreported_percentage_issue
    records = [{'citation': 'PubMed:5%', 'text': 'Reported 10%.', 'matched_passages': []}]
    assert unreported_percentage_issue('The estimate remains uncertain [PubMed:5%].', records,
                                       require_citations=True) is None
    assert unreported_percentage_issue('Reported 5% [PubMed:5%].', records, require_citations=True)


def test_percentage_citation_id_cannot_hide_a_reversed_pair():
    from triallens.answer_checks import requested_comparison_order_issue
    records = [{'citation': 'PubMed:0.35%', 'text': '0.35% vs. -0.58%', 'matched_passages': []}]
    assert requested_comparison_order_issue('Explain the discrepancy',
        '-0.58% versus 0.35% [PubMed:0.35%].', records)
    assert requested_comparison_order_issue('Explain the discrepancy',
        '0.35% versus -0.58% [PubMed:0.35%].', records) is None


def test_attached_ci_bounds_allow_abbreviated_decimals_without_losing_sign():
    from triallens.answer_checks import estimate_interval_issue, unreported_percentage_issue
    records = [{'citation': 'PubMed:1', 'text': '-.94% [95% CI, -1.25 to -.63].', 'matched_passages': []}]
    correct = 'Estimate -0.94% (95% CI -1.25% to -0.63%) [PubMed:1].'
    assert unreported_percentage_issue(correct, records, require_citations=True) is None
    assert estimate_interval_issue(correct.replace('-0.94%', '+0.94%'), records)


def test_dispersion_attention_note_never_asserts_that_equal_values_are_the_same_outcome():
    from triallens.answer_checks import requested_dispersion_notes
    records = [{'citation': 'PubMed:1', 'text': 'Arm A changed 0.58%±0.11%; Arm B changed 0.58%.', 'matched_passages': []}]
    notes = requested_dispersion_notes('Give uncertainty.', 'Arm B changed 0.58% [PubMed:1].', records)
    assert len(notes) == 1 and 'Check whether' in notes[0]
    assert 'do not transfer dispersion' in notes[0]

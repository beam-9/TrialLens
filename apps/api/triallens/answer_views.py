"""Honest read views for answers saved before generation provenance was recorded."""
from triallens.models import Answer, AnswerTraceItem


HISTORICAL_PROVENANCE_NOTE = (
    "Historical answer: its generation context was not recorded separately from retrieval. "
    "Earlier extractive support and quality notes are hidden; citation support has not been reconstructed or verified."
)


def answer_read_view(answer: Answer) -> Answer:
    """Do not present old excerpt-answer judgments as checks on generated prose.

    The current reconciler records both context and final attribution explicitly.
    Older conversational records cannot be repaired using today's source collection:
    source content, scope and even record identities may have changed since then.
    Keep their answer and retrieval snapshots intact and expose the uncertainty.
    This function is a projection only; it never modifies the stored research record.
    """
    labels = {item.label for item in answer.answer_trace}
    no_generation = any(item.label == "Response method" and item.value == "No model generation"
                        for item in answer.answer_trace)
    if (answer.generation_mode != "conversational" or no_generation
            or {"Generation context", "Final attribution"}.issubset(labels)):
        return answer
    note = answer.generation_note
    if HISTORICAL_PROVENANCE_NOTE not in note:
        note = f"{note} {HISTORICAL_PROVENANCE_NOTE}".strip()
    return answer.model_copy(update={
        "generation_note": note,
        "evidence": [],
        "supporting_evidence": [],
        "evidence_synthesis": [],
        "facet_coverage": [],
        "evidence_map": [],
        "source_readouts": [],
        "safety_limitations": [],
        "reasoning_summary": [HISTORICAL_PROVENANCE_NOTE],
        "evidence_quality": [
            "Recorded citations identify historical attribution only. They do not establish that the cited sources support each generated claim.",
        ],
        "limitations": list(dict.fromkeys([
            "Limited to indexed source excerpts; this is research assistance, not individual clinical guidance.",
            HISTORICAL_PROVENANCE_NOTE, *answer.uncertainty,
        ])),
        "answer_trace": [AnswerTraceItem(
            label="Historical provenance", value="Not reconstructed",
            detail="Original answer text, citations and retrieved passages are retained. The original generation context is unknown.",
        )],
    })

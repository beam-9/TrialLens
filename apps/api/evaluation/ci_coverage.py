"""Opt-in coverage check for explicitly requested, unambiguous intervals."""
from contextlib import contextmanager
from decimal import Decimal
import json
import re

_NUMBER = r"[−+-]?(?:\d+(?:\.\d+)?|\.\d+)"
_INTERVAL = re.compile(
    rf"(\d{{2}}(?:\.\d+)?)\s*%\s*(?:CI|confidence interval)\s*[:=(\[]?\s*(?:(?:was|is|(?:which\s+)?ranges?)\s+(?:from\s+)?)?"
    rf"({_NUMBER})\s*(?:to|[–—,-])\s*({_NUMBER})", re.I
)


def intervals(text):
    return {
        tuple(Decimal(value.replace("−", "-")) for value in match.groups())
        for match in _INTERVAL.finditer(text)
    }


def requirement(payload):
    question = payload.get("question", "")
    history = payload.get("history", [])
    if history and re.search(r"\b(?:keep|preserv\w*|without changing)\b.*\b(?:numbers|figures)\b", question, re.I):
        question += " " + history[-1]["question"]
    if not re.search(r"\b(?:confidence interval|uncertainty)\b", question, re.I):
        return None
    records = payload.get("evidence", [])
    if len(records) != 1:
        return None
    record = records[0]
    reported = intervals(" ".join([record["text"], *record["matched_passages"]]))
    if len(reported) != 1:
        return None
    return record["citation"], next(iter(reported))


def includes_requirement(answer, required):
    citation, interval = required
    return any(
        f"[{citation}]" in paragraph and interval in intervals(paragraph)
        for paragraph in answer["paragraphs"]
    )


@contextmanager
def ci_coverage_experiment(enabled):
    if not enabled:
        yield
        return
    from triallens import conversation

    original = conversation.cloudflare.completion

    def completion(messages, schema):
        required = requirement(json.loads(messages[1]["content"]))
        if required is None or len(messages) != 4:
            return original(messages, schema)
        citation, (level, lower, upper) = required
        note = (
            f"\nCoverage check: answer the requested uncertainty using the {level}% "
            f"confidence interval {lower} to {upper}. Include it as a compact "
            f"parenthetical, such as ({level}% CI {lower} to {upper}, followed by the "
            f"reported units and direction). Cite [{citation}] exactly in the same "
            "paragraph and in cited_sources. Keep the entire source ID. Preserve "
            "the source's direction, units and comparison. Keep any synthetic-data label in the direct answer. Report the bounds as stated "
            "and omit any statement about where the true effect likely lies. "
            "Check the population against the source. State any total enrollment "
            "as the total across groups. Give per-group counts only if the source reports them."
        )
        submitted = [*messages[:-1], {**messages[-1], "content": messages[-1]["content"] + note}]
        result = original(submitted, schema)
        if not includes_requirement(json.loads(result), required):
            raise ValueError("Final answer omitted the requested cited confidence interval")
        return result

    conversation.cloudflare.completion = completion
    try:
        yield
    finally:
        conversation.cloudflare.completion = original

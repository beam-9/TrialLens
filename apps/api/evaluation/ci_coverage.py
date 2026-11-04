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


_RANDOM_ASSIGNMENT = r"(?:randomi[sz]ed|randomly assigned)"
_PARTICIPANT_COUNT = r"([1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*)"
_RANDOMIZED_TOTAL = re.compile(
    rf"\b{_PARTICIPANT_COUNT}\s+(?:adults|participants|patients)\s+"
    rf"were\s+{_RANDOM_ASSIGNMENT}\s+to\s+"
    r"(?:either\b|[^.!?;]{1,160}\bor\s+(?:a\s+)?(?:placebo|usual care|standard care|control)\b)",
    re.I,
)


def reported_randomized_total(record):
    """Recognize a source's explicit participant total at random assignment."""
    passages = [record["text"], *record["matched_passages"]]
    totals = {
        int(match.group(1).replace(",", ""))
        for passage in passages
        for match in _RANDOMIZED_TOTAL.finditer(passage)
    }
    return next(iter(totals)) if len(totals) == 1 else None


def includes_randomized_total(answer, citation, total):
    count = rf"(?<![\d,])(?:{total}|{total:,})(?![\d,])"
    people = (
        rf"{count}\s+(?:adults|participants|patients)\b"
        r"(?!\s+(?:each\b|per\s+(?:arm|group)\b|(?:in|to)\s+each\b))"
    )
    assignment = (
        rf"(?:{people}\s+(?:(?:in )?total\s+)?were\s+{_RANDOM_ASSIGNMENT}"
        rf"|{_RANDOM_ASSIGNMENT}\s+{people})"
    )
    return any(
        f"[{citation}]" in paragraph and re.search(assignment, paragraph, re.I)
        for paragraph in answer["paragraphs"]
    )


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
        payload = json.loads(messages[1]["content"])
        required = requirement(payload)
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
        total = reported_randomized_total(payload["evidence"][0])
        if total is not None:
            note += (
                f" The same source explicitly reports random assignment of {total} "
                "participants in total. Retain the design with the count and comparison "
                f"in a paragraph cited [{citation}]. For example, say that {total} "
                "participants were randomly assigned, then name the groups from the source."
            )
        submitted = [*messages[:-1], {**messages[-1], "content": messages[-1]["content"] + note}]
        result = original(submitted, schema)
        answer = json.loads(result)
        if not includes_requirement(answer, required):
            raise ValueError("Final answer omitted the requested cited confidence interval")
        if total is not None and not includes_randomized_total(answer, citation, total):
            raise ValueError("Final answer omitted the cited randomized participant total")
        return result

    conversation.cloudflare.completion = completion
    try:
        yield
    finally:
        conversation.cloudflare.completion = original

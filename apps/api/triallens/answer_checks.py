"""Narrow answer wording checks that do not claim scientific entailment."""
from __future__ import annotations

import re


_CI_CONTEXT = re.compile(r"\bconfidence intervals?\b|\b\d{1,3}\s*%\s*CI\b|\bCI\b", re.I)
_TRUE_TARGET = (
    r"(?:true|actual|underlying|fixed)\s+"
    r"(?:(?:population|average|treatment|treatment\s+average)\s+)?"
    r"(?:effect|difference|value|parameter|mean)"
)
_RANGE = r"(?:this\s+|that\s+|these\s+|the\s+|observed\s+)?(?:confidence\s+)?(?:interval|range|bounds)"
_FIXED_RANGE = r"(?:this|that|observed|reported|given|same)\s+(?:confidence\s+)?(?:interval|range|bounds)"
_ANAPHORIC_RANGE = re.compile(r"\b(?:this|that|these|those|observed)\s+(?:confidence\s+)?(?:interval|range|bounds)\b", re.I)
_PERCENT = r"\d{1,3}\s*%"
_REPETITION = r"(?:repetitions?|repeated\s+(?:samples?|studies|experiments|trials|draws|iterations)|resamples?)"

_PROBABILITY_TRUE_PARAMETER = re.compile(
    r"(?:"
    + _PERCENT
    + r"\s*(?:chance|probability|likelihood)\s+(?:that\s+)?(?:the\s+)?"
    + _TRUE_TARGET
    + r"[^.!?;]{0,100}?\b(?:is|lies|falls|remains|will\s+be)\b[^.!?;]{0,70}?\b(?:within|inside|in)\b[^.!?;]{0,35}?"
    + _RANGE
    + r"|"
    + _TRUE_TARGET
    + r"[^.!?;]{0,50}?\b(?:is|lies|falls|remains|would\s+(?:be|lie|fall)|will\s+be)\b[^.!?;]{0,60}?\b(?:within|inside|in)\b[^.!?;]{0,35}?"
    + _FIXED_RANGE
    + r"[^.!?;]{0,70}?\b(?:in|for)\s+"
    + _PERCENT
    + r"\s*(?:of\s+)?"
    + _REPETITION
    + r"|"
    + _PERCENT
    + r"\s*(?:of\s+)?"
    + _REPETITION
    + r"[^.!?;]{0,70}?"
    + _TRUE_TARGET
    + r"[^.!?;]{0,55}?\b(?:is|lies|falls|remains|would\s+(?:be|lie|fall))\b[^.!?;]{0,45}?\b(?:within|inside|in)\b[^.!?;]{0,35}?"
    + _FIXED_RANGE
    + r")",
    re.I,
)
_NEGATED_PROBABILITY = re.compile(
    r"\b(?:not|never|isn't|is\s+not|doesn't|does\s+not|cannot|can't)\b"
    r"[^.!?;]{0,45}?"
    r"(?:\d{1,3}\s*%\s*(?:chance|probability|likelihood)|"
    r"(?:chance|probability|likelihood)[^.!?;]{0,15}\d{1,3}\s*%)",
    re.I,
)
_LIKELY_FIXED_EFFECT = re.compile(
    _TRUE_TARGET
    + r"\s+(?:is\s+(?:likely|probably)\s+(?:to\s+)?(?:be|lie|fall)|"
    r"(?:likely|probably)\s+(?:lies|falls|is))\s+(?:within|inside|in)\s+"
    + _RANGE,
    re.I,
)
_NEGATED_INTERPRETATION = re.compile(
    r"\b(?:does\s+not|doesn't|cannot|can't)\s+(?:mean|imply|show)\b[^.!?;]{0,35}$", re.I,
)

CONFIDENCE_INTERVAL_ERROR = (
    "Do not describe a confidence interval as the probability that the true effect lies within the observed bounds, "
    "or as a percentage of repetitions in which the fixed effect falls within those bounds. Report the stated bounds "
    "and comparison only unless a source explains the interval's method."
)


def confidence_interval_issue(text: str) -> str | None:
    """Flag explicit CI-as-parameter-probability wording; not a semantic review.

    Correct repeated-sampling wording about 95% of constructed intervals
    containing a fixed true value is intentionally outside this detector.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for index, sentence in enumerate(sentences):
        if re.search(r"\bBayesian\b.{0,35}\bcredible interval\b", sentence, re.I):
            continue
        current_has_ci = bool(_CI_CONTEXT.search(sentence))
        prior_has_ci = index > 0 and bool(_CI_CONTEXT.search(sentences[index - 1]))
        anaphoric_prior = prior_has_ci and bool(_ANAPHORIC_RANGE.search(sentence))
        if not current_has_ci and not anaphoric_prior:
            continue
        matches = sorted([*_PROBABILITY_TRUE_PARAMETER.finditer(sentence),
                          *_LIKELY_FIXED_EFFECT.finditer(sentence)], key=lambda match: match.start())
        for match in matches:
            # Evaluate negation for this claim only; a nearby negated explanation
            # must not suppress a separate affirmative misinterpretation.
            prefix = sentence[:match.start()]
            boundaries = list(re.finditer(r";|\b(?:but|however|although|yet)\b", prefix, re.I))
            if boundaries:
                prefix = prefix[boundaries[-1].end():]
            if (_NEGATED_PROBABILITY.search(prefix + match.group(0))
                    or _NEGATED_INTERPRETATION.search(prefix)):
                continue
            return CONFIDENCE_INTERVAL_ERROR
    return None

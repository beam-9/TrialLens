"""Exact, bounded reporting units from the linked paper packets in Ask context."""

import re

from triallens.answer_checks import _PERCENT_DISPERSION, _PERCENT_ESTIMATE_CI


_FIGURE = re.compile(r"^(Fig(?:ure)?\.?\s+\d+\.?)\s+\(A\)", re.I)
_NEXT_PANEL = re.compile(r"(?<=\.)\s+(?=\(([B-Z])\)\s)")
_PANEL_TOKEN = re.compile(r"\(([A-Z])\)(?=\s)")
_RESULT_SENTENCE = re.compile(r"(?<=\.)\s+(?=(?:The|In|At|After|For|There|Compared)\b)")
_MAX_UNITS_PER_PASSAGE = 8
_MAX_UNIT_TEXT = 2000
_MAX_TUPLES_PER_UNIT = 12


def reporting_units_for(passage, section):
    """Return offsets into immutable passage text, with exact numeric anchors.

    Empty output keeps the original catalog entry. Section and figure roles
    come from the linked context, while numeric anchors are purely lexical.
    """
    starts = [0]
    role = None
    figure = None
    labels = []
    if section.startswith("Full text figure caption "):
        role = "figure_caption"
        first_panel = _FIGURE.match(passage)
        if first_panel:
            figure = first_panel[1]
            later_panels = list(_NEXT_PANEL.finditer(passage, first_panel.end()))
            letters = [match[1] for match in later_panels]
            if (letters == [chr(ord("B") + index) for index in range(len(letters))]
                    and _PANEL_TOKEN.findall(passage) == ["A", *letters]):
                starts.extend(match.end() for match in later_panels)
                labels = ["A", *letters]
    elif section.startswith("Full text paragraph ") and re.search(r" — Results\b", section, re.I):
        role = "results"
        starts.extend(match.end() for match in _RESULT_SENTENCE.finditer(passage))
    if role is None or len(starts) > _MAX_UNITS_PER_PASSAGE:
        return []

    units = []
    found_numbers = False
    for index, (start, stop) in enumerate(zip(starts, [*starts[1:], len(passage)])):
        text = passage[start:stop].rstrip()
        if not text or len(text) > _MAX_UNIT_TEXT:
            return []
        dispersion = [match[0] for match in _PERCENT_DISPERSION.finditer(text)]
        intervals = [match[0] for match in _PERCENT_ESTIMATE_CI.finditer(text)
                     if match[1].startswith(("+", "-", "−"))]
        if len(dispersion) + len(intervals) > _MAX_TUPLES_PER_UNIT:
            return []
        found_numbers |= bool(dispersion or intervals)
        unit = {"span_start": start, "span_end": start + len(text), "role": role, "section": section}
        if figure:
            unit["figure"] = figure
        if labels:
            unit["panel"] = labels[index]
        if dispersion:
            unit["reported_dispersion"] = dispersion
        if intervals:
            unit["reported_signed_intervals"] = intervals
        units.append(unit)
    return units if found_numbers else []

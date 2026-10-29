"""Bounded complete-outcome packets for ClinicalTrials.gov API v2 results.

Schema assumptions were checked against ClinicalTrials.gov's official API v2
Study Data Structure and Results Data Element Definitions (accessed 2026-10-28):
``resultsSection.outcomeMeasuresModule.outcomeMeasures`` contains outcome
objects with title/type/timeFrame/description, units, measure paramType and
dispersionType, groups, denoms, classes/categories/measurements, and analyses.
Measurement rows link through groupId; analysis records can carry groupIds,
groupDescription, statisticalMethod, paramDispersionValue, and nonInferiorityType.
Analyses are emitted only when at least two groupIds resolve to titled groups.
See https://clinicaltrials.gov/data-api/about-api/study-data-structure and
https://clinicaltrials.gov/policy/results-definitions. These are submitted
results fields; this module does not derive statistics or outcomes.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
import re
from typing import Any

MAX_OUTCOMES = 20
MAX_GROUPS = 30
MAX_VALUE_ROWS = 100
MAX_PACKET_CHARS = 8000
# Retained as an import-compatible alias; this is now a whole-packet limit.
MAX_TEXT = MAX_PACKET_CHARS

SCOPE_NOTE = (
    "Coverage: ClinicalTrials.gov outcome measures only. Participant flow, "
    "baseline characteristics, adverse events/safety tables, and other "
    "results modules are not indexed by this parser."
)


def _text(value: Any) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value


def _mapping(value: Any) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def parse_outcome_measures(results_section: Any) -> tuple[dict[str, str], dict[str, Any]]:
    """Return bounded, plain-text result sections plus truncation metadata.

    Keys are based on the API's array position (``results.outcomeMeasures.001``)
    and therefore stable for a fixed payload. Invalid or empty structures yield
    no sections. Every group-linked value carries the submitted group title/id.
    """
    module = _mapping(_mapping(results_section).get("outcomeMeasuresModule"))
    outcomes = _list(module.get("outcomeMeasures"))
    if not outcomes:
        return {}, {"truncated": False, "omitted_outcomes": 0, "omission_reasons": {}, "scope": SCOPE_NOTE}

    omitted = 0
    reasons: dict[str, int] = {}
    if len(outcomes) > MAX_OUTCOMES:
        omitted += len(outcomes) - MAX_OUTCOMES
        reasons["outcome_limit"] = len(outcomes) - MAX_OUTCOMES
    sections: dict[str, str] = {}
    for index, raw in enumerate(outcomes[:MAX_OUTCOMES], start=1):
        outcome = _mapping(raw)
        title = _text(outcome.get("title"))
        if not title:
            omitted += 1
            reasons["missing_title"] = reasons.get("missing_title", 0) + 1
            continue
        lines = [f"Outcome: {title}"]
        for label, key in (("Type", "type"), ("Time frame", "timeFrame"), ("Description", "description"),
                           ("Population", "populationDescription"), ("Reporting status", "reportingStatus")):
            value = _text(outcome.get(key))
            lines.append(f"{label}: {value or 'unknown'}")

        raw_groups = _list(outcome.get("groups"))
        if len(raw_groups) > MAX_GROUPS:
            omitted += 1
            reasons["group_limit"] = reasons.get("group_limit", 0) + 1
            continue
        group_by_id: dict[str, str] = {}
        duplicate_group_ids: set[str] = set()
        for group in raw_groups[:MAX_GROUPS]:
            group = _mapping(group)
            group_id, group_title = _text(group.get("id")), _text(group.get("title"))
            if group_id:
                if group_id in group_by_id:
                    duplicate_group_ids.add(group_id)
                group_by_id[group_id] = group_title
            description = _text(group.get("description"))
            if group_id or group_title or description:
                lines.append("Group: " + " | ".join(part for part in (
                    group_title or "unknown group title",
                    f"id={group_id}" if group_id else "",
                    f"description={description}" if description else "",
                ) if part))

        def group_label(row: Mapping) -> str:
            gid = _text(row.get("groupId"))
            title = group_by_id.get(gid, "")
            if gid and title and gid not in duplicate_group_ids:
                return f"{title} (id={gid})"
            return f"unknown group (id={gid or 'unavailable'})"

        rows_seen = 0
        measurement_rows = 0
        row_limit_exceeded = False

        def add_rows(label: str, rows: Any, value_key: str = "value", *, is_measurement: bool = False) -> None:
            nonlocal rows_seen, measurement_rows, row_limit_exceeded
            for row in _list(rows):
                if rows_seen >= MAX_VALUE_ROWS:
                    row_limit_exceeded = True
                    return
                row = _mapping(row)
                value = _text(row.get(value_key))
                if not value:
                    continue
                rows_seen += 1
                if is_measurement:
                    measurement_rows += 1
                details = [f"group={group_label(row)}", f"value={value}"]
                for key, name in (("spread", "spread"), ("lowerLimit", "lower limit"), ("upperLimit", "upper limit")):
                    item = _text(row.get(key))
                    if item:
                        details.append(f"{name}={item}")
                lines.append(f"{label}: " + "; ".join(details))

        units = _text(outcome.get("units")) or _text(outcome.get("unitOfMeasure"))
        lines.append(f"Units: {units or 'unknown'}")
        for label, key in (("Measure parameter type", "paramType"), ("Measure dispersion type", "dispersionType")):
            value = _text(outcome.get(key))
            if value:
                lines.append(f"{label}: {value}")
        for denom in _list(outcome.get("denoms")):
            denom = _mapping(denom)
            denom_units = _text(denom.get("units")) or units
            add_rows(f"Denominator ({denom_units or 'unknown units'})", denom.get("counts"))

        for class_item in _list(outcome.get("classes")):
            class_item = _mapping(class_item)
            class_title = _text(class_item.get("title"))
            for category in _list(class_item.get("categories")):
                category = _mapping(category)
                category_title = _text(category.get("title"))
                prefix = "Measurement" + (f" [{class_title}]" if class_title else "") + (f" / {category_title}" if category_title else "")
                add_rows(prefix + f" ({units or 'unknown units'})", category.get("measurements"), is_measurement=True)

        if row_limit_exceeded:
            omitted += 1
            reasons["row_limit"] = reasons.get("row_limit", 0) + 1
            continue

        for analysis in _list(outcome.get("analyses")):
            analysis = _mapping(analysis)
            raw_group_ids = analysis.get("groupIds")
            group_ids = [ _text(item) for item in raw_group_ids ] if isinstance(raw_group_ids, list) else []
            if (len(group_ids) < 2 or len(set(group_ids)) != len(group_ids)
                    or any(not gid or gid not in group_by_id or not group_by_id[gid] or gid in duplicate_group_ids for gid in group_ids)):
                continue
            params = []
            for key, name in (("groupDescription", "comparison"), ("paramType", "parameter"), ("paramValue", "parameter value"),
                              ("dispersionType", "dispersion"), ("paramDispersionValue", "parameter dispersion"),
                              ("statisticalMethod", "statistical method"), ("statisticalComment", "statistical comment"),
                              ("estimateComment", "estimate comment"),
                              ("otherAnalysisDescription", "other analysis description"),
                              ("nonInferiorityType", "non-inferiority type"), ("nonInferiorityDescription", "non-inferiority description"),
                              ("pValue", "p value"), ("pValueComment", "p value comment"),
                              ("ciPctValue", "CI percent"), ("ciNumSides", "CI sides"),
                              ("ciLowerLimit", "CI lower"), ("ciLowerLimitComment", "CI lower comment"),
                              ("ciUpperLimit", "CI upper"), ("ciUpperLimitComment", "CI upper comment")):
                value = _text(analysis.get(key))
                if value:
                    params.append(f"{name}={value}")
            if params:
                group_context = ", ".join(f"{group_by_id[gid]} (id={gid})" for gid in group_ids)
                lines.append("Analysis groups: " + group_context + "\nAnalysis: " + "; ".join(params))

        section = "\n".join(lines)
        if measurement_rows == 0:
            omitted += 1
            reasons["no_category_measurements"] = reasons.get("no_category_measurements", 0) + 1
            continue
        if len(section) > MAX_PACKET_CHARS:
            omitted += 1
            reasons["section_limit"] = reasons.get("section_limit", 0) + 1
            continue
        sections[f"Results outcome {index:03d}"] = section

    return sections, {
        "truncated": omitted > 0,
        "omitted_outcomes": omitted,
        "omission_reasons": reasons,
        "scope": SCOPE_NOTE,
    }

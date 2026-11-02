"""Conservative renderer for complete, source-rendered participant count tables."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from triallens.models import EvidenceSource, RetrievedChunk
from triallens.rag import citation_for, is_outcome_packet

_INT = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_GROUP = re.compile(r"Group: (.+?) \| id=([^|;]+)\Z")
_DENOM = re.compile(r"Denominator \(Participants\): group=(.+?) \(id=([^()]+)\); value=([^;]+)\Z")
_MEASURE = re.compile(r"Measurement \[(.+?)\] \(Participants\): group=(.+?) \(id=([^()]+)\); value=([^;]+)\Z")
_NCT = re.compile(r"\bNCT\d{8}\b", re.I)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def _integer(s: str) -> int | None:
    if not _INT.fullmatch(s):
        return None
    return int(s)


def _parse(raw: Any) -> dict | None:
    if not isinstance(raw, str) or len(raw) > 8000:
        return None
    lines = raw.splitlines()
    if any(line.startswith("Analysis:") for line in lines):
        return None
    fields: dict[str, str] = {}
    groups: dict[str, str] = {}
    denoms: dict[str, int] = {}
    values: dict[str, dict[str, int]] = defaultdict(dict)
    cats: list[str] = []
    for line in lines:
        if not line:
            continue
        if ": " in line and line.split(": ", 1)[0] in {"Outcome", "Type", "Time frame", "Description", "Population", "Reporting status", "Units", "Measure parameter type", "Measure dispersion type"}:
            key, value = line.split(": ", 1)
            if key in fields:
                return None
            fields[key] = value
            continue
        if line.startswith("Group: "):
            m = _GROUP.fullmatch(line)
            if not m or not m[1].strip() or not m[2].strip() or m[2].strip() in groups:
                return None
            groups[m[2].strip()] = m[1].strip()
            continue
        if line.startswith("Denominator ("):
            m = _DENOM.fullmatch(line)
            if not m or m[1].strip() != groups.get(m[2].strip()):
                return None
            val = _integer(m[3])
            if val is None or val <= 0 or m[2].strip() in denoms:
                return None
            denoms[m[2].strip()] = val
            continue
        if line.startswith("Measurement"):
            m = _MEASURE.fullmatch(line)
            if not m or m[2].strip() != groups.get(m[3].strip()):
                return None
            cat, gid = m[1].strip(), m[3].strip()
            val = _integer(m[4])
            if not cat or val is None or (gid in values and cat in values[gid]):
                return None
            values[gid][cat] = val
            if cat not in cats:
                cats.append(cat)
            continue
        # Known descriptive rows are accepted; all other rows mean an unsupported rendering.
        if not any(line.startswith(prefix) for prefix in ("Description:", "Population:", "Reporting status:", "Type:", "Time frame:", "Analysis groups:")):
            return None
    if fields.get("Units") != "Participants" or fields.get("Measure parameter type") != "NUMBER":
        return None
    if not fields.get("Outcome") or not fields.get("Time frame") or not (2 <= len(groups) <= 4) or len(denoms) != len(groups):
        return None
    if not (1 <= len(cats) <= 4) or set(values) != set(groups) or any(set(v) != set(cats) for v in values.values()):
        return None
    if any(v > denoms[g] for g, table in values.items() for v in table.values()):
        return None
    # Keep lines complete and reject any unconsumed or malformed Measurement/Denominator row.
    return {"fields": fields, "groups": groups, "denoms": denoms, "values": dict(values), "categories": cats}


def _raw_outcome_titles(source: EvidenceSource) -> list[str]:
    sections = source.metadata.get("sections") if isinstance(source.metadata, dict) else None
    if not isinstance(sections, dict):
        return []
    titles = []
    for section, raw in sections.items():
        if not isinstance(section, str) or not section.startswith("Results outcome ") or not isinstance(raw, str):
            continue
        match = re.search(r"(?m)^Outcome: (.+)$", raw)
        if match and match[1].strip():
            titles.append(match[1].strip())
    return titles


def _select(question: str, candidates: list[tuple[EvidenceSource, str, dict]], sources: list[EvidenceSource]) -> tuple[EvidenceSource, str, dict] | None:
    ids = {x.upper() for x in _NCT.findall(question)}
    if len(ids) != 1:
        return None
    q = _norm(question)
    matches = []
    for source, section, parsed in candidates:
        if source.external_id.upper() not in ids:
            continue
        title = parsed["fields"]["Outcome"]
        norm_title = _norm(title)
        # A title phrase is required; broad keyword overlap can choose the wrong measure.
        if norm_title not in q:
            continue
        matches.append((source, section, parsed, norm_title))
    if len(matches) != 1:
        return None
    source, section, parsed, selected_title = matches[0]
    # A deliberately narrow request grammar: unknown qualifiers, extra endpoints,
    # or subgroup language fall through to normal evidence synthesis.
    remaining = q.replace(selected_title, " ")
    remaining = _NCT.sub(" ", remaining)
    allowed = set("for what were was are is the participant participants count counts number numbers and denominator denominators at baseline week weeks results result give show report me please of in explain which treatment studied study trial comparison can tell us how many with key main limitation limitations keeping keep more simply simpler that those these this it you could would to understand plain language english without changing same".split())
    if not set(re.findall(r"[a-z]+", remaining)).issubset(allowed):
        return None
    for other_source in sources:
        if other_source.external_id.upper() not in ids:
            continue
        for other_title in _raw_outcome_titles(other_source):
            normalized_other = _norm(other_title)
            if normalized_other == selected_title:
                continue
            # Any explicit competing outcome title or its registered acronym makes the request ambiguous.
            if normalized_other in q or (f"{selected_title} questionnaire" in q and f"{selected_title} questionnaire" in normalized_other):
                return None
            for acronym in re.findall(r"\(([A-Z][A-Z0-9-]{1,})\)", other_title):
                if re.search(rf"\b{re.escape(acronym.casefold())}\b", q) and acronym.casefold() not in selected_title:
                    return None
    return source, section, parsed


def _visit_weeks_match(parsed: dict, question: str) -> bool:
    titles = list(parsed["groups"].values())
    matches = [re.fullmatch(r"(.+?)\s+Week\s+(\d+)", title, re.I) for title in titles]
    if not all(matches) or len({m[1].casefold() for m in matches if m}) != 1:
        return False
    actual = {int(m[2]) for m in matches if m}
    requested = {int(n) for n in re.findall(r"\bweek\s*(\d+)\b", question, re.I)}
    return 0 in actual and requested.issubset(actual)


def _render(source: EvidenceSource, parsed: dict, simple: bool) -> str:
    fields = parsed["fields"]
    groups = parsed["groups"]
    titles = list(groups.values())
    weeks = [re.fullmatch(r"(.*?)\s+Week\s+(\d+)", t, re.I) for t in titles]
    shorten = all(weeks) and len({m[1] for m in weeks if m}) == 1
    display = {gid: (f"Week {weeks[i][2]} ({weeks[i][1]})" if shorten else title) for i, (gid, title) in enumerate(groups.items()) for title in [title]}
    out = []
    for group_id, title in groups.items():
        label = display[group_id]
        categories = ", ".join(f"{cat}: {parsed['values'][group_id][cat]}" for cat in parsed["categories"])
        out.append(f"{label}: {categories}; denominator {parsed['denoms'][group_id]} participants")
    study = source.title
    first = (f"ClinicalTrials.gov reports {fields['Outcome']} ({fields['Time frame']}) for {study}: " if not simple else f"The registry reports these participant counts for {fields['Outcome']} ({fields['Time frame']}): ") + "; ".join(out) + "."
    unequal_denominators = len(set(parsed["denoms"].values())) > 1
    design = "This was a single-group, nonrandomized study, so the results do not establish that the treatment caused any change. "
    design += ("Different group denominators do not show which individual participants changed categories." if unequal_denominators else "Group totals do not show whether individual participants changed categories.")
    if source.metadata.get("demo") or "DEMO" in source.external_id.upper():
        first = "Demo/synthetic registry data: " + first
    brief = source.metadata.get("sections", {}).get("Brief summary", "")
    if not simple and isinstance(brief, str) and len(brief) <= 250 and len(brief.split()) <= 24:
        purpose = f" The registry describes the study as: {brief}"
    else:
        purpose = ""
    citation = citation_for(source)
    return first + purpose + f" [{citation}]\n\n" + design + f" [{citation}]"


def reported_counts(question: str, sources: list[EvidenceSource], retrieved: list[RetrievedChunk], *, simple: bool = False) -> dict | None:
    """Return a count-only answer for an explicitly requested baseline/week result table."""
    if not isinstance(question, str):
        return None
    q = _norm(question)
    if re.search(r"\banother outcome\b|\bmultiple outcomes\b", q) or not re.search(r"\b(counts?|numbers?|how many|participants)\b", q) or not re.search(r"\b(denominator|out of|baseline|week\s*\d+)\b", q):
        return None
    if not re.search(r"\bbaseline\b", q) or not re.search(r"\bweek\s*\d+\b", q):
        return None
    eligible = []
    for source in sources:
        design = source.metadata.get("registry_design") if isinstance(source.metadata, dict) else None
        if not isinstance(design, dict) or design.get("allocation") != "NON_RANDOMIZED" or design.get("intervention_model") != "SINGLE_GROUP":
            continue
        sections = source.metadata.get("sections")
        if not isinstance(sections, dict):
            continue
        for section, raw in sections.items():
            if not isinstance(section, str) or not is_outcome_packet(source, section):
                continue
            parsed = _parse(raw)
            if not parsed:
                continue
            if any(c.source_id == source.id and _norm(c.section) == _norm(section) and _norm(c.text) == _norm(raw) for c in retrieved):
                eligible.append((source, section, parsed))
    eligible = [(source, section, parsed) for source, section, parsed in eligible if _visit_weeks_match(parsed, question)]
    chosen = _select(question, eligible, sources)
    if chosen is None:
        return None
    source, section, parsed = chosen
    answer = _render(source, parsed, simple)
    if len(answer) > 9000:
        return None
    uncertainty = "Registry-reported participant counts; different group denominators do not identify individual transitions." if len(set(parsed["denoms"].values())) > 1 else "Registry-reported group totals do not identify individual participant transitions."
    return {"source_id": source.id, "citation": citation_for(source), "section": section,
            "direct_answer": answer, "uncertainty": uncertainty}

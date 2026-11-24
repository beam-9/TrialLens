"""Bounded, identity-checked JATS evidence; never interpret or calculate table values."""
from __future__ import annotations

import copy
import hashlib
import re
import xml.etree.ElementTree as ET
from collections import Counter

from triallens.text import normalize

MAX_XML_BYTES = 2 * 1024 * 1024
MAX_PARAGRAPHS = 24
MAX_PARAGRAPH_CHARS = 16000
MAX_TABLES = 6
MAX_PACKET_CHARS = 8000
MAX_TABLE_CHARS = MAX_PACKET_CHARS
MAX_CAPTIONS = 6
MAX_CAPTION_CHARS = 16000
SCOPE = (
    "Partial PMC article indexing: bounded body paragraphs, complete supported tables and figure caption text. "
    "Abstracts, references, figure images, supplementary material and unsupported tables are excluded. "
    "Missing values, arm definitions and statistics are not inferred."
)
_SKIP = {"abstract", "ref-list", "ref", "table-wrap", "table-wrap-group", "fig", "fig-group", "supplementary-material"}


def _tag(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _text(node: ET.Element | None) -> str:
    return normalize("".join(node.itertext())) if node is not None else ""


def _prose(node: ET.Element) -> str:
    parts = [node.text or ""]
    for child in node:
        if _tag(child) not in _SKIP:
            parts.append(_prose(child))
        parts.append(child.tail or "")
    # Normalize once at the outer boundary so inline numeric fragments stay joined.
    return "".join(parts)


def _caption_text(node: ET.Element) -> str:
    if _tag(node) in {"math", "tex-math", "inline-formula", "disp-formula", "alternatives",
                      "table-wrap", "table-wrap-group", "table", "thead", "tbody", "tfoot",
                      "tr", "th", "td", "colgroup", "col", "array"}:
        raise ValueError("unsupported_caption_markup")
    parts = [node.text or ""]
    for child in node:
        tag = _tag(child)
        block = tag in {"p", "title", "list", "list-item", "disp-quote", "break"}
        if tag in {"abstract", "ref-list", "ref", "supplementary-material"}:
            parts.append(child.tail or "")
            continue
        text = _caption_text(child)
        if tag in {"sup", "sub"}:
            text = f"<{tag}>{text}</{tag}>"
        parts.extend(("\n" if block else "", text, "\n" if block else "", child.tail or ""))
    return "".join(parts)


def _table_reason(wrap: ET.Element) -> str | None:
    tables = [node for node in wrap.iter() if _tag(node) == "table"]
    if len(tables) != 1:
        return "missing_or_nested_table"
    table = tables[0]
    rows = [node for node in table.iter() if _tag(node) == "tr"]
    if len(rows) < 2:
        return "missing_rows"
    cells_by_row = [[child for child in row if _tag(child) in {"th", "td"}] for row in rows]
    if any(not cells for cells in cells_by_row):
        return "missing_cells"
    for cells in cells_by_row:
        for cell in cells:
            if any(cell.get(attr, "1") != "1" for attr in ("rowspan", "colspan")):
                return "merged_cells"
            if any(_tag(node) in {"table", "tr"} for node in cell.iter() if node is not cell):
                return "nested_cells"
    if len({len(cells) for cells in cells_by_row}) != 1:
        return "ragged_rows"
    if any(_tag(cell) != "th" or not _text(cell) for cell in cells_by_row[0]):
        return "missing_column_headers"
    return None


def parse_paper_text(xml: bytes, expected_pmid: str, expected_pmcid: str) -> tuple[dict[str, str], dict]:
    """Return source sections and audit metadata, or empty sections with a reason.

    Table packets contain original semantic XML, preserving header/cell positions,
    labels, inline markup and footnotes together; no arm or statistic is derived.
    Figure packets contain the label and complete supported caption text, with
    explicit sup/sub notation; unsupported formula/table markup is omitted whole.
    """
    meta = {"status": "unavailable", "scope": SCOPE, "partial_indexing": True}

    def unavailable(reason: str) -> tuple[dict[str, str], dict]:
        return {}, {**meta, "reason": reason}

    if not isinstance(xml, bytes) or len(xml) > MAX_XML_BYTES:
        return unavailable("oversized_or_invalid_xml")
    meta["xml_sha256"] = hashlib.sha256(xml).hexdigest()
    # Reject UTF-16/32 so declaration scanning sees every markup byte. External
    # declarations are removed, never resolved; internal subsets/entities fail closed.
    if b"\x00" in xml or re.search(br"<!\s*ENTITY\b", xml, re.I):
        return unavailable("unsafe_xml_declaration")
    parse_xml = xml
    declarations = list(re.finditer(br"<!\s*DOCTYPE\b[^>]*>", xml, re.I))
    if re.search(br"<!\s*DOCTYPE\b", xml, re.I):
        quoted = br"(?:\"[^\"<>\[\]]*\"|'[^'<>\[\]]*')"
        external = br"<!DOCTYPE\s+article\s+(?:SYSTEM\s+" + quoted + br"|PUBLIC\s+" + quoted + br"\s+" + quoted + br")\s*>"
        if len(declarations) != 1 or not re.fullmatch(external, declarations[0].group(), re.I):
            return unavailable("unsafe_xml_declaration")
        declaration = declarations[0]
        parse_xml = xml[:declaration.start()] + xml[declaration.end():]
    try:
        root = ET.fromstring(parse_xml)
    except (ET.ParseError, ValueError, LookupError):
        return unavailable("malformed_xml")
    pending = [(root, 0)]
    while pending:
        node, depth = pending.pop()
        if depth > 64:
            return unavailable("xml_nesting_limit")
        pending.extend((child, depth + 1) for child in node)
    articles = [root] if _tag(root) == "article" else [node for node in root if _tag(node) == "article"]
    if len(articles) != 1:
        return unavailable("missing_or_multiple_articles")
    article = articles[0]
    front = next((node for node in article if _tag(node) == "front"), None)
    article_meta = next((node for node in front if _tag(node) == "article-meta"), None) if front is not None else None
    if article_meta is None:
        return unavailable("missing_article_metadata")
    ids = {}
    for kind in ("pmid", "pmc", "pmcid"):
        values = [_text(node) for node in article_meta if _tag(node) == "article-id" and node.get("pub-id-type") == kind]
        if len(values) > 1 or (values and not values[0]):
            return unavailable("missing_or_ambiguous_article_ids")
        if values:
            ids[kind] = values[0]
    if "pmid" not in ids or not ({"pmc", "pmcid"} & ids.keys()):
        return unavailable("missing_or_ambiguous_article_ids")
    # PMC JATS exports use either numeric pmc or prefixed pmcid identifiers.
    pmcids = {value if value.startswith("PMC") else "PMC" + value
              for kind, value in ids.items() if kind in {"pmc", "pmcid"}}
    if len(pmcids) != 1:
        return unavailable("article_identity_mismatch")
    actual_pmcid = pmcids.pop()
    if (not re.fullmatch(r"[0-9]+", expected_pmid)
            or not re.fullmatch(r"PMC[0-9]+", expected_pmcid)
            or ids["pmid"] != expected_pmid or actual_pmcid != expected_pmcid):
        return unavailable("article_identity_mismatch")
    meta.update(pmid=expected_pmid, pmcid=expected_pmcid)
    licenses = [node for node in article_meta.iter() if _tag(node) == "license"]
    links = list(dict.fromkeys(value for node in licenses for element in node.iter()
                               for key, value in element.attrib.items() if key.rsplit("}", 1)[-1] == "href"))
    license_text = normalize(" ".join(_text(node) for node in licenses))
    meta["license"] = {"text": license_text[:2000], "links": [link[:500] for link in links[:4]]}
    meta["license_missing"] = not bool(license_text or links)
    meta["license_truncated"] = len(license_text) > 2000 or len(links) > 4 or any(len(link) > 500 for link in links[:4])
    body = next((node for node in article if _tag(node) == "body"), None)
    if body is None:
        return unavailable("missing_body")
    sections: dict[str, str] = {}
    caption_labels: dict[str, str] = {}
    reasons: Counter = Counter()
    paragraph_count = table_count = paragraph_chars = omitted_paragraphs = omitted_tables = 0
    paragraph_candidates: list[tuple[int, tuple[str, ...], str]] = []
    table_ordinal = 0
    caption_count = caption_chars = omitted_captions = caption_ordinal = 0

    def visit_embedded(node: ET.Element, headings: tuple[str, ...]) -> None:
        for child in node:
            tag = _tag(child)
            if tag in {"table-wrap", "table-wrap-group", "fig", "fig-group"}:
                visit(child, headings)
            elif tag not in _SKIP:
                visit_embedded(child, headings)

    def visit(node: ET.Element, headings: tuple[str, ...] = ()) -> None:
        nonlocal table_count, omitted_tables, table_ordinal
        nonlocal caption_count, caption_chars, omitted_captions, caption_ordinal
        tag = _tag(node)
        captions = [child for child in node if _tag(child) == "caption"] if tag in {"fig", "fig-group"} else []
        if tag == "fig" or (tag == "fig-group" and captions):
            caption_ordinal += 1
            labels = [child for child in node if _tag(child) == "label"]
            caption = label = ""
            reason = None
            if len(captions) != 1:
                reason = "missing_or_ambiguous_caption"
            elif len(labels) > 1:
                reason = "ambiguous_caption_label"
            else:
                try:
                    caption = "\n".join(filter(None, (normalize(line) for line in _caption_text(captions[0]).splitlines())))
                    label = normalize(_caption_text(labels[0])) if labels else ""
                except ValueError:
                    reason = "unsupported_caption_markup"
            packet = "\n".join(filter(None, (label, caption)))
            if reason is None:
                if not caption:
                    reason = "missing_or_ambiguous_caption"
                elif len(packet) > MAX_PACKET_CHARS:
                    reason = "caption_size_limit"
                elif caption_count >= MAX_CAPTIONS:
                    reason = "caption_count_limit"
                elif caption_chars + len(packet) > MAX_CAPTION_CHARS:
                    reason = "caption_total_size_limit"
            if reason:
                omitted_captions += 1
                reasons[reason] += 1
            else:
                caption_count += 1
                caption_chars += len(packet)
                section = f"Full text figure caption {caption_ordinal:03d}"
                sections[section] = packet
                if labels:
                    caption_labels[section] = label
            if tag == "fig":
                return
        if tag == "fig-group":
            for child in node:
                if _tag(child) in {"fig", "fig-group"}:
                    visit(child, headings)
            return
        if tag == "table-wrap":
            table_ordinal += 1
            complete_table = copy.deepcopy(node)
            complete_table.tail = None
            packet = ET.tostring(complete_table, encoding="unicode")
            reason = _table_reason(node)
            if reason is None and len(packet) > MAX_TABLE_CHARS:
                reason = "table_size_limit"
            if reason is None and table_count >= MAX_TABLES:
                reason = "table_count_limit"
            if reason:
                omitted_tables += 1
                reasons[reason] += 1
            else:
                table_count += 1
                sections[f"Full text table {table_ordinal:03d}"] = packet
            return
        if tag in _SKIP - {"table-wrap-group", "fig-group"}:
            return
        if tag == "sec":
            title = next((_text(child) for child in node if _tag(child) == "title"), "")
            if title:
                headings = (*headings, title[:240])
        if tag == "p":
            text = normalize(_prose(node))
            if text:
                paragraph_candidates.append((len(paragraph_candidates) + 1, headings, text))
            # Embedded evidence stays separate from the surrounding prose.
            visit_embedded(node, headings)
            return
        for child in node:
            visit(child, headings)

    visit(body)
    # JATS commonly relocates body-referenced tables and figures into article floats.
    for floats in article:
        if _tag(floats) == "floats-group":
            for child in floats:
                if _tag(child) in {"table-wrap", "table-wrap-group", "fig", "fig-group"}:
                    visit(child)

    def paragraph_priority(item: tuple[int, tuple[str, ...], str]) -> tuple[int, int]:
        ordinal, headings, _ = item
        heading = " / ".join(headings)
        priority = next((rank for rank, pattern in enumerate((r"\bresults?\b", r"\bmethods?\b", r"\bdiscussion\b"))
                         if re.search(pattern, heading, re.I)), 3)
        return priority, ordinal

    for ordinal, headings, text in sorted(paragraph_candidates, key=paragraph_priority):
        if (paragraph_count >= MAX_PARAGRAPHS or len(text) > MAX_PACKET_CHARS
                or paragraph_chars + len(text) > MAX_PARAGRAPH_CHARS):
            omitted_paragraphs += 1
            reasons["paragraph_limit"] += 1
            continue
        paragraph_count += 1
        paragraph_chars += len(text)
        label = " / ".join(headings)[:240] or "Body"
        sections[f"Full text paragraph {ordinal:03d} — {label}"] = text
    meta.update(status="available" if sections else "unavailable", indexed_paragraphs=paragraph_count,
                indexed_tables=table_count, omitted_paragraphs=omitted_paragraphs,
                omitted_tables=omitted_tables, omission_reasons=dict(reasons),
                indexed_captions=caption_count, omitted_captions=omitted_captions,
                caption_labels=caption_labels,
                caption_sections=[key for key in sections if key.startswith("Full text figure caption ")],
                table_sections=[key for key in sections if key.startswith("Full text table ")],
                paragraph_sections=[key for key in sections if key.startswith("Full text paragraph ")])
    if not sections:
        meta["reason"] = "no_supported_body_content"
    return sections, meta

"""Evaluation-only paragraph attribution over the unchanged evidence array."""
from contextlib import contextmanager
import json
import re
from unittest.mock import patch


FORMAT = """
Use this output format in place of all earlier citation and JSON formatting rules.
Return only JSON with paragraphs (1–5 entries) and uncertainty (0–3 entries).
Each entry is an object with text (one line of prose) and source_indices
(an array of distinct integers). Each index is the zero-based position in the
supplied evidence array: 0 is the first record and 1 is the second. Select only
records that support the claims in that entry. Every paragraph in a sourced
answer needs its own source_indices. Use a separate paragraph when a claim
needs different sources. Cite numerical limitations in their uncertainty entry
using an index also cited in paragraphs. Do not put citation markers or square
brackets in text. Write confidence intervals in parentheses with "to" between
bounds. If the evidence cannot answer at all, say what you cannot verify from
the excerpts, leave all source_indices empty, and return an empty uncertainty list.
"""
PLAIN_TEXT = r"^[^\[\]【】［］\r\n]+$"
PASSAGE_FORMAT = """
The output uses passage_indices instead of source_indices. Each integer
selects an exact support from the passage_catalog in the evidence request,
using its zero-based position in that catalog. The catalog points to a source
index and either a field or an element of matched_passages. Read those exact
supports as data. Choose the passage containing the reported numbers, groups,
endpoint and uncertainty. Split a paragraph if its claims require different
supports. Use content_scope for claims about what the excerpts cover.
"""


class PassagePercentageMismatch(ValueError):
    """A reported percentage cannot be checked against the selected passage."""


def attribution_schema(source_count, index_field="source_indices"):
    indices = {"type": "array", "items": {"type": "integer"}, "maxItems": source_count}
    if source_count:
        indices["items"]["enum"] = list(range(source_count))
    entry = {
        "type": "object",
        "properties": {"text": {"type": "string", "pattern": PLAIN_TEXT}, index_field: indices},
        "required": ["text", index_field],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "paragraphs": {"type": "array", "items": entry, "minItems": 1, "maxItems": 5},
            "uncertainty": {"type": "array", "items": entry, "maxItems": 3},
        },
        "required": ["paragraphs", "uncertainty"],
        "additionalProperties": False,
    }


def _unique_keys(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate structured answer key")
    return result


def render_answer(raw, citations, *, passages=None):
    index_field = "passage_indices" if passages is not None else "source_indices"
    response = json.loads(raw, object_pairs_hook=_unique_keys)
    if not isinstance(response, dict) or response.keys() != {"paragraphs", "uncertainty"}:
        raise ValueError("Invalid structured answer")
    paragraphs = response["paragraphs"]
    uncertainty = response["uncertainty"]
    if not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= 5:
        raise ValueError("Invalid structured paragraphs")
    if not isinstance(uncertainty, list) or len(uncertainty) > 3:
        raise ValueError("Invalid structured uncertainty")

    def render(entry):
        if not isinstance(entry, dict) or entry.keys() != {"text", index_field}:
            raise ValueError("Invalid attributed entry")
        prose = entry["text"]
        indices = entry[index_field]
        if not isinstance(prose, str) or not prose.strip() or not re.fullmatch(PLAIN_TEXT, prose):
            raise ValueError("Invalid attributed prose")
        if (not isinstance(indices, list)
                or any(type(index) is not int or not 0 <= index < len(citations) for index in indices)
                or len(indices) != len(set(indices))):
            raise ValueError("Invalid evidence indices")
        owners = list(dict.fromkeys(citations[index] for index in indices))
        rendered = " ".join([prose.strip(), *(f"[{owner}]" for owner in owners)])
        if passages is not None and indices:
            from triallens.answer_checks import estimate_interval_issue, unreported_percentage_issue

            scoped = {owner: {"citation": owner, "text": "", "matched_passages": []} for owner in owners}
            for index in indices:
                scoped[citations[index]]["matched_passages"].append(passages[index])
            if (estimate_interval_issue(rendered, list(scoped.values()))
                    or unreported_percentage_issue(rendered, list(scoped.values()), require_citations=True)):
                raise PassagePercentageMismatch("Percentage is inconsistent with the selected passages")
        return rendered, owners

    rendered_paragraphs = [render(entry) for entry in paragraphs]
    rendered_uncertainty = [render(entry) for entry in uncertainty]
    cited = dict.fromkeys(owner for _, owners in rendered_paragraphs for owner in owners)
    if cited and any(not owners for _, owners in rendered_paragraphs):
        raise ValueError("Missing paragraph attribution")
    if (uncertainty and not cited
            or any(owner not in cited for _, owners in rendered_uncertainty for owner in owners)):
        raise ValueError("Invalid uncertainty attribution")
    return json.dumps({
        "paragraphs": [text for text, _ in rendered_paragraphs],
        "cited_sources": list(cited),
        "uncertainty": [text for text, _ in rendered_uncertainty],
    }, ensure_ascii=False)


def _passage_catalog(records):
    catalog, citations, texts = [], [], []
    for source_index, record in enumerate(records):
        fields = [({"field": field}, record.get(field)) for field in ("text", "content_scope")]
        fields.extend(
            ({"matched_passage_index": index}, passage)
            for index, passage in enumerate(record.get("matched_passages", []))
        )
        for location, passage in fields:
            if isinstance(passage, str) and passage.strip():
                catalog.append({"source_index": source_index, **location})
                citations.append(record["citation"])
                texts.append(passage)
    return catalog, citations, texts


@contextmanager
def structured_attribution_experiment(enabled, *, passage_attribution=False):
    if not enabled:
        yield
        return
    from triallens import cloudflare
    original = cloudflare.completion

    def completion(messages, _schema):
        payload = json.loads(messages[1]["content"])
        citations = [record["citation"] for record in payload["evidence"]]
        revision = len(messages) == 4
        submitted = list(messages)
        format_rules = FORMAT
        index_field = "source_indices"
        passages = None
        if passage_attribution:
            catalog, citations, passages = _passage_catalog(payload["evidence"])
            payload["passage_catalog"] = catalog
            submitted[1] = {**messages[1], "content": json.dumps(payload, ensure_ascii=False)}
            format_rules = FORMAT.replace("source_indices", "passage_indices")
            format_rules = format_rules.replace(
                "supplied evidence array: 0 is the first record and 1 is the second.",
                "passage_catalog: 0 is the first entry and 1 is the second.",
            ) + PASSAGE_FORMAT
            index_field = "passage_indices"
        submitted[0] = {**messages[0], "content": messages[0]["content"] + format_rules}
        if revision:
            submitted[-1] = {
                **messages[-1],
                "content": messages[-1]["content"]
                + "\nThe draft may use server-rendered citation markers and a different schema. "
                "Rebuild the response from the evidence if the draft is unavailable."
                + format_rules,
            }
        raw = original(submitted, attribution_schema(len(citations), index_field))
        try:
            return render_answer(raw, citations, passages=passages)
        except (ValueError, TypeError) as error:
            if revision:
                raise
            if isinstance(error, PassagePercentageMismatch):
                return json.dumps({"draft_validation": (
                    "A percentage or attached interval was inconsistent with its selected passage. "
                    "Find the exact Results or caption passage supporting each numerical sentence. "
                    "Separate results and caption estimates when their supports differ."
                )})
            # Preserve the original second-pass opportunity on a rejected draft.
            return "{}"

    with patch.object(cloudflare, "completion", completion):
        yield

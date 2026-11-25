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


def attribution_schema(source_count):
    indices = {"type": "array", "items": {"type": "integer"}, "maxItems": source_count}
    if source_count:
        indices["items"]["enum"] = list(range(source_count))
    entry = {
        "type": "object",
        "properties": {"text": {"type": "string", "pattern": PLAIN_TEXT}, "source_indices": indices},
        "required": ["text", "source_indices"],
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


def render_answer(raw, citations):
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
        if not isinstance(entry, dict) or entry.keys() != {"text", "source_indices"}:
            raise ValueError("Invalid attributed entry")
        prose = entry["text"]
        indices = entry["source_indices"]
        if not isinstance(prose, str) or not prose.strip() or not re.fullmatch(PLAIN_TEXT, prose):
            raise ValueError("Invalid attributed prose")
        if (not isinstance(indices, list)
                or any(type(index) is not int or not 0 <= index < len(citations) for index in indices)
                or len(indices) != len(set(indices))):
            raise ValueError("Invalid evidence indices")
        markers = [f"[{citations[index]}]" for index in indices]
        return " ".join([prose.strip(), *markers])

    rendered_paragraphs = [render(entry) for entry in paragraphs]
    rendered_uncertainty = [render(entry) for entry in uncertainty]
    cited = dict.fromkeys(index for entry in paragraphs for index in entry["source_indices"])
    if cited and any(not entry["source_indices"] for entry in paragraphs):
        raise ValueError("Missing paragraph attribution")
    if (uncertainty and not cited
            or any(index not in cited for entry in uncertainty for index in entry["source_indices"])):
        raise ValueError("Invalid uncertainty attribution")
    return json.dumps({
        "paragraphs": rendered_paragraphs,
        "cited_sources": [citations[index] for index in cited],
        "uncertainty": rendered_uncertainty,
    }, ensure_ascii=False)


@contextmanager
def structured_attribution_experiment(enabled):
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
        submitted[0] = {**messages[0], "content": messages[0]["content"] + FORMAT}
        if revision:
            submitted[-1] = {
                **messages[-1],
                "content": messages[-1]["content"]
                + "\nThe draft may use server-rendered citation markers and a different schema. "
                "Rebuild the response from the evidence if the draft is unavailable."
                + FORMAT,
            }
        raw = original(submitted, attribution_schema(len(citations)))
        try:
            return render_answer(raw, citations)
        except (ValueError, TypeError):
            if revision:
                raise
            # Preserve the original second-pass opportunity on a rejected draft.
            return "{}"

    with patch.object(cloudflare, "completion", completion):
        yield

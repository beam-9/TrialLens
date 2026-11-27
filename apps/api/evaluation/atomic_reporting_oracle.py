"""Offline rendering control for three frozen ATOMIC benchmark cases.

The typed readings were transcribed from the frozen source. This control
does not extract facts from arbitrary articles or score a generated answer.
"""
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json

from triallens.text import normalize


_SNAPSHOT_SHA256 = "c4259794e5dd8d8ed1f768192edf17f976b9b7ec33a8b3d3a93dadf6f95cbd83"
_CITATION = "PubMed:38763510"
_RESULTS = "Full text paragraph 019 — RESULTS / Changes in HbA1c and LDL-C levels after 16 weeks of treatment"
_FIGURE = "Full text figure caption 002"


@dataclass(frozen=True)
class ArmEstimate:
    arm: str
    change: Decimal
    plus_minus: Decimal


@dataclass(frozen=True)
class SignedContrast:
    first_arm: str
    second_arm: str
    estimate: Decimal
    confidence_level: int
    lower: Decimal
    upper: Decimal


_ARMS = (
    ArmEstimate("metformin plus atorvastatin", Decimal("-0.58"), Decimal("0.11")),
    ArmEstimate("atorvastatin alone", Decimal("0.35"), Decimal("0.11")),
)
_CONTRAST = SignedContrast(_ARMS[0].arm, _ARMS[1].arm, Decimal("-0.94"), 95, Decimal("-1.25"), Decimal("-0.63"))
_RESULTS_GAP = Decimal("0.94")
_WEEK = 16


def _verify_support(record: dict, sections: dict, section: str) -> None:
    indices = [
        link.get("matched_passage_index")
        for link in record.get("paper_passage_links", [])
        if link.get("section") == section
    ]
    passages = record.get("matched_passages", [])
    if len(indices) != 1 or type(indices[0]) is not int or not 0 <= indices[0] < len(passages):
        raise ValueError(f"Missing or ambiguous selected support: {section}")
    # The evidence builder collapses whitespace in linked caption paragraphs.
    if passages[indices[0]] != normalize(sections[section]):
        raise ValueError(f"Selected support differs from the frozen source: {section}")


def render_atomic_oracle(case_id: str, evidence: list[dict], snapshot_bytes: bytes) -> str:
    """Render only facts with exact current, linked support from the frozen paper."""
    if case_id not in {"full-text-results", "full-text-simplify", "caption-interval"}:
        raise ValueError("Case is outside the frozen numerical rendering control")
    if hashlib.sha256(snapshot_bytes).hexdigest() != _SNAPSHOT_SHA256:
        raise ValueError("ATOMIC snapshot hash mismatch")
    source, = json.loads(snapshot_bytes)["sources"]
    records = [record for record in evidence if record.get("citation") == _CITATION]
    if len(records) != 1 or records[0].get("source_type") != source["source_type"]:
        raise ValueError("Missing or ambiguous ATOMIC evidence owner")
    if records[0].get("content_truncated") is not True:
        raise ValueError("Expected the partial ATOMIC article index")

    sections = source["metadata"]["sections"]
    _verify_support(records[0], sections, _FIGURE)
    paragraphs = []
    if case_id != "caption-interval":
        _verify_support(records[0], sections, _RESULTS)
        arm_results = []
        for arm in _ARMS:
            direction = "fell" if arm.change < 0 else "rose"
            arm_results.append(f"HbA1c {direction} {abs(arm.change)}% ± {arm.plus_minus}% with {arm.arm}")
        paragraphs.append(
            f"At {_WEEK} weeks, the Results report {' and '.join(arm_results)}. "
            f"They give a difference magnitude of {_RESULTS_GAP}%. [{_CITATION}]"
        )
    contrast = _CONTRAST
    paragraphs.append(
        f"Figure 2A compares the {_WEEK}-week least-squares mean percent change from baseline "
        f"for {contrast.first_arm} minus {contrast.second_arm}. The signed contrast was "
        f"{contrast.estimate}% ({contrast.confidence_level}% CI {contrast.lower} to {contrast.upper}). "
        f"The combination group had a greater reduction in this measure. [{_CITATION}]"
    )
    paragraphs.append(
        f"The index includes the abstract and selected article passages, including figure captions. "
        f"Article coverage is partial. [{_CITATION}]"
    )
    return "\n\n".join(paragraphs)

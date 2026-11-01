"""Safe extraction and rendering of ClinicalTrials.gov design metadata."""

from __future__ import annotations

from collections.abc import Mapping


_STRING_FIELDS = (
    "study_type",
    "allocation",
    "intervention_model",
    "observational_model",
    "time_perspective",
    "primary_purpose",
    "masking",
    "enrollment_type",
)


def sanitize_design_fields(value: object) -> dict:
    """Return only whitelisted, bounded fields with safe primitive values."""
    if not isinstance(value, Mapping):
        return {}
    clean: dict = {}
    for field in _STRING_FIELDS:
        item = value.get(field)
        if isinstance(item, str):
            item = item.strip()
            if item and len(item) <= 120:
                clean[field] = item
    count = value.get("enrollment_count")
    if type(count) is int and 0 <= count <= 1_000_000_000:
        clean["enrollment_count"] = count
    return clean


def parse_registry_design(raw_designModule: object) -> dict:
    """Extract explicit study design fields from a registry designModule."""
    if not isinstance(raw_designModule, Mapping):
        return {}
    info = raw_designModule.get("designInfo")
    info = info if isinstance(info, Mapping) else {}
    masking_info = info.get("maskingInfo")
    masking_info = masking_info if isinstance(masking_info, Mapping) else {}
    enrollment = raw_designModule.get("enrollmentInfo")
    enrollment = enrollment if isinstance(enrollment, Mapping) else {}
    raw = {
        "study_type": raw_designModule.get("studyType"),
        "allocation": info.get("allocation"),
        "intervention_model": info.get("interventionModel"),
        "observational_model": info.get("observationalModel"),
        "time_perspective": info.get("timePerspective"),
        "primary_purpose": info.get("primaryPurpose"),
        "masking": masking_info.get("masking"),
        "enrollment_count": enrollment.get("count"),
        "enrollment_type": enrollment.get("type"),
    }
    return sanitize_design_fields(raw)


def render_registry_design(canonical: object) -> str:
    """Render explicit registry values without interpreting missing fields."""
    fields = sanitize_design_fields(canonical)
    if not fields:
        return ""
    labels = (
        ("study_type", "Study type"),
        ("allocation", "Allocation"),
        ("intervention_model", "Intervention model"),
        ("observational_model", "Observational model"),
        ("time_perspective", "Time perspective"),
        ("primary_purpose", "Primary purpose"),
        ("masking", "Masking"),
    )
    lines = [f"{label}: {fields[key]}" for key, label in labels if key in fields]
    enrollment = []
    if "enrollment_count" in fields:
        enrollment.append(str(fields["enrollment_count"]))
    if "enrollment_type" in fields:
        enrollment.append(fields["enrollment_type"])
    if enrollment:
        lines.append("Registered enrollment: " + " ".join(enrollment)
                     + " (registered count, not necessarily an outcome denominator).")
    return "\n".join(lines)

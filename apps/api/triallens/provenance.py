"""Stable source-content identities; timestamps and local IDs are not revisions."""
from __future__ import annotations
import hashlib
import json
from triallens.models import EvidenceSource


def source_revision(source: EvidenceSource) -> str:
    values = source.model_dump(mode='json', exclude={'id', 'workspace_id', 'created_at'})
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

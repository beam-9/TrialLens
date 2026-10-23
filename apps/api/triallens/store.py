from __future__ import annotations

import json
import fcntl
import os
import tempfile
from functools import wraps
import re
from pathlib import Path

from triallens.models import Answer, EvidenceBrief, EvidenceChunk, EvidenceExtraction, EvidenceSource, Workspace, utc_now
from triallens.answer_views import answer_read_view


def serialized_write(method):
    """Lock the entire read/modify/write operation, including across API workers."""
    @wraps(method)
    def locked(self, *args, **kwargs):
        with self.path.with_suffix(self.path.suffix + ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                return method(self, *args, **kwargs)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    return locked


class JsonStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parents[1] / "data" / "triallens.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @serialized_write
    def _initialize(self):
        if not self.path.exists():
            self._write({"workspaces": {}, "sources": {}, "chunks": {}, "extractions": {}, "answers": {}, "briefs": {}})

    def _read(self) -> dict:
        data = json.loads(self.path.read_text())
        for key in ["workspaces", "sources", "chunks", "extractions", "answers", "briefs"]:
            data.setdefault(key, {})
        return data

    def _write(self, data: dict) -> None:
        # Publish a complete snapshot: concurrent readers see the old or new file.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False) as file:
                temporary = file.name
                json.dump(data, file, indent=2, sort_keys=True)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    @serialized_write
    def create_workspace(self, workspace: Workspace) -> Workspace:
        data = self._read()
        data["workspaces"][workspace.id] = workspace.model_dump(mode="json")
        self._write(data)
        return workspace

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        raw = self._read()["workspaces"].get(workspace_id)
        return Workspace(**raw) if raw else None

    def list_workspaces(self) -> list[Workspace]:
        return [Workspace(**item) for item in self._read()["workspaces"].values()]

    @serialized_write
    def update_workspace(self, workspace: Workspace) -> Workspace:
        data = self._read()
        workspace.updated_at = utc_now()
        data["workspaces"][workspace.id] = workspace.model_dump(mode="json")
        self._write(data)
        return workspace

    @serialized_write
    def replace_workspace_evidence(
        self, workspace_id: str, sources: list[EvidenceSource], chunks: list[EvidenceChunk],
        extractions: list[EvidenceExtraction] | None = None
    ) -> None:
        data = self._read()
        data["sources"] = {
            sid: source
            for sid, source in data["sources"].items()
            if source["workspace_id"] != workspace_id
        }
        data["chunks"] = {
            cid: chunk
            for cid, chunk in data["chunks"].items()
            if chunk["workspace_id"] != workspace_id
        }
        data["extractions"] = {
            eid: extraction
            for eid, extraction in data["extractions"].items()
            if extraction["workspace_id"] != workspace_id
        }
        for source in sources:
            data["sources"][source.id] = source.model_dump(mode="json")
        for chunk in chunks:
            data["chunks"][chunk.id] = chunk.model_dump(mode="json")
        for extraction in extractions or []:
            data["extractions"][extraction.id] = extraction.model_dump(mode="json")
        self._write(data)

    def list_sources(self, workspace_id: str) -> list[EvidenceSource]:
        return [
            EvidenceSource(**item)
            for item in self._read()["sources"].values()
            if item["workspace_id"] == workspace_id
        ]

    def list_chunks(self, workspace_id: str) -> list[EvidenceChunk]:
        return [
            EvidenceChunk(**item)
            for item in self._read()["chunks"].values()
            if item["workspace_id"] == workspace_id
        ]

    @serialized_write
    def replace_workspace_extractions(self, workspace_id: str, extractions: list[EvidenceExtraction]) -> None:
        data = self._read()
        data["extractions"] = {
            eid: extraction
            for eid, extraction in data["extractions"].items()
            if extraction["workspace_id"] != workspace_id
        }
        for extraction in extractions:
            data["extractions"][extraction.id] = extraction.model_dump(mode="json")
        self._write(data)

    def list_extractions(self, workspace_id: str) -> list[EvidenceExtraction]:
        return [
            EvidenceExtraction(**item)
            for item in self._read()["extractions"].values()
            if item["workspace_id"] == workspace_id
        ]

    @serialized_write
    def update_extraction(self, workspace_id: str, extraction_id: str, updates: dict) -> EvidenceExtraction | None:
        data = self._read()
        raw = data["extractions"].get(extraction_id)
        if not raw or raw["workspace_id"] != workspace_id:
            return None
        for key, value in updates.items():
            if value is not None:
                raw[key] = value
        raw["has_quantitative_result"] = _has_number(raw.get("outcome_result", ""))
        data["extractions"][extraction_id] = raw
        self._write(data)
        return EvidenceExtraction(**raw)

    @serialized_write
    def save_answer(self, answer: Answer) -> Answer:
        data = self._read()
        data["answers"][answer.id] = answer.model_dump(mode="json")
        self._write(data)
        return answer

    def get_answer(self, answer_id: str) -> Answer | None:
        raw = self._read()["answers"].get(answer_id)
        return answer_read_view(Answer(**raw)) if raw else None

    def list_answers(self, workspace_id: str) -> list[Answer]:
        return [
            answer_read_view(Answer(**item))
            for item in self._read()["answers"].values()
            if item["workspace_id"] == workspace_id
        ]

    @serialized_write
    def set_answer_saved_to_brief(self, workspace_id: str, answer_id: str, saved: bool) -> Answer | None:
        # Update the stored flag, never write a read-view projection over history.
        data = self._read()
        raw = data["answers"].get(answer_id)
        if not raw or raw["workspace_id"] != workspace_id:
            return None
        raw["saved_to_brief"] = saved
        self._write(data)
        return answer_read_view(Answer(**raw))

    @serialized_write
    def save_brief(self, brief: EvidenceBrief) -> EvidenceBrief:
        data = self._read()
        data["briefs"][brief.workspace_id] = brief.model_dump(mode="json")
        self._write(data)
        return brief

    def get_brief(self, workspace_id: str) -> EvidenceBrief | None:
        raw = self._read()["briefs"].get(workspace_id)
        if not raw:
            return None
        brief = EvidenceBrief(**raw)
        brief.saved_answers = [answer_read_view(answer) for answer in brief.saved_answers]
        return brief


def _has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))

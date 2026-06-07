from __future__ import annotations

import json
from pathlib import Path

from triallens.models import Answer, EvidenceBrief, EvidenceChunk, EvidenceSource, Workspace, utc_now


class JsonStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parents[1] / "data" / "triallens.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"workspaces": {}, "sources": {}, "chunks": {}, "answers": {}, "briefs": {}})

    def _read(self) -> dict:
        return json.loads(self.path.read_text())

    def _write(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True))

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

    def update_workspace(self, workspace: Workspace) -> Workspace:
        data = self._read()
        workspace.updated_at = utc_now()
        data["workspaces"][workspace.id] = workspace.model_dump(mode="json")
        self._write(data)
        return workspace

    def replace_workspace_evidence(
        self, workspace_id: str, sources: list[EvidenceSource], chunks: list[EvidenceChunk]
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
        for source in sources:
            data["sources"][source.id] = source.model_dump(mode="json")
        for chunk in chunks:
            data["chunks"][chunk.id] = chunk.model_dump(mode="json")
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

    def save_answer(self, answer: Answer) -> Answer:
        data = self._read()
        data["answers"][answer.id] = answer.model_dump(mode="json")
        self._write(data)
        return answer

    def get_answer(self, answer_id: str) -> Answer | None:
        raw = self._read()["answers"].get(answer_id)
        return Answer(**raw) if raw else None

    def list_answers(self, workspace_id: str) -> list[Answer]:
        return [
            Answer(**item)
            for item in self._read()["answers"].values()
            if item["workspace_id"] == workspace_id
        ]

    def save_brief(self, brief: EvidenceBrief) -> EvidenceBrief:
        data = self._read()
        data["briefs"][brief.workspace_id] = brief.model_dump(mode="json")
        self._write(data)
        return brief

    def get_brief(self, workspace_id: str) -> EvidenceBrief | None:
        raw = self._read()["briefs"].get(workspace_id)
        return EvidenceBrief(**raw) if raw else None


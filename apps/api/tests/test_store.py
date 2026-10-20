from concurrent.futures import ThreadPoolExecutor
import time

from triallens.models import Workspace
from triallens.store import JsonStore


def test_concurrent_instances_preserve_all_workspace_saves(tmp_path):
    class SlowReadStore(JsonStore):
        def _read(self):
            data = super()._read()
            time.sleep(0.01)  # Widen the actual read/modify/write race.
            return data

    path = tmp_path / "workspaces.json"
    stores = [SlowReadStore(path) for _ in range(8)]
    workspaces = [Workspace(condition=f"Research topic {index}", source_types=[]) for index in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda pair: pair[0].create_workspace(pair[1]), zip(stores, workspaces)))
    assert {item.id for item in JsonStore(path).list_workspaces()} == {item.id for item in workspaces}


def test_failed_snapshot_write_keeps_previous_data(monkeypatch, tmp_path):
    import pytest
    import triallens.store as storage
    path = tmp_path / "workspaces.json"
    store = JsonStore(path)
    first = store.create_workspace(Workspace(condition="Existing topic", source_types=[]))
    def interrupted_dump(data, file, **kwargs):
        file.write('{"workspaces":')
        raise OSError("Simulated full disk")
    monkeypatch.setattr(storage.json, "dump", interrupted_dump)
    with pytest.raises(OSError, match="Simulated full disk"):
        store.create_workspace(Workspace(condition="New topic", source_types=[]))
    assert [item.id for item in store.list_workspaces()] == [first.id]
    assert {p.name for p in tmp_path.iterdir()} == {"workspaces.json", "workspaces.json.lock"}

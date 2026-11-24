import pytest
from app.storage import Store, Conflict


def test_persistence_and_stale_update(tmp_path):
    path = str(tmp_path / "runs.sqlite")
    store = Store(path)
    run = store.create({"status": "new"})
    updated = store.update(run["id"], 1, lambda p: {**p, "status": "reviewed"})
    assert updated["version"] == 2
    assert Store(path).get(run["id"])["status"] == "reviewed"
    with pytest.raises(Conflict):
        store.update(run["id"], 1, lambda p: p)
    assert len(store.get(run["id"])["events"]) == 2


def test_failed_update_rolls_back(tmp_path):
    store = Store(str(tmp_path / "runs.sqlite"))
    run = store.create({"status": "new"})

    def fail(p):
        raise ValueError("invalid")

    with pytest.raises(ValueError):
        store.update(run["id"], 1, fail)
    assert store.get(run["id"])["version"] == 1
    assert len(store.get(run["id"])["events"]) == 1

"""SQLite run storage with transactional optimistic review updates."""

from contextlib import contextmanager
import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL)"
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, payload):
        rid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                "INSERT INTO runs VALUES (?,?,?,?)", (rid, now, 1, json.dumps(payload, allow_nan=False))
            )
            db.execute(
                "INSERT INTO events(run_id,kind,created,payload) VALUES (?,?,?,?)",
                (rid, "created", now, "{}"),
            )
        return self.get(rid)

    def get(self, rid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
            if row is None:
                raise KeyError(rid)
            events = db.execute(
                "SELECT kind,created,payload FROM events WHERE run_id=? ORDER BY id", (rid,)
            ).fetchall()
        return dict(
            id=row["id"],
            created=row["created"],
            version=row["version"],
            **json.loads(row["payload"]),
            events=[dict(e) for e in events],
        )

    def list(self):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute("SELECT id,created,version FROM runs ORDER BY created DESC LIMIT 30")
            ]

    def update(self, rid, version, transform):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
            if row is None:
                raise KeyError(rid)
            if row["version"] != version:
                raise Conflict("This run changed. Reload it before reviewing again.")
            payload = transform(json.loads(row["payload"]))
            db.execute(
                "UPDATE runs SET payload=?,version=version+1 WHERE id=?",
                (json.dumps(payload, allow_nan=False), rid),
            )
            db.execute(
                "INSERT INTO events(run_id,kind,created,payload) VALUES (?,?,?,?)",
                (
                    rid,
                    "reviewed",
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps({"previous_version": version}),
                ),
            )
        return self.get(rid)

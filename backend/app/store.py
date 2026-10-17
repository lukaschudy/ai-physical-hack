"""Session persistence + original image / audio storage under DATA_DIR."""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol

from .models import Session


class SessionStore(Protocol):
    def save(self, session: Session) -> None: ...
    def get(self, session_id: str) -> Session | None: ...
    def list(self) -> list[Session]: ...


class MemorySessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def save(self, session: Session) -> None:
        self._sessions[session.id] = session.model_copy(deep=True)

    def get(self, session_id: str) -> Session | None:
        s = self._sessions.get(session_id)
        return s.model_copy(deep=True) if s else None

    def list(self) -> list[Session]:
        sessions = sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)
        return [s.model_copy(deep=True) for s in sessions]


class SqliteSessionStore:
    """One row per session: the full Session as JSON plus indexed columns for listing.

    A fresh connection per call keeps it safe under FastAPI's threadpool.
    """

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS sessions ("
                " id TEXT PRIMARY KEY,"
                " created_at REAL NOT NULL,"  # unix seconds, for ordering
                " status TEXT NOT NULL,"
                " data TEXT NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS sessions_created_at ON sessions (created_at)")
            db.execute("CREATE INDEX IF NOT EXISTS sessions_status ON sessions (status)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def save(self, session: Session) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO sessions (id, created_at, status, data) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (id) DO UPDATE SET"
                " created_at = excluded.created_at, status = excluded.status, data = excluded.data",
                (
                    session.id,
                    session.created_at.timestamp(),
                    session.status,
                    session.model_dump_json(),
                ),
            )

    def get(self, session_id: str) -> Session | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT data FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return Session.model_validate_json(row[0]) if row else None

    def list(self) -> list[Session]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT data FROM sessions ORDER BY created_at DESC").fetchall()
        return [Session.model_validate_json(r[0]) for r in rows]


class BlobStore:
    """Files on disk. Paths returned are relative to the root."""

    def __init__(self, root: Path):
        self.root = root

    def put(self, rel: str, data: bytes) -> str:
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return rel

    def path(self, rel: str) -> Path:
        path = (self.root / rel).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("path escapes data dir")
        return path

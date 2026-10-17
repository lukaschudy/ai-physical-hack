"""Session persistence + original image / audio storage under DATA_DIR."""

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
        return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)


class BlobStore:
    """Files on disk. Paths returned are relative to the root."""

    def __init__(self, root: Path):
        self.root = root

    def put(self, rel: str, data: bytes) -> str:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return rel

    def path(self, rel: str) -> Path:
        path = (self.root / rel).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("path escapes data dir")
        return path

"""Reference retrieval: Jev pulls labelled legit/fraud examples for the declared task."""

import json
import re
from pathlib import Path
from typing import Protocol

from .models import ReferenceAnnotation

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "references.json"


class ReferenceStore(Protocol):
    def retrieve(self, task: str, k: int = 6) -> list[ReferenceAnnotation]: ...


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


class JsonReferenceStore:
    """Keyword-overlap retrieval over a local JSON file (stand-in for MicroAGI's database)."""

    def __init__(self, path: Path = DEFAULT_PATH):
        self.refs = [ReferenceAnnotation(**r) for r in json.loads(path.read_text())]

    def retrieve(self, task: str, k: int = 6) -> list[ReferenceAnnotation]:
        query = _words(task)
        scored = [(len(query & _words(r.task + " " + r.description)), r) for r in self.refs]
        scored = [s for s in scored if s[0] > 0]
        scored.sort(key=lambda s: s[0], reverse=True)
        return [r for _, r in scored[:k]]

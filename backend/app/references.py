"""Reference retrieval: Jev pulls labelled legit/fraud examples for the declared task.

Data conventions (data/references.json): refs with task GENERIC_TASK are task-agnostic and always
retrievable; a fraud ref's first signal names its fraud pattern (e.g. "screen replay").
"""

import json
import re
from collections.abc import Callable
from itertools import zip_longest
from pathlib import Path
from typing import Protocol

from .models import ReferenceAnnotation

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "references.json"
GENERIC_TASK = "any task"


class ReferenceStore(Protocol):
    def retrieve(self, task: str, k: int = 6) -> list[ReferenceAnnotation]: ...


def stem(word: str) -> str:
    """Light suffix stripping, applied identically to queries and references."""
    for suffix, repl in (
        ("ies", "y"),
        ("ied", "y"),
        ("ing", ""),
        ("ed", ""),
        ("es", ""),
        ("s", ""),
    ):
        if word.endswith(suffix) and not word.endswith("ss") and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)] + repl
            break
    if len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "ls":
        word = word[:-1]  # chopp -> chop
    return word


STOPWORDS = {
    stem(w)
    for w in "a an the and or of to in on at for with from into by up out off my your his her "
    "their our some this that it its is are be been do doing does make making get put i me we "
    "you all".split()
}

# canonical term -> alternatives. A word may map to several canonicals ("clean" -> wash + tidy),
# so the declared task's other words decide which reference task wins.
_SYNONYMS = {
    "shirt": "tshirt tee blouse sweater hoodie jumper clothes clothing laundry garment towel "
    "jeans pants trousers",
    "wash": "clean rinse scrub washup dishwashing",
    "dish": "plate bowl cup mug glass cutlery utensil fork spoon pan pot crockery washup "
    "dishwashing",
    "chop": "cut dice slice mince julienne",
    "vegetable": "veg veggie veggies carrot onion pepper cucumber potato tomato lettuce celery "
    "zucchini courgette garlic salad",
    "bed": "sheet bedsheet linen duvet pillow blanket mattress bedding comforter",
    "tidy": "clean organize organise declutter arrange sort straighten",
    "desk": "workspace workstation",
    "water": "irrigate mist spray",
    "plant": "houseplant flower succulent herb garden fern",
    "sandwich": "toastie sub wrap panini blt",
    "assemble": "build construct screw install",
    "furniture": "shelf bookshelf bookcase chair cabinet ikea drawer dresser wardrobe desk stool "
    "flatpack",
}
SYNONYMS: dict[str, set[str]] = {}
for _canon, _alts in _SYNONYMS.items():
    for _alt in _alts.split():
        SYNONYMS.setdefault(stem(_alt), set()).add(stem(_canon))

# Verb-only overlap ("wash the car" vs "wash dishes") is not a task match.
ACTIONS = {stem(w) for w in "fold wash chop tidy water assemble".split()}


def terms(text: str, expand: bool = True) -> set[str]:
    """Normalised, stemmed content words, plus their synonym canonicals when expand is set."""
    out: set[str] = set()
    for word in re.findall(r"[a-z]+", text.lower()):
        s = stem(word)
        if len(word) > 1 and s not in STOPWORDS:
            out |= {s} | (SYNONYMS.get(s, set()) if expand else set())
    return out


def _balanced(
    refs: list[ReferenceAnnotation], n: int, score: Callable[[ReferenceAnnotation], int]
) -> list[ReferenceAnnotation]:
    """Up to n refs alternating legit/fraud, best-scoring first, file order on ties."""
    pools = [
        sorted((r for r in refs if r.label == lab), key=score, reverse=True)
        for lab in ("legit", "fraud")
    ]
    return [r for pair in zip_longest(*pools) for r in pair if r is not None][:n]


class JsonReferenceStore:
    """Synonym-aware keyword retrieval over a local JSON file (stand-in for MicroAGI's database).

    Returns the best-matching task's refs, balanced legit/fraud, plus generic refs in about a
    third of the slots (fraud patterns the task refs don't cover first). Unknown tasks get only
    generic refs.
    """

    def __init__(self, path: Path = DEFAULT_PATH):
        self.refs = [ReferenceAnnotation(**r) for r in json.loads(path.read_text())]
        self.generic = [r for r in self.refs if r.task == GENERIC_TASK]
        self.tasks: dict[str, list[ReferenceAnnotation]] = {}
        for r in self.refs:
            if r.task != GENERIC_TASK:
                self.tasks.setdefault(r.task, []).append(r)
        # task names stay unexpanded so a query synonym ("desk" -> furniture) can't tie two tasks
        self._task_terms = {t: terms(t, expand=False) for t in self.tasks}
        self._terms = {
            r.id: terms(" ".join([r.task, r.description, *r.signals])) for r in self.refs
        }

    def _matching(self, query: set[str]) -> list[ReferenceAnnotation]:
        """Refs of the best-scoring task(s) sharing a non-action word with the query."""
        scores: dict[str, int] = {}
        for task, refs in self.tasks.items():
            hits = query & self._task_terms[task]
            if hits - ACTIONS:
                described = set().union(*(self._terms[r.id] for r in refs))
                scores[task] = 3 * len(hits) + len(query & described)
        if not scores:
            return []
        best = max(scores.values())
        return [r for t, refs in self.tasks.items() if scores.get(t) == best for r in refs]

    def retrieve(self, task: str, k: int = 6) -> list[ReferenceAnnotation]:
        if k <= 0:
            return []
        query = terms(task)

        def score(r: ReferenceAnnotation) -> int:
            return len(query & self._terms[r.id])

        generic = [r for r in self.generic if r.label == "fraud"]
        specific = _balanced(self._matching(query), k - min(k // 3, len(generic)), score)
        if not specific:
            return _balanced(self.generic, k, score)
        covered = {r.signals[0] for r in specific if r.label == "fraud" and r.signals}
        generic.sort(key=lambda r: (bool(r.signals) and r.signals[0] in covered, -score(r)))
        return specific + generic[: k - len(specific)]

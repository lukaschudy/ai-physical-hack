"""Reference seed data + retrieval."""

import json
from collections import Counter

import pytest

from app.references import DEFAULT_PATH, GENERIC_TASK, JsonReferenceStore, stem, terms

PATTERNS = {
    "screen replay",
    "looped footage",
    "static photo",
    "idle motion",
    "wrong task",
    "another person",
    "too fast",
    "scene cuts",
}


@pytest.fixture(scope="module")
def store() -> JsonReferenceStore:
    return JsonReferenceStore()


# --- normalisation ---


@pytest.mark.parametrize(
    "words",
    [
        ("chop", "chopping", "chopped", "chops"),
        ("dish", "dishes"),
        ("plant", "plants"),
        ("water", "watering", "watered"),
        ("assemble", "assembling", "assembled"),
        ("tidy", "tidying", "tidies", "tidied"),
        ("vegetable", "vegetables"),
        ("glass", "glasses"),
    ],
)
def test_stem_conflates_inflections(words):
    assert len({stem(w) for w in words}) == 1


def test_terms_normalise_and_expand():
    assert terms("Fold a T-Shirt!") == {"fold", "shirt"}
    assert {"shirt", "fold"} <= terms("folding the laundry")
    assert {"wash", "tidy"} <= terms("clean")  # ambiguous word maps to both tasks
    assert terms("do the dishes", expand=False) == {"dish"}
    assert terms("the and of a") == set()


# --- seed data ---


def test_seed_data_shape():
    raw = json.loads(DEFAULT_PATH.read_text())
    refs = JsonReferenceStore().refs
    assert len(refs) == len(raw)
    assert len({r.id for r in refs}) == len(refs)
    tasks = {r.task for r in refs} - {GENERIC_TASK}
    assert len(tasks) >= 8
    for task in tasks:
        labels = Counter(r.label for r in refs if r.task == task)
        assert 2 <= labels["legit"] <= 3 and 2 <= labels["fraud"] <= 3, task
    assert all(r.description and len(r.signals) >= 2 for r in refs)


def test_fraud_patterns_covered(store):
    frauds = [r for r in store.refs if r.label == "fraud"]
    assert all(r.signals[0] in PATTERNS for r in frauds)
    specific = {r.signals[0] for r in frauds if r.task != GENERIC_TASK}
    generic = {r.signals[0] for r in store.generic if r.label == "fraud"}
    assert specific == PATTERNS and generic == PATTERNS
    assert any(r.label == "legit" for r in store.generic)


# --- retrieval ---


def test_every_task_retrieves_itself_balanced(store):
    for task in store.tasks:
        refs = store.retrieve(task)
        specific = [r for r in refs if r.task != GENERIC_TASK]
        assert len(refs) == 6 and len({r.id for r in refs}) == 6
        assert {r.task for r in specific} == {task}
        assert Counter(r.label for r in specific) == {"legit": 2, "fraud": 2}
        assert [r.task for r in refs[4:]] == [GENERIC_TASK] * 2


@pytest.mark.parametrize(
    ("query", "task"),
    [
        ("Folding my laundry", "fold a t-shirt"),
        ("fold towels", "fold a t-shirt"),
        ("do the dishes", "wash dishes"),
        ("clean the dishes", "wash dishes"),
        ("dicing onions", "chop vegetables"),
        ("slice veggies", "chop vegetables"),
        ("change the bedsheets", "make a bed"),
        ("clean my desk", "tidy a desk"),
        ("organise my workspace", "tidy a desk"),
        ("watering my houseplants", "water plants"),
        ("make a PB&J sandwich", "make a sandwich"),
        ("build an IKEA bookshelf", "assemble furniture"),
        ("assemble a desk", "assemble furniture"),
    ],
)
def test_paraphrases_hit_the_right_task(store, query, task):
    specific = {r.task for r in store.retrieve(query)} - {GENERIC_TASK}
    assert specific == {task}


@pytest.mark.parametrize("query", ["wash the car", "chop wood", "record my cat", "???"])
def test_unknown_task_gets_only_generic_refs(store, query):
    refs = store.retrieve(query)
    assert len(refs) == 6 and {r.task for r in refs} == {GENERIC_TASK}
    assert refs[0].label == "legit" and all(r.label == "fraud" for r in refs[1:])


def test_generic_refs_add_uncovered_patterns(store):
    refs = store.retrieve("fold a t-shirt", k=9)
    specific = [r for r in refs if r.task != GENERIC_TASK]
    generic = [r for r in refs if r.task == GENERIC_TASK]
    assert len(specific) == 6 and len(generic) == 3
    task_patterns = {r.signals[0] for r in specific if r.label == "fraud"}
    assert not task_patterns & {r.signals[0] for r in generic}
    assert all(r.label == "fraud" for r in generic)


@pytest.mark.parametrize(("k", "generic"), [(1, 0), (2, 0), (3, 1), (6, 2), (12, 6)])
def test_k_budget(store, k, generic):
    refs = store.retrieve("wash dishes", k=k)
    assert len(refs) == k
    assert sum(r.task == GENERIC_TASK for r in refs) == generic


def test_k_zero(store):
    assert store.retrieve("wash dishes", k=0) == []


def test_ties_keep_file_order_and_include_both_tasks(tmp_path):
    def ref(i: str, task: str, label: str) -> dict:
        return {"id": i, "task": task, "label": label, "description": "x", "signals": ["s"]}

    path = tmp_path / "refs.json"
    path.write_text(
        json.dumps(
            [
                ref("a1", "wash dishes", "legit"),
                ref("a2", "wash dishes", "fraud"),
                ref("b1", "chop vegetables", "legit"),
                ref("b2", "chop vegetables", "fraud"),
            ]
        )
    )
    refs = JsonReferenceStore(path).retrieve("dishes and vegetables", k=4)
    assert [r.id for r in refs] == ["a1", "a2", "b1", "b2"]

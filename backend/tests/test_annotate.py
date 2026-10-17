"""GeminiAnnotator with the google-genai client mocked."""

import json
from types import SimpleNamespace

import pytest
from google.genai import types

from app.annotate import AnnotationError, FakeAnnotator, GeminiAnnotator, parse_batch


def frame(**kw):
    base = {"action": "folding", "hands": "both", "objects": ["shirt"], "scene": "desk"}
    return base | {"anomalies": []} | kw


def batch_json(n=10, **kw):
    return json.dumps({"frames": [frame(**kw) for _ in range(n)], "summary": "Folds a shirt."})


class FakeModels:
    def __init__(self, *texts):
        self.texts, self.calls = list(texts), []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.texts.pop(0))


def annotator(*texts):
    models = FakeModels(*texts)
    return GeminiAnnotator("key", "flash-test", client=SimpleNamespace(models=models)), models


IMAGES = [bytes([0xFF, 0xD8, i]) for i in range(10)]


def test_annotate_sets_index_and_timestamp_from_batch_start():
    a, _ = annotator(batch_json(anomalies=["moire on a monitor"]))
    result = a.annotate(IMAGES, "fold a t-shirt", 20.0)
    assert [f.index for f in result.frames] == list(range(10))
    assert [f.timestamp_s for f in result.frames] == [20.0 + i for i in range(10)]
    assert result.frames[0].anomalies == ["moire on a monitor"]
    assert result.summary == "Folds a shirt."


def test_request_sends_task_and_frames_in_order_with_schema():
    a, models = annotator(batch_json())
    a.annotate(IMAGES, "fold a t-shirt", 0.0)
    (call,) = models.calls
    assert call["model"] == "flash-test"
    assert "fold a t-shirt" in call["contents"][0]
    parts = [p for p in call["contents"] if isinstance(p, types.Part)]
    assert [p.inline_data.data for p in parts] == IMAGES
    assert all(p.inline_data.mime_type == "image/jpeg" for p in parts)
    cfg = call["config"]
    assert cfg.response_mime_type == "application/json"
    assert "anomalies" in json.dumps(cfg.response_json_schema)
    assert "screen" in cfg.system_instruction and "another person" in cfg.system_instruction


@pytest.mark.parametrize(
    "bad", ["", "not json", batch_json(n=7), '{"frames": [{}], "summary": ""}']
)
def test_retries_once_on_bad_output(bad):
    a, models = annotator(bad, batch_json())
    assert len(a.annotate(IMAGES, "task", 0.0).frames) == 10
    assert len(models.calls) == 2


def test_raises_after_two_bad_outputs():
    a, models = annotator(batch_json(n=3), None)
    with pytest.raises(AnnotationError, match="unusable"):
        a.annotate(IMAGES, "task", 0.0)
    assert len(models.calls) == 2


def test_parse_batch_reports_frame_count_mismatch():
    with pytest.raises(ValueError, match="expected 10 frames, got 9"):
        parse_batch(batch_json(n=9), 10, 0.0)


def test_fake_annotator_still_offline():
    assert len(FakeAnnotator().annotate(IMAGES, "task", 0.0).frames) == 10

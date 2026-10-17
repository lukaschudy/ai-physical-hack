"""ElevenLabsSpeaker with the SDK client mocked."""

from unittest.mock import MagicMock

from app.config import load_settings
from app.tts import OUTPUT_FORMAT, ElevenLabsSpeaker, FakeSpeaker


def test_synthesize_joins_streamed_chunks():
    client = MagicMock()
    client.text_to_speech.convert.return_value = iter([b"ID3", b"\xff\xfb", b"end"])
    speaker = ElevenLabsSpeaker("key", "voice", "model", client=client)

    assert speaker.synthesize("What are you holding?") == b"ID3\xff\xfbend"
    assert speaker.mime == "audio/mpeg"
    client.text_to_speech.convert.assert_called_once_with(
        "voice", text="What are you holding?", model_id="model", output_format=OUTPUT_FORMAT
    )


def test_builds_sdk_client_from_api_key():
    speaker = ElevenLabsSpeaker("key", "voice", "model")
    assert speaker.client.text_to_speech is not None


def test_default_voice_and_low_latency_model(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.delenv("ELEVENLABS_TTS_MODEL", raising=False)
    s = load_settings()
    assert s.elevenlabs_voice_id == "JBFqnCBsd6RMkjVDRZzb"
    assert s.elevenlabs_tts_model == "eleven_flash_v2_5"


def test_fake_speaker_returns_wav():
    assert FakeSpeaker().synthesize("hi")[:4] == b"RIFF"

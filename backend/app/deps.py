"""Wire the pipeline: real clients when keys exist and USE_FAKES is off, fakes otherwise."""

from .annotate import FakeAnnotator, GeminiAnnotator
from .astra import ClaudeQuestioner, FakeQuestioner
from .config import Settings
from .jev import FakeComparer, GeminiComparer
from .pipeline import Pipeline
from .references import JsonReferenceStore
from .store import BlobStore, MemorySessionStore
from .stt import ElevenLabsTranscriber, FakeTranscriber
from .tts import ElevenLabsSpeaker, FakeSpeaker
from .verdict import FakeJudge, GeminiJudge


def build_pipeline(s: Settings) -> Pipeline:
    gemini = bool(s.gemini_api_key) and not s.use_fakes
    claude = bool(s.anthropic_api_key) and not s.use_fakes
    eleven = bool(s.elevenlabs_api_key) and not s.use_fakes
    return Pipeline(
        references=JsonReferenceStore(),
        annotator=GeminiAnnotator(s.gemini_api_key, s.flash_model) if gemini else FakeAnnotator(),
        comparer=GeminiComparer(s.gemini_api_key, s.jev_model) if gemini else FakeComparer(),
        questioner=ClaudeQuestioner(s.anthropic_api_key, s.astra_model)
        if claude
        else FakeQuestioner(),
        speaker=ElevenLabsSpeaker(
            s.elevenlabs_api_key, s.elevenlabs_voice_id, s.elevenlabs_tts_model
        )
        if eleven
        else FakeSpeaker(),
        transcriber=ElevenLabsTranscriber(s.elevenlabs_api_key, s.elevenlabs_stt_model)
        if eleven
        else FakeTranscriber(),
        judge=GeminiJudge(s.gemini_api_key, s.jev_model) if gemini else FakeJudge(),
        sessions=MemorySessionStore(),
        blobs=BlobStore(s.data_dir),
    )

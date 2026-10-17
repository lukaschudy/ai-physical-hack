import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    anthropic_api_key: str
    elevenlabs_api_key: str
    use_fakes: bool  # offline fakes for every external service
    data_dir: Path
    flash_model: str
    jev_model: str
    astra_model: str
    elevenlabs_voice_id: str
    elevenlabs_tts_model: str
    elevenlabs_stt_model: str


def load_settings() -> Settings:
    env = os.environ.get
    return Settings(
        gemini_api_key=env("GEMINI_API_KEY", ""),
        anthropic_api_key=env("ANTHROPIC_API_KEY", ""),
        elevenlabs_api_key=env("ELEVENLABS_API_KEY", ""),
        # TODO(integration): flip default to "0" once every real client is implemented.
        use_fakes=env("USE_FAKES", "1") == "1",
        data_dir=Path(env("DATA_DIR", "./var")),
        flash_model=env("FLASH_MODEL", "gemini-3.8-flash"),
        jev_model=env("JEV_MODEL", "gemini-flash-latest"),
        astra_model=env("ASTRA_MODEL", "claude-opus-5-5"),
        elevenlabs_voice_id=env("ELEVENLABS_VOICE_ID", ""),
        elevenlabs_tts_model=env("ELEVENLABS_TTS_MODEL", ""),
        elevenlabs_stt_model=env("ELEVENLABS_STT_MODEL", ""),
    )

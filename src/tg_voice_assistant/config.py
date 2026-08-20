from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_poll_timeout: int = Field(50, alias="TELEGRAM_POLL_TIMEOUT")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    transcription_model: str = Field("gpt-transcribe", alias="TRANSCRIPTION_MODEL")
    normalization_model: str = Field("gpt-5-nano", alias="NORMALIZATION_MODEL")
    database_path: Path = Field(Path("data/processed.sqlite3"), alias="DATABASE_PATH")
    audio_dir: Path = Field(Path("data/audio-tmp"), alias="AUDIO_DIR")

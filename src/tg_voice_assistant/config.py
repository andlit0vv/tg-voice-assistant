from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    telegram_api_id: int = Field(..., alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(..., alias="TELEGRAM_API_HASH")
    telegram_session: str = Field("data/session", alias="TELEGRAM_SESSION")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    transcription_model: str = Field("gpt-4o-mini-transcribe", alias="TRANSCRIPTION_MODEL")
    normalization_model: str = Field("gpt-4.1-mini", alias="NORMALIZATION_MODEL")
    database_path: Path = Field(Path("data/processed.sqlite3"), alias="DATABASE_PATH")
    audio_dir: Path = Field(Path("data/audio-tmp"), alias="AUDIO_DIR")
    max_parallel_chats: int = Field(32, alias="MAX_PARALLEL_CHATS")

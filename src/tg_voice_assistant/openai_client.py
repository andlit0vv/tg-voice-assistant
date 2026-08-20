from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

NORMALIZATION_PROMPT = """
Преврати расшифровку Telegram-голосового в естественное текстовое сообщение.

Сохраняй смысл, факты, порядок мыслей, стиль и сленг автора.
Убирай слова-паразиты вроде «ну», «вот», «короче», «типа», «как бы», если они не несут смысла.
Убирай повторы слов, фраз, самопоправки и дубли мыслей.
Не пересказывай и не добавляй ничего от себя.
Исправляй пунктуацию, регистр и очевидные ошибки распознавания.
  Делай естественные смысловые абзацы, если сообщение длинное.
Не используй эмодзи, Markdown, заголовки и длинное тире.
Верни только готовый текст для отправки в Telegram.
""".strip()


@dataclass(frozen=True)
class OpenAIStageResult:
    text: str
    usage: dict[str, Any]

    @property
    def total_tokens(self) -> int | None:
        value = self.usage.get("total_tokens")
        return value if isinstance(value, int) else None


class OpenAITranscriber:
    def __init__(self, api_key: str, transcription_model: str, normalization_model: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.transcription_model = transcription_model
        self.normalization_model = normalization_model

    async def transcribe(self, audio_path: Path) -> str:
        result = await self.transcribe_with_usage(audio_path)
        return result.text

    async def transcribe_with_usage(self, audio_path: Path) -> OpenAIStageResult:
        with audio_path.open("rb") as audio_file:
            result = await self.client.audio.transcriptions.create(
                model=self.transcription_model,
                file=audio_file,
            )
        return OpenAIStageResult(text=result.text.strip(), usage=_extract_usage(result))

    async def normalize(self, transcript: str) -> str:
        result = await self.normalize_with_usage(transcript)
        return result.text

    async def normalize_with_usage(self, transcript: str) -> OpenAIStageResult:
        response = await self.client.responses.create(
            model=self.normalization_model,
            instructions=NORMALIZATION_PROMPT,
            input=transcript,
        )
        return OpenAIStageResult(text=response.output_text.strip().strip('"'), usage=_extract_usage(response))


def _extract_usage(result: Any) -> dict[str, Any]:
    usage = getattr(result, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump(mode="json", exclude_none=True)
    if isinstance(usage, dict):
        return {key: value for key, value in usage.items() if value is not None}
    return {}

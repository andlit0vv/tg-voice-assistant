from pathlib import Path

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


class OpenAITranscriber:
    def __init__(self, api_key: str, transcription_model: str, normalization_model: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.transcription_model = transcription_model
        self.normalization_model = normalization_model

    async def transcribe(self, audio_path: Path) -> str:
        with audio_path.open("rb") as audio_file:
            result = await self.client.audio.transcriptions.create(
                model=self.transcription_model,
                file=audio_file,
            )
        return result.text.strip()

    async def normalize(self, transcript: str) -> str:
        response = await self.client.responses.create(
            model=self.normalization_model,
            instructions=NORMALIZATION_PROMPT,
            input=transcript,
        )
        return response.output_text.strip().strip('"')

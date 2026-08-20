from pathlib import Path

from openai import AsyncOpenAI

NORMALIZATION_PROMPT = """
Ты превращаешь русскую или смешанную устную речь из Telegram-голосового в готовое обычное текстовое сообщение.

Правила:
- Сохраняй исходный смысл, факты, порядок мыслей и стиль автора.
- Не пересказывай, не сокращай и не добавляй новые мысли.
- Исправляй пунктуацию, регистр и очевидные ошибки распознавания.
- Делай естественные смысловые абзацы, если сообщение длинное.
- Не добавляй эмодзи.
- Не используй длинное тире или среднее тире. Если нужно тире, используй обычный дефис или перестрой фразу.
- Не добавляй заголовки, пояснения, Markdown, кавычки вокруг результата или служебные фразы.
- Верни только финальный текст, который можно сразу отправить в Telegram.
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

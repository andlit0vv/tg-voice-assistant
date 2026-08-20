import asyncio
import logging
from collections import defaultdict
from pathlib import Path

from telethon import TelegramClient, events
from telethon.tl.custom.message import Message

from .config import Settings
from .openai_client import OpenAITranscriber
from .store import ProcessedStore

logger = logging.getLogger(__name__)


class VoiceAssistant:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = TelegramClient(
            settings.telegram_session,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        self.store = ProcessedStore(settings.database_path)
        self.transcriber = OpenAITranscriber(
            settings.openai_api_key,
            settings.transcription_model,
            settings.normalization_model,
        )
        self.chat_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.settings.audio_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        self.client.add_event_handler(self._on_outgoing_message, events.NewMessage(outgoing=True))
        await self.client.start()
        logger.info("Telegram Voice-to-Text Companion started")
        await self.client.run_until_disconnected()

    async def _on_outgoing_message(self, event: events.NewMessage.Event) -> None:
        message = event.message
        if not self._is_voice_message(message):
            return

        chat_id = event.chat_id
        message_id = message.id
        if chat_id is None or not self.store.try_claim(chat_id, message_id):
            return

        async with self.chat_locks[chat_id]:
            await self._process_voice(message, chat_id, message_id)

    async def _process_voice(self, message: Message, chat_id: int, message_id: int) -> None:
        audio_path = self._audio_path(chat_id, message_id)
        try:
            await message.download_media(file=str(audio_path))
            transcript = await self.transcriber.transcribe(audio_path)
            if not transcript:
                raise ValueError("empty transcription")
            normalized = await self.transcriber.normalize(transcript)
            if not normalized:
                raise ValueError("empty normalized text")
            await self.client.send_message(chat_id, normalized)
            self.store.mark_done(chat_id, message_id)
            logger.info("Processed outgoing voice %s/%s", chat_id, message_id)
        except Exception as exc:
            logger.exception("Failed to process outgoing voice %s/%s", chat_id, message_id)
            self.store.mark_failed(chat_id, message_id, str(exc))
        finally:
            audio_path.unlink(missing_ok=True)

    def _audio_path(self, chat_id: int, message_id: int) -> Path:
        return self.settings.audio_dir / f"{chat_id}_{message_id}.ogg"

    @staticmethod
    def _is_voice_message(message: Message) -> bool:
        return bool(message.voice)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    await VoiceAssistant(Settings()).start()


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .openai_client import OpenAITranscriber
from .store import ProcessedStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VoiceTask:
    chat_id: int
    message_id: int
    file_id: str
    user_id: int | None = None
    username: str | None = None
    business_connection_id: str | None = None


class GoogleSheetsLogger:
    def __init__(self, webhook_url: str | None) -> None:
        self.webhook_url = webhook_url
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) if webhook_url else None

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()

    async def log_voice_message(self, payload: dict[str, Any]) -> None:
        if not self.webhook_url or not self.client:
            return
        try:
            response = await self.client.post(self.webhook_url, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("ok") is False:
                logger.warning("Google Sheets webhook rejected voice log: %s", data)
        except Exception:
            logger.warning("Failed to log voice message to Google Sheets", exc_info=True)


class TelegramBotAPI:
    def __init__(self, token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.file_base_url = f"https://api.telegram.org/file/bot{token}"
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0))

    async def close(self) -> None:
        await self.client.aclose()

    async def request(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self.client.post(f"{self.base_url}/{method}", json=payload or {})
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API {method} failed: {data}")
        return data["result"]

    async def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message", "business_connection", "business_message"],
        }
        if offset is not None:
            payload["offset"] = offset
        return await self.request("getUpdates", payload)

    async def download_file(self, file_id: str, destination: Path) -> None:
        file_info = await self.request("getFile", {"file_id": file_id})
        file_path = file_info["file_path"]
        async with self.client.stream("GET", f"{self.file_base_url}/{file_path}") as response:
            response.raise_for_status()
            with destination.open("wb") as audio_file:
                async for chunk in response.aiter_bytes():
                    audio_file.write(chunk)

    async def send_message(self, chat_id: int, text: str, business_connection_id: str | None = None) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if business_connection_id:
            payload["business_connection_id"] = business_connection_id
        await self.request("sendMessage", payload)


class VoiceAssistant:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.telegram = TelegramBotAPI(settings.telegram_bot_token)
        self.store = ProcessedStore(settings.database_path)
        self.transcriber = OpenAITranscriber(
            settings.openai_api_key,
            settings.transcription_model,
            settings.normalization_model,
        )
        self.sheets_logger = GoogleSheetsLogger(settings.google_sheets_webhook_url)
        self.chat_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.settings.audio_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        logger.info("Telegram Voice-to-Text Business bot started")
        offset: int | None = None
        try:
            while True:
                updates = await self.telegram.get_updates(offset, self.settings.telegram_poll_timeout)
                for update in updates:
                    offset = update["update_id"] + 1
                    await self._handle_update(update)
        finally:
            await self.telegram.close()
            await self.sheets_logger.close()

    async def _handle_update(self, update: dict[str, Any]) -> None:
        if "business_connection" in update:
            connection = update["business_connection"]
            logger.info(
                "Business connection %s is %s",
                connection.get("id"),
                "enabled" if connection.get("is_enabled") else "disabled",
            )
            return

        message = update.get("business_message") or update.get("message")
        if not message:
            return

        task = self._voice_task_from_message(message)
        if task is None:
            return

        if not self.store.try_claim(task.chat_id, task.message_id):
            return

        async with self.chat_locks[task.chat_id]:
            await self._process_voice(task)

    def _voice_task_from_message(self, message: dict[str, Any]) -> VoiceTask | None:
        voice = message.get("voice")
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        file_id = voice.get("file_id") if isinstance(voice, dict) else None
        if chat_id is None or message_id is None or file_id is None:
            return None
        return VoiceTask(
            chat_id=chat_id,
            message_id=message_id,
            file_id=file_id,
            user_id=(message.get("from") or {}).get("id"),
            username=(message.get("from") or {}).get("username"),
            business_connection_id=message.get("business_connection_id"),
        )

    async def _process_voice(self, task: VoiceTask) -> None:
        audio_path = self._audio_path(task.chat_id, task.message_id)
        try:
            await self.telegram.download_file(task.file_id, audio_path)
            transcription_started = time.perf_counter()
            transcription = await self.transcriber.transcribe_with_usage(audio_path)
            transcription_seconds = time.perf_counter() - transcription_started
            transcript = transcription.text
            if not transcript:
                raise ValueError("empty transcription")
            normalization_started = time.perf_counter()
            normalization = await self.transcriber.normalize_with_usage(transcript)
            normalization_seconds = time.perf_counter() - normalization_started
            normalized = normalization.text
            if not normalized:
                raise ValueError("empty normalized text")
            await self.telegram.send_message(task.chat_id, normalized, task.business_connection_id)
            await self.sheets_logger.log_voice_message(
                {
                    "user_id": task.user_id,
                    "username": task.username,
                    "chat_id": task.chat_id,
                    "message_id": task.message_id,
                    "transcription": transcript,
                    "normalized_text": normalized,
                    "processing_seconds": round(transcription_seconds + normalization_seconds, 3),
                    "transcription_seconds": round(transcription_seconds, 3),
                    "normalization_seconds": round(normalization_seconds, 3),
                    "transcription_tokens": transcription.total_tokens,
                    "normalization_tokens": normalization.total_tokens,
                    "transcription_usage": transcription.usage,
                    "normalization_usage": normalization.usage,
                }
            )
            self.store.mark_done(task.chat_id, task.message_id)
            logger.info("Processed voice %s/%s", task.chat_id, task.message_id)
        except Exception as exc:
            logger.exception("Failed to process voice %s/%s", task.chat_id, task.message_id)
            self.store.mark_failed(task.chat_id, task.message_id, str(exc))
        finally:
            audio_path.unlink(missing_ok=True)

    def _audio_path(self, chat_id: int, message_id: int) -> Path:
        return self.settings.audio_dir / f"{chat_id}_{message_id}.ogg"


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    await VoiceAssistant(Settings()).start()


if __name__ == "__main__":
    asyncio.run(main())

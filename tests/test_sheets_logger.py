import asyncio

from tg_voice_assistant.app import GoogleSheetsLogger


class FailingClient:
    async def post(self, *args, **kwargs):
        raise RuntimeError("webhook is down")

    async def aclose(self):
        pass


def test_google_sheets_logger_ignores_missing_webhook_url():
    logger = GoogleSheetsLogger(None)

    asyncio.run(logger.log_voice_message({"message_id": 1}))
    asyncio.run(logger.close())


def test_google_sheets_logger_does_not_raise_on_request_failure():
    logger = GoogleSheetsLogger("https://example.invalid/webhook")
    logger.client = FailingClient()

    asyncio.run(logger.log_voice_message({"message_id": 1}))
    asyncio.run(logger.close())

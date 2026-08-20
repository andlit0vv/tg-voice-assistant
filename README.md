# Telegram Voice-to-Text Business Bot

Персональный Telegram-бот для Business Chat Automation: он получает голосовые сообщения из чатов, к которым вы дали доступ в Telegram, расшифровывает аудио через OpenAI и отправляет следом нормализованный текст в тот же чат.

## Что делает сервис

- Работает через Telegram Bot API, поэтому больше не требует `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` и Telethon session-файл.
- Поддерживает Telegram Business Chat Automation: подключите бота к своему аккаунту в Telegram и выберите чаты, к которым бот получит доступ.
- Также умеет работать как обычный бот: если отправить голосовое напрямую боту, он ответит текстом в чате с ботом.
- Реагирует на voice messages, скачивает аудио во временную папку, отправляет его в OpenAI для транскрибации, нормализует текст и удаляет локальный аудиофайл после обработки.
- Хранит обработанные `chat_id` и `message_id` в SQLite, чтобы перезапуски не создавали дубли.
- Опционально логирует успешно обработанные голосовые сообщения и usage-метрики OpenAI в Google Sheets через Google Apps Script webhook.
- Обрабатывает сообщения одного чата последовательно, чтобы несколько голосовых подряд получали текст в правильном порядке.
- Не отправляет технические ошибки собеседнику: проблемы попадают только в логи и локальную таблицу статусов.

## Как подключить через Telegram Business Chat Automation

1. Создайте бота через [@BotFather](https://t.me/BotFather) и получите bot token.
2. Скопируйте `.env.example` в `.env` и укажите `TELEGRAM_BOT_TOKEN` и `OPENAI_API_KEY`.
3. Запустите сервис локально или на сервере.
4. В Telegram откройте настройки Business Chat Automation, добавьте созданного бота и выберите чаты, к которым он может иметь доступ.
5. Отправьте голосовое сообщение в один из доступных чатов. Если Telegram передаст это сообщение боту как `business_message`, сервис отправит нормализованный текст обратно в тот же чат от имени подключённой business-автоматизации.

> Важно: точный набор сообщений, которые Telegram передаёт business-боту, зависит от настроек Telegram Business, выбранных чатов и прав подключения. Если голосовое не приходит в логи сервиса, проверьте, что бот подключён в Chat Automation и у него есть доступ к нужному чату.

## Локальный запуск

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m tg_voice_assistant.app
```

## Переменные окружения

```env
TELEGRAM_BOT_TOKEN=123456:your_bot_token_from_botfather
TELEGRAM_POLL_TIMEOUT=50
OPENAI_API_KEY=sk-your-key
TRANSCRIPTION_MODEL=gpt-transcribe
NORMALIZATION_MODEL=gpt-5-nano
DATABASE_PATH=data/processed.sqlite3
AUDIO_DIR=data/audio-tmp
GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/your-deployment-id/exec
```

- `TELEGRAM_BOT_TOKEN` - токен бота из BotFather.
- `TELEGRAM_POLL_TIMEOUT` - таймаут long polling в секундах.
- `OPENAI_API_KEY` - ключ OpenAI API.
- `TRANSCRIPTION_MODEL` - модель для распознавания аудио.
- `NORMALIZATION_MODEL` - модель для превращения распознанной устной речи в готовое текстовое сообщение.
- `DATABASE_PATH` - SQLite-база обработанных сообщений.
- `AUDIO_DIR` - временная папка для скачанных голосовых.
- `GOOGLE_SHEETS_WEBHOOK_URL` - необязательный URL Google Apps Script webhook для записи успешных обработок в Google Sheets. Если переменная пустая или webhook временно недоступен, бот продолжит отправлять пользователю нормализованный текст, а ошибка попадёт только в логи сервиса.

## Логирование в Google Sheets

1. Создайте Google Sheet с листом `Voice Logs`.
2. Добавьте в Apps Script функцию `doPost(e)` и опубликуйте проект как Web app с доступом для вызывающего сервиса.
3. Укажите URL публикации в `GOOGLE_SHEETS_WEBHOOK_URL`.

Сервис отправляет JSON со следующими полями: `user_id`, `username`, `chat_id`, `message_id`, `transcription`, `normalized_text`, `processing_seconds`, `transcription_seconds`, `normalization_seconds`, `transcription_tokens`, `normalization_tokens`, `transcription_usage`, `normalization_usage`. Поля `*_usage` содержат все usage-метрики, которые вернул OpenAI API для этапа, и могут понадобиться для последующего расчёта стоимости.

Пример расширенного Apps Script, совместимого с этими полями:

```js
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Voice Logs");

    if (!sheet) {
      throw new Error('Sheet "Voice Logs" not found');
    }

    sheet.appendRow([
      new Date(),
      data.user_id || "",
      data.username || "",
      data.chat_id || "",
      data.message_id || "",
      data.transcription || "",
      data.normalized_text || "",
      data.processing_seconds || "",
      data.transcription_seconds || "",
      data.normalization_seconds || "",
      data.transcription_tokens || "",
      data.normalization_tokens || "",
      JSON.stringify(data.transcription_usage || {}),
      JSON.stringify(data.normalization_usage || {})
    ]);

    return ContentService
      .createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: String(error) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
```

## Деплой на сервер

1. Скопируйте репозиторий на сервер.
2. Создайте `.env` по примеру `.env.example`.
3. Запустите сервис:

```bash
docker compose up -d --build
```

Логи доступны через:

```bash
docker compose logs -f tg-voice-assistant
```

## Ограничения безопасности

Храните `.env` как секрет: `TELEGRAM_BOT_TOKEN` позволяет управлять ботом, а `OPENAI_API_KEY` даёт доступ к вашему OpenAI API. Не коммитьте `.env` в репозиторий и не передавайте его третьим лицам.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
ENV PYTHONPATH=/app/src
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
CMD ["python", "-m", "tg_voice_assistant.app"]

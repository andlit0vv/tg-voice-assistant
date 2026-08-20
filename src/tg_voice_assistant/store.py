import sqlite3
from pathlib import Path


class ProcessedStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_messages (
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                error TEXT,
                PRIMARY KEY (chat_id, message_id)
            )
            """
        )
        self._connection.commit()

    def try_claim(self, chat_id: int, message_id: int) -> bool:
        cursor = self._connection.execute(
            """
            INSERT OR IGNORE INTO processed_messages (chat_id, message_id, status)
            VALUES (?, ?, 'processing')
            """,
            (chat_id, message_id),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def mark_done(self, chat_id: int, message_id: int) -> None:
        self._connection.execute(
            """
            UPDATE processed_messages
               SET status = 'done', updated_at = CURRENT_TIMESTAMP, error = NULL
             WHERE chat_id = ? AND message_id = ?
            """,
            (chat_id, message_id),
        )
        self._connection.commit()

    def mark_failed(self, chat_id: int, message_id: int, error: str) -> None:
        self._connection.execute(
            """
            UPDATE processed_messages
               SET status = 'failed', updated_at = CURRENT_TIMESTAMP, error = ?
             WHERE chat_id = ? AND message_id = ?
            """,
            (error[:1000], chat_id, message_id),
        )
        self._connection.commit()

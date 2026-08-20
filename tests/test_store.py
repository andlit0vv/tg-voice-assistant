from tg_voice_assistant.store import ProcessedStore


def test_try_claim_is_idempotent(tmp_path):
    store = ProcessedStore(tmp_path / "processed.sqlite3")

    assert store.try_claim(123, 456) is True
    assert store.try_claim(123, 456) is False


def test_failed_message_is_not_reclaimed(tmp_path):
    store = ProcessedStore(tmp_path / "processed.sqlite3")

    assert store.try_claim(1, 2) is True
    store.mark_failed(1, 2, "boom")

    assert store.try_claim(1, 2) is False

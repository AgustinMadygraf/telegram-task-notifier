from src.entities.telegram import extract_chat_id


def test_extract_chat_id_from_message() -> None:
    update = {"message": {"chat": {"id": 123}}}

    assert extract_chat_id(update) == 123


def test_extract_chat_id_from_callback_query_message() -> None:
    update = {"callback_query": {"message": {"chat": {"id": 456}}}}

    assert extract_chat_id(update) == 456


def test_extract_chat_id_returns_none_when_not_available() -> None:
    assert extract_chat_id({"message": {"chat": {"id": "123"}}}) is None
    assert extract_chat_id({"edited_message": {"chat": {}}}) is None
    assert extract_chat_id({}) is None

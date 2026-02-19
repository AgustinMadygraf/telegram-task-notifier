from typing import Any, Optional


def extract_chat_id(update: dict[str, Any]) -> Optional[int]:
    message = update.get("message") or update.get("edited_message")
    if isinstance(message, dict):
        chat = message.get("chat")
        if isinstance(chat, dict) and isinstance(chat.get("id"), int):
            return chat["id"]

    callback_query = update.get("callback_query")
    if isinstance(callback_query, dict):
        callback_message = callback_query.get("message")
        if isinstance(callback_message, dict):
            chat = callback_message.get("chat")
            if isinstance(chat, dict) and isinstance(chat.get("id"), int):
                return chat["id"]

    return None

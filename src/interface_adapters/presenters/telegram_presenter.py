from typing import Any


def present_webhook_result(chat_id: int | None) -> dict[str, Any]:
    return {"ok": True, "captured_chat_id": chat_id}


def present_last_chat(last_chat_id: int | None) -> dict[str, Any]:
    return {"last_chat_id": last_chat_id}


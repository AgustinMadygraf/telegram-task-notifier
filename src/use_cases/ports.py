from typing import Protocol


class ChatStateGateway(Protocol):
    def get_last_chat_id(self) -> int | None:
        ...

    def set_last_chat_id(self, chat_id: int) -> None:
        ...


class TelegramNotificationGateway(Protocol):
    async def send_message(self, chat_id: int, text: str) -> None:
        ...


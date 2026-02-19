import logging

from src.use_cases.ports import ChatStateGateway


class GetLastChatUseCase:
    def __init__(self, chat_state_gateway: ChatStateGateway, logger: logging.Logger) -> None:
        self._chat_state_gateway = chat_state_gateway
        self._logger = logger

    def execute(self) -> int | None:
        last_chat_id = self._chat_state_gateway.get_last_chat_id()
        self._logger.info("Consulta last_chat_id -> %s", last_chat_id)
        return last_chat_id

import logging
import threading
from pathlib import Path

from src.use_cases.ports import ChatStateGateway


class FileChatStateGateway(ChatStateGateway):
    def __init__(self, state_file_path: Path, logger: logging.Logger) -> None:
        self._state_file_path = state_file_path
        self._state_lock = threading.Lock()
        self._last_chat_id: int | None = None
        self._logger = logger
        self._load_last_chat_id_from_file()

    def get_last_chat_id(self) -> int | None:
        with self._state_lock:
            return self._last_chat_id

    def set_last_chat_id(self, chat_id: int) -> None:
        with self._state_lock:
            self._last_chat_id = chat_id
        self._persist_last_chat_id(chat_id)

    def _load_last_chat_id_from_file(self) -> None:
        if not self._state_file_path.exists():
            self._logger.info("No se encontro archivo de estado de chat en %s", self._state_file_path)
            return

        try:
            raw_value = self._state_file_path.read_text(encoding="utf-8").strip()
            if not raw_value:
                self._logger.warning("Archivo de estado vacio en %s", self._state_file_path)
                return

            chat_id = int(raw_value)
        except ValueError:
            self._logger.warning("Archivo de estado invalido en %s", self._state_file_path)
            return
        except OSError:
            self._logger.exception("No se pudo leer archivo de estado en %s", self._state_file_path)
            return

        with self._state_lock:
            self._last_chat_id = chat_id
        self._logger.info("last_chat_id restaurado desde archivo: %s", chat_id)

    def _persist_last_chat_id(self, chat_id: int) -> None:
        temp_path = self._state_file_path.with_suffix(".tmp")
        try:
            temp_path.write_text(str(chat_id), encoding="utf-8")
            temp_path.replace(self._state_file_path)
            self._logger.info("last_chat_id persistido en archivo: %s", chat_id)
        except OSError:
            self._logger.exception("No se pudo persistir last_chat_id en %s", self._state_file_path)


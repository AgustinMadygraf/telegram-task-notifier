import logging

from src.interface_adapters.gateways.file_chat_state_gateway import FileChatStateGateway


def test_file_chat_state_gateway_returns_none_when_file_missing(tmp_path) -> None:
    state_file = tmp_path / ".last_chat_id"
    gateway = FileChatStateGateway(state_file_path=state_file, logger=logging.getLogger("test"))

    assert gateway.get_last_chat_id() is None


def test_file_chat_state_gateway_loads_existing_chat_id(tmp_path) -> None:
    state_file = tmp_path / ".last_chat_id"
    state_file.write_text("12345", encoding="utf-8")
    gateway = FileChatStateGateway(state_file_path=state_file, logger=logging.getLogger("test"))

    assert gateway.get_last_chat_id() == 12345


def test_file_chat_state_gateway_ignores_invalid_file(tmp_path) -> None:
    state_file = tmp_path / ".last_chat_id"
    state_file.write_text("invalid", encoding="utf-8")
    gateway = FileChatStateGateway(state_file_path=state_file, logger=logging.getLogger("test"))

    assert gateway.get_last_chat_id() is None


def test_file_chat_state_gateway_ignores_empty_file(tmp_path) -> None:
    state_file = tmp_path / ".last_chat_id"
    state_file.write_text("", encoding="utf-8")
    gateway = FileChatStateGateway(state_file_path=state_file, logger=logging.getLogger("test"))

    assert gateway.get_last_chat_id() is None


def test_file_chat_state_gateway_persists_chat_id(tmp_path) -> None:
    state_file = tmp_path / ".last_chat_id"
    gateway = FileChatStateGateway(state_file_path=state_file, logger=logging.getLogger("test"))

    gateway.set_last_chat_id(999)

    assert gateway.get_last_chat_id() == 999
    assert state_file.read_text(encoding="utf-8").strip() == "999"

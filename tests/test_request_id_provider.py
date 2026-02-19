from uuid import UUID

from src.infrastructure.request_id.context_request_id_provider import (
    ContextRequestIdProvider,
    reset_request_id,
    set_request_id,
)


def test_context_request_id_provider_uses_context_value() -> None:
    provider = ContextRequestIdProvider()
    token = set_request_id("request-123")
    try:
        assert provider.new_id() == "request-123"
    finally:
        reset_request_id(token)


def test_context_request_id_provider_generates_uuid_without_context() -> None:
    provider = ContextRequestIdProvider()

    generated = provider.new_id()

    assert isinstance(UUID(generated), UUID)

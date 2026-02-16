class InvalidTelegramSecretError(Exception):
    """Raised when webhook secret does not match."""


class LastChatNotAvailableError(Exception):
    """Raised when there is no known chat_id to notify."""


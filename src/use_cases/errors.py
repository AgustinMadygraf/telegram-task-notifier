class InvalidTelegramSecretError(Exception):
    """Raised when webhook secret does not match."""


class LastChatNotAvailableError(Exception):
    """Raised when there is no known chat_id to notify."""


class HoneypotTriggeredError(Exception):
    """Raised when honeypot field is filled."""


class RateLimitExceededError(Exception):
    """Raised when request limit for contact endpoints is exceeded."""


class MailDeliveryError(Exception):
    """Raised when the mail gateway cannot deliver a message."""

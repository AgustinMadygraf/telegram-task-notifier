import logging

import src.infrastructure.smtp.smtp_mail_gateway as smtp_module
from src.entities.contact import ContactMessage, EmailAddress
from src.infrastructure.smtp.smtp_mail_gateway import SmtpMailGateway


class DummySMTP:
    instances: list["DummySMTP"] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.sent_message = None
        DummySMTP.instances.append(self)

    def __enter__(self) -> "DummySMTP":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def send_message(self, message: object) -> None:
        self.sent_message = message


def _contact_message() -> ContactMessage:
    return ContactMessage(
        name="Jane Doe",
        email=EmailAddress("jane@example.com"),
        message="Need a demo",
        meta={"source": "landing"},
        attribution={"website": ""},
    )


def test_smtp_mail_gateway_sends_message_with_tls_and_auth(monkeypatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr(smtp_module.smtplib, "SMTP", DummySMTP)
    gateway = SmtpMailGateway(
        host="smtp.example.com",
        port=587,
        username="user",
        password="pass",
        use_tls=True,
        sender="no-reply@example.com",
        default_recipient="ops@example.com",
        logger=logging.getLogger("test"),
    )

    gateway.send_contact_email(_contact_message(), request_id="req-123")

    smtp = DummySMTP.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.logged_in == ("user", "pass")
    assert smtp.sent_message["Subject"] == "[Contact] New request #req-123"
    assert smtp.sent_message["From"] == "no-reply@example.com"
    assert smtp.sent_message["To"] == "ops@example.com"
    assert smtp.sent_message["Reply-To"] == "jane@example.com"


def test_smtp_mail_gateway_skips_login_without_credentials(monkeypatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr(smtp_module.smtplib, "SMTP", DummySMTP)
    gateway = SmtpMailGateway(
        host="smtp.example.com",
        port=25,
        username="",
        password="",
        use_tls=False,
        sender="sender@example.com",
        default_recipient="ops@example.com",
        logger=logging.getLogger("test"),
    )

    gateway.send_contact_email(_contact_message(), request_id="req-999")

    smtp = DummySMTP.instances[0]
    assert smtp.started_tls is False
    assert smtp.logged_in is None


def test_smtp_mail_gateway_safe_helpers_sanitize_and_truncate() -> None:
    assert SmtpMailGateway._safe_text("a\r\nb", max_length=10) == "a  b"
    assert SmtpMailGateway._safe_text("abcdef", max_length=3) == "abc..."
    assert SmtpMailGateway._safe_json({"k": "v"}, max_length=100) == '{"k": "v"}'

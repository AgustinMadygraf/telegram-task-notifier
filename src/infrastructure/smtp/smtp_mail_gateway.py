from email.message import EmailMessage
import json
import logging
import smtplib
import time

from src.entities.contact import ContactMessage
from src.shared.log_safety import mask_email, mask_identifier
from src.use_cases.ports import MailGateway


class SmtpMailGateway(MailGateway):  # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool,
        sender: str,
        default_recipient: str,
        logger: logging.Logger,
        timeout_seconds: float = 20.0,
        mask_sensitive_ids: bool = True,
    ) -> None:
        self._host = host.strip()
        self._port = port
        self._username = username.strip()
        self._password = password
        self._use_tls = use_tls
        self._sender = sender.strip()
        self._default_recipient = default_recipient.strip()
        self._logger = logger
        self._timeout_seconds = timeout_seconds
        self._mask_sensitive_ids = mask_sensitive_ids

    @staticmethod
    def _safe_text(value: object, max_length: int = 6000) -> str:
        text = str(value)
        sanitized = text.replace("\r", " ").replace("\n", " ").strip()
        if len(sanitized) > max_length:
            return f"{sanitized[:max_length]}..."
        return sanitized

    @classmethod
    def _safe_json(cls, value: object, max_length: int = 6000) -> str:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        return cls._safe_text(serialized, max_length=max_length)

    # pylint: disable=too-many-locals
    def send_contact_email(self, contact_message: ContactMessage, request_id: str) -> None:
        safe_request_id = self._safe_text(request_id, max_length=128)
        request_id_for_log = (
            safe_request_id if not self._mask_sensitive_ids else mask_identifier(safe_request_id, prefix=3, suffix=3)
        )
        message = EmailMessage()
        message["Subject"] = f"[Contact] New request #{safe_request_id}"
        message["From"] = self._sender
        message["To"] = self._default_recipient
        message["Reply-To"] = contact_message.email.value

        body = "\n".join(
            [
                f"request_id: {safe_request_id}",
                f"name: {self._safe_text(contact_message.name, max_length=256)}",
                f"email: {contact_message.email.value}",
                f"message: {self._safe_text(contact_message.message, max_length=6000)}",
                f"meta: {self._safe_json(contact_message.meta, max_length=3000)}",
                f"attribution: {self._safe_json(contact_message.attribution, max_length=3000)}",
            ]
        )
        message.set_content(body)

        phase = "connect"
        started_at = time.perf_counter()
        phase_started_at = started_at
        phase_timings: dict[str, float] = {}
        tls_response: object = None
        auth_response: object = None
        send_response: object = None
        self._logger.info(
            "smtp_send_start",
            extra={
                "event": "smtp_send_start",
                "request_id": request_id_for_log,
                "smtp_host": self._host,
                "smtp_port": self._port,
                "smtp_to": (
                    self._default_recipient if not self._mask_sensitive_ids else mask_email(self._default_recipient)
                ),
                "smtp_tls_enabled": self._use_tls,
                "smtp_auth_enabled": bool(self._username),
            },
        )

        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout_seconds) as smtp:
                phase_timings["connect_ms"] = round((time.perf_counter() - phase_started_at) * 1000, 2)

                phase = "starttls"
                if self._use_tls:
                    phase_started_at = time.perf_counter()
                    tls_response = smtp.starttls()
                    phase_timings["starttls_ms"] = round((time.perf_counter() - phase_started_at) * 1000, 2)

                phase = "login"
                if self._username:
                    phase_started_at = time.perf_counter()
                    auth_response = smtp.login(self._username, self._password)
                    phase_timings["auth_ms"] = round((time.perf_counter() - phase_started_at) * 1000, 2)

                phase = "send"
                phase_started_at = time.perf_counter()
                send_response = smtp.send_message(message)
                phase_timings["send_ms"] = round((time.perf_counter() - phase_started_at) * 1000, 2)

            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            self._logger.info(
                "smtp_send_success",
                extra={
                    "event": "smtp_send_success",
                    "request_id": request_id_for_log,
                    "smtp_to": (
                        self._default_recipient if not self._mask_sensitive_ids else mask_email(self._default_recipient)
                    ),
                    "duration_ms": elapsed_ms,
                    "phase_timings_ms": phase_timings,
                    "starttls_code": self._extract_smtp_response_code(tls_response),
                    "auth_code": self._extract_smtp_response_code(auth_response),
                    "send_refused_count": len(send_response) if isinstance(send_response, dict) else 0,
                },
            )
        except Exception:
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            self._logger.exception(
                "smtp_send_failure",
                extra={
                    "event": "smtp_send_failure",
                    "request_id": request_id_for_log,
                    "smtp_to": (
                        self._default_recipient if not self._mask_sensitive_ids else mask_email(self._default_recipient)
                    ),
                    "phase": phase,
                    "duration_ms": elapsed_ms,
                    "phase_timings_ms": phase_timings,
                },
            )
            raise

    @staticmethod
    def _extract_smtp_response_code(response: object) -> int | None:
        if isinstance(response, tuple) and response and isinstance(response[0], int):
            return response[0]
        return None

"""SMTP delivery shared by dashboard modules; no credentials are logged."""

import smtplib
import ssl
from email.headerregistry import Address
from email.errors import HeaderParseError

from flask import current_app

from configs import paths


class EmailDeliveryError(Exception):
    def __init__(self, code=502):
        self.code = code
        self.public_message = (
            "Email service is not configured" if code == 503 else "Não foi possível enviar a mensagem. Tente novamente."
        )
        super().__init__(self.public_message)


def valid_email(value):
    """Accept one bare mailbox, never a list or an injected header."""
    if not isinstance(value, str) or not value or any(char in value for char in "\r\n"):
        return False
    try:
        address = Address(addr_spec=value)
        return bool(address.username and address.domain and address.addr_spec == value)
    except (ValueError, IndexError, HeaderParseError):
        return False


def _setting(name, default=None):
    value = current_app.config.get(name, getattr(paths, name, None))
    return default if value is None else value


def _flag(name, default):
    value = str(_setting(name, default)).strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        raise ValueError("Invalid SMTP boolean")
    return value in {"true", "1", "yes", "on"}


def deliver_email(message):
    """Return only after SMTP accepts every To/CC recipient."""
    try:
        host = _setting("SMTP_HOST")
        sender = _setting("SMTP_FROM_ADDRESS")
        username = _setting("SMTP_USERNAME")
        password = _setting("SMTP_PASSWORD")
        use_ssl = _flag("SMTP_USE_SSL", False)
        use_tls = _flag("SMTP_USE_TLS", not use_ssl)
        port = int(_setting("SMTP_PORT", 465 if use_ssl else 587))
        timeout = float(_setting("SMTP_TIMEOUT", 15))
        if (
            not host or not valid_email(sender) or not 1 <= port <= 65535
            or not 0 < timeout <= 60 or (use_ssl and use_tls)
            or bool(username) != bool(password)
        ):
            raise ValueError("Invalid SMTP configuration")
    except (TypeError, ValueError):
        raise EmailDeliveryError(503) from None

    message["From"] = sender
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    options = {"context": ssl.create_default_context()} if use_ssl else {}
    try:
        with smtp_class(host, port, timeout=timeout, **options) as smtp:
            if use_tls:
                smtp.starttls(context=ssl.create_default_context())
            if username:
                smtp.login(username, password)
            refused = smtp.send_message(message)
            if refused:
                raise EmailDeliveryError()
    except (smtplib.SMTPException, OSError, ValueError):
        raise EmailDeliveryError() from None

import json
import logging
import os
from datetime import datetime, timezone


_SENSITIVE_FRAGMENTS = (
    "password",
    "pass",
    "token",
    "secret",
    "session",
    "api_hash",
    "encryption_key",
    "phone_code",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(fragment in normalized for fragment in _SENSITIVE_FRAGMENTS)


def sanitize_context(context: dict | None) -> dict:
    if not context:
        return {}

    safe = {}
    for key, value in context.items():
        key_text = str(key)
        if _is_sensitive_key(key_text):
            safe[key_text] = "[REDACTED]"
            continue

        if isinstance(value, dict):
            safe[key_text] = sanitize_context(value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            safe[key_text] = value
        else:
            safe[key_text] = str(value)
    return safe


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        event = getattr(record, "event", None)
        if event:
            payload["event"] = event

        context = getattr(record, "context", None)
        if context:
            payload["context"] = sanitize_context(context)

        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str | None = None) -> None:
    configured_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    numeric_level = getattr(logging, configured_level, logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root.handlers.clear()
    root.addHandler(handler)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    message: str | None = None,
    **context,
) -> None:
    logger.log(
        level,
        message or event,
        extra={
            "event": event,
            "context": sanitize_context(context),
        },
    )

"""
backend/app/core/logging.py
EduPlus AI Timetable Maker — Structured Application Logging with Request ID & Secret Redaction
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from datetime import datetime, timezone

from backend.app.core.config import settings

# Per-request correlation ID propagated through middleware and logs
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9\-_\.]+|(?:password|secret|token|api_key|apikey)\s*[=:]\s*['\"]?[^\s,'\"\}]+)"
)


class SecretRedactingFilter(logging.Filter):
    """Prevents accidental logging of raw Bearer tokens, passwords, or API keys."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET_PATTERN.sub("[REDACTED]", record.msg)
        record.request_id = request_id_ctx.get()
        return True


class JsonLogFormatter(logging.Formatter):
    """Structured JSON formatter suitable for production log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", request_id_ctx.get()),
            "message": record.getMessage(),
        }
        if record.exc_info and not settings.is_production:
            log_entry["exception"] = self.formatException(record.exc_info)
        elif record.exc_info:
            log_entry["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SecretRedactingFilter())

    if settings.LOG_FORMAT == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] [req=%(request_id)s] %(name)s: %(message)s")
        )

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    app_logger = logging.getLogger("eduplus")
    app_logger.setLevel(level)
    return app_logger


logger = setup_logging()

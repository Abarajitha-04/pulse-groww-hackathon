"""
Structured (JSON) logging setup.

Why JSON instead of the default `logging.basicConfig` text format: any
real log aggregator (CloudWatch, Datadog, Loki, even `journalctl -o json`)
wants one JSON object per line so it can index fields like `request_id`
or `status_code` — a free-text log line makes that a regex-parsing
exercise instead of a query. This intentionally doesn't reach for a
dependency (structlog, python-json-logger) for something this small: a
custom `logging.Formatter` is ~30 lines and one less thing to pin/upgrade.

`request_id_var` is a contextvar rather than a global so it stays correct
under concurrent requests (each asyncio task/request gets its own value,
unlike a module-level variable that different requests would stomp on).
"""
import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Anything passed via logger.info("...", extra={...}) rides along
        # as its own top-level field instead of being dropped.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload:
                try:
                    json.dumps(value)
                    payload[key] = value
                except TypeError:
                    payload[key] = str(value)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet down noisy third-party loggers to WARNING so our own JSON
    # lines aren't drowned out; uvicorn's own access log is replaced by
    # our request-logging middleware (app/main.py), which carries
    # request_id and latency that uvicorn's default format doesn't.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

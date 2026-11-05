from __future__ import annotations
import logging
import re
import sys

_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*"), "[jwt]"),
    (re.compile(r"(?i)\b(password|token|secret|authorization|cookie|answers?|score|features?)\b\s*[=:]\s*\S+"), r"\1=[redacted]"),
]


def redact(text: str) -> str:
    for pat, rep in _PATTERNS:
        text = pat.sub(rep, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def configure_logging(stream=None, level: int = logging.INFO) -> logging.Handler:
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_edu_handler", False):
            root.removeHandler(h)
    handler._edu_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)
    return handler

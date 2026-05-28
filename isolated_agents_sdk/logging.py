"""Logging configuration for the Isolated Agents SDK.

Uses loguru as the backend. Stdlib logging calls (from third-party libraries
and internal ``logging.getLogger`` usage) are intercepted and forwarded to
loguru via InterceptHandler so everything flows through a single pipeline.
"""

from __future__ import annotations

import fnmatch
import logging
import sys
from typing import Any, List, Optional

from loguru import logger as _loguru_logger

# ---------------------------------------------------------------------------
# Sensitive-value masking
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS: List[str] = [
    "*PASSWORD*", "*SECRET*", "*TOKEN*", "*KEY*", "*CREDENTIALS*",
]


def _mask_value(key: str, value: Any) -> Any:
    """Return [MASKED] if key matches a sensitive pattern, else value."""
    if not isinstance(key, str):
        return value
    key_upper = key.upper()
    for pattern in _SENSITIVE_PATTERNS:
        if fnmatch.fnmatch(key_upper, pattern.upper()):
            return "[MASKED]"
    if isinstance(value, dict):
        return {k: _mask_value(k, v) for k, v in value.items()}
    return value


def add_global_sensitive_patterns(patterns: List[str]) -> None:
    """Register additional sensitive key patterns for log masking."""
    for p in patterns:
        if p not in _SENSITIVE_PATTERNS:
            _SENSITIVE_PATTERNS.append(p)


# ---------------------------------------------------------------------------
# Stdlib → loguru bridge
# ---------------------------------------------------------------------------

class _InterceptHandler(logging.Handler):
    """Forward every stdlib logging record into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Map stdlib level name → loguru level
        try:
            level: str | int = _loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Walk the call stack to find the true caller (skip loguru internals)
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        _loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logging(
    level: int = logging.INFO,
    use_colors: bool = True,
    log_file: Optional[str] = None,
    structured: bool = False,
) -> None:
    """Configure loguru for the SDK.

    Args:
        level: Logging level (default: logging.INFO).
        use_colors: Whether to colorise console output.
        log_file: Optional path to write logs to disk (JSON lines).
        structured: If True, console output is also JSON.
    """
    level_name = logging.getLevelName(level)

    # Remove all existing loguru sinks so repeated calls don't duplicate output
    _loguru_logger.remove()

    if structured:
        fmt = _json_formatter
    else:
        fmt = (
            "<green>{time:YYYY-MM-DDTHH:mm:ss.SSS}Z</green> "
            "<level>[{level}]</level> "
            "<cyan>{extra[sdk_name]}</cyan>: {message}"
        )

    _loguru_logger.configure(extra={"sdk_name": "isolated_agents_sdk"})

    _loguru_logger.add(
        sys.stdout,
        level=level_name,
        format=fmt,
        colorize=use_colors and not structured,
        filter=_sensitive_filter,
    )

    if log_file:
        _loguru_logger.add(
            log_file,
            level=level_name,
            format=_json_formatter,
            colorize=False,
            rotation="10 MB",
            retention=5,
            filter=_sensitive_filter,
        )

    # Intercept all stdlib logging (third-party libs + our own getLogger calls)
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    # Silence noisy stdlib loggers that would otherwise flood output
    for noisy in ("asyncio", "urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a stdlib Logger that forwards to loguru via InterceptHandler.

    Keeping the stdlib interface means no changes are needed in the ~20 files
    that already call ``logging.getLogger(__name__)``.
    """
    if not name.startswith("isolated_agents_sdk"):
        name = f"isolated_agents_sdk.{name}"
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sensitive_filter(record: dict) -> bool:  # type: ignore[type-arg]
    """Mask sensitive values in the loguru record's extra dict in-place."""
    for key in list(record.get("extra", {}).keys()):
        record["extra"][key] = _mask_value(key, record["extra"][key])
    return True


def _json_formatter(record: dict) -> str:  # type: ignore[type-arg]
    """Produce a JSON-lines string from a loguru record."""
    import json
    from datetime import timezone

    ts = record["time"].astimezone(timezone.utc).isoformat()
    entry: dict[str, Any] = {
        "timestamp": ts,
        "level": record["level"].name,
        "logger": record["name"],
        "message": record["message"],
    }
    extra = {k: _mask_value(k, v) for k, v in record.get("extra", {}).items()
             if k != "sdk_name"}
    if extra:
        entry["extra"] = extra
    if record["exception"]:
        entry["exception"] = str(record["exception"])
    return json.dumps(entry) + "\n"

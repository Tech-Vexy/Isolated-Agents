"""Logging configuration for the Isolated Agents SDK.

Provides a unified logging setup with support for colored console output
and timestamps.
"""

import logging
import sys
import json
import fnmatch
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List

# Detection for colored logs

# Detection for colored logs
try:
    import colorlog
    _HAS_COLORLOG = True
except ImportError:
    _HAS_COLORLOG = False

def setup_logging(
    level: int = logging.INFO,
    use_colors: bool = True,
    log_file: Optional[str] = None,
    structured: bool = False
) -> None:
    """Configure logging for the SDK.
    
    Args:
        level: Logging level (default: logging.INFO)
        use_colors: Whether to use colored output in console
        log_file: Optional path to write logs to disk
        structured: Whether to use JSON formatted output
    """
    # Map standard level names to user requested markers
    logging.addLevelName(logging.DEBUG, "Default")
    logging.addLevelName(logging.INFO, "INFO")
    logging.addLevelName(logging.WARNING, "Warning")
    logging.addLevelName(logging.ERROR, "Error")
    logging.addLevelName(logging.CRITICAL, "Error")

    # Root logger for the SDK
    logger = logging.getLogger("isolated_agents_sdk")
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if structured:
        formatter = JsonFormatter()
    else:
        # Custom "Pretty/Logfmt" unbundled format for console
        formatter = ConsoleFormatter()
        
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if requested
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_formatter = JsonFormatter() if structured else ConsoleFormatter()
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

def get_logger(name: str) -> logging.Logger:
    """Helper to get a logger within the SDK namespace."""
    if not name.startswith("isolated_agents_sdk"):
        name = f"isolated_agents_sdk.{name}"
    return logging.getLogger(name)

class ConsoleFormatter(logging.Formatter):
    """Formatter that outputs a flattened 'Pretty/Logfmt' style line for console."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensitive_patterns: List[str] = [
            "*PASSWORD*", "*SECRET*", "*TOKEN*", "*KEY*", "*CREDENTIALS*"
        ]

    def add_sensitive_patterns(self, patterns: List[str]):
        """Add additional sensitive patterns for masking."""
        for p in patterns:
            if p not in self.sensitive_patterns:
                self.sensitive_patterns.append(p)

    def _mask_value(self, key: str, value: Any) -> Any:
        """Mask value if key matches sensitive patterns."""
        if not isinstance(key, str):
            return value
            
        key_upper = key.upper()
        for pattern in self.sensitive_patterns:
            if fnmatch.fnmatch(key_upper, pattern.upper()):
                return "[MASKED]"
        
        # also check if the value itself looks like a dict/JSON and mask recursively
        if isinstance(value, dict):
            return {k: self._mask_value(k, v) for k, v in value.items()}
            
        return value

    def format(self, record: logging.LogRecord) -> str:
        # 1. Base components
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        level = record.levelname
        # Strip internal namespace prefix for cleaner logs
        logger_name = record.name.replace("isolated_agents_sdk.", "")
        message = record.getMessage()

        # 2. Extract extra fields
        extra_fields = []
        for key, value in record.__dict__.items():
            if key not in ("args", "asctime", "created", "exc_info", "exc_text",
                           "filename", "funcName", "levelname", "levelno", "lineno",
                           "module", "msecs", "message", "msg", "name", "pathname",
                           "process", "processName", "relativeCreated", "stack_info",
                           "thread", "threadName"):
                
                # v0.2.0: Mask sensitive fields
                value = self._mask_value(key, value)

                # Handle spaces in values (logfmt style quoting)
                if isinstance(value, str) and " " in value:
                    value = f'"{value}"'
                extra_fields.append(f"{key}={value}")

        # 3. Handle colors if enabled
        res_message = message
        if _HAS_COLORLOG:
            # We use colorlog's prefix logic if possible or manual ANSI
            color_map = {
                'Default':  '\033[36m', # Cyan
                'INFO':     '\033[32m', # Green
                'Warning':  '\033[33m', # Yellow
                'Error':    '\033[31m', # Red
            }
            reset = '\033[0m'
            color = color_map.get(level, '')
            res_line = f"{timestamp} {color}[{level}]{reset} {logger_name}: {message}"
        else:
            res_line = f"{timestamp} [{level}] {logger_name}: {message}"

        # 4. Append extras with separator if present
        if extra_fields:
            res_line += f" | {' '.join(extra_fields)}"

        # 5. Append exceptions
        if record.exc_info:
            res_line += f"\n{self.formatException(record.exc_info)}"

        return res_line

class JsonFormatter(logging.Formatter):
    """Formatter that outputs JSON for structured logging."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensitive_patterns: List[str] = [
            "*PASSWORD*", "*SECRET*", "*TOKEN*", "*KEY*", "*CREDENTIALS*"
        ]

    def add_sensitive_patterns(self, patterns: List[str]):
        """Add additional sensitive patterns for masking."""
        for p in patterns:
            if p not in self.sensitive_patterns:
                self.sensitive_patterns.append(p)

    def _mask_value(self, key: str, value: Any) -> Any:
        """Mask value if key matches sensitive patterns."""
        if not isinstance(key, str):
            return value
            
        key_upper = key.upper()
        for pattern in self.sensitive_patterns:
            if fnmatch.fnmatch(key_upper, pattern.upper()):
                return "[MASKED]"
        
        if isinstance(value, dict):
            return {k: self._mask_value(k, v) for k, v in value.items()}
            
        return value

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present in record (from 'extra' dict in logging calls)
        # Standard logging doesn't put 'extra' keys directly on record in a clean way,
        # but common structured logging patterns use this.
        for key, value in record.__dict__.items():
            if key not in ("args", "asctime", "created", "exc_info", "exc_text", 
                           "filename", "funcName", "levelname", "levelno", "lineno", 
                           "module", "msecs", "message", "msg", "name", "pathname", 
                           "process", "processName", "relativeCreated", "stack_info", 
                           "thread", "threadName"):
                # v0.2.0: Mask sensitive fields
                log_data[key] = self._mask_value(key, value)
            
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

def add_global_sensitive_patterns(patterns: List[str]):
    """Register sensitive patterns with all active SDK formatters."""
    root_logger = logging.getLogger("isolated_agents_sdk")
    for handler in root_logger.handlers:
        formatter = handler.formatter
        if hasattr(formatter, "add_sensitive_patterns"):
            formatter.add_sensitive_patterns(patterns)

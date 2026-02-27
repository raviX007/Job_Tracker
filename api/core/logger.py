"""Structured logging setup for the job application agent.

Console output format is controlled by LOG_FORMAT env var:
  - "console" (default): colored, human-readable output for development
  - "json": structured JSON output for production (Render, Datadog, etc.)

File handler always writes JSON regardless of LOG_FORMAT.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

SERVICE_NAME = "job-tracker-api"

EXTRA_FIELDS = ("job_id", "company", "platform", "profile_id", "action", "request_id")


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured logging.

    Includes Datadog APM correlation placeholders (dd.trace_id, dd.span_id).
    These are empty by default and filled automatically when ddtrace is installed.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "dd.trace_id": getattr(record, "dd.trace_id", ""),
            "dd.span_id": getattr(record, "dd.span_id", ""),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        for key in EXTRA_FIELDS:
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry)


class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter for console output."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"{color}{timestamp} [{record.levelname:8s}]{self.RESET} {record.name}: {record.getMessage()}"


def setup_logger(name: str = "jobbot") -> logging.Logger:
    """Set up and return the application logger.

    - Console handler: format controlled by LOG_FORMAT env var
    - File handler (logs/ dir): always JSON structured
    - Log level from LOG_LEVEL env var (default: INFO)
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "console").lower()

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Prevent duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    # Console handler — JSON in production, colored text in dev
    console = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        console.setFormatter(JSONFormatter())
    else:
        console.setFormatter(ConsoleFormatter())
    logger.addHandler(console)

    # File handler (always JSON)
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{name}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
    except PermissionError:
        pass 

# Singleton logger instance
logger = setup_logger()

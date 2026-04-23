"""Application logging setup."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.core.config import Settings

IMPORT_LOGGER_NAME = "my_fi.imports"


def configure_logging(settings: Settings) -> None:
    """Configure local diagnostic logs for import troubleshooting."""

    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = settings.logs_dir / settings.import_log_file

    logger = logging.getLogger(IMPORT_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)


def get_import_logger() -> logging.Logger:
    """Return the import diagnostic logger."""

    return logging.getLogger(IMPORT_LOGGER_NAME)

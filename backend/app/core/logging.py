"""
backend/app/core/logging.py
EduPlus AI Timetable Maker — Logging Configuration
"""

import logging
import sys
from backend.app.core.config import settings


def setup_logging():
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger("eduplus")
    logger.setLevel(level)
    return logger


logger = setup_logging()

